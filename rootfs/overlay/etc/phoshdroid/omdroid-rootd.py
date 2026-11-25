#!/usr/bin/env python3
"""omdroid-rootd: the fake-root broker behind Omdroid's `sudo`.

Started by ProotService as a SECOND proot of the session's rootfs, with `-0`
(fake root) instead of the desktop's `-i 1000:1000`. It listens on a Unix
socket under the shared /tmp and answers one request per connection:

    {"argv": [...], "cwd": "...", "env": {...}, "user": "root",
     "tty": {"rows": 40, "cols": 100} | null, "keep_env": false}

Frames, both directions: struct ">BI" (channel, length), then the payload.
    0 stdin        1 stdout       2 stderr       3 exit code (">i")
    4 window size ("rows cols", client -> broker)  5 error text

The request runs with the client's argv and cwd, a whitelisted environment,
and either the caller's terminal (a pty: bytes, window size, Ctrl+C/Z as
bytes) or plain pipes with stdin streamed. Concurrency: one thread per
connection, so a long install never blocks another `sudo`.

Nothing here grants real privilege: the whole guest is the Android app's own
uid inside its private storage. This exists so Omarchy's 70 scripts that call
`sudo` work at all.
"""
import errno
import fcntl
import json
import os
import pwd
import queue
import re
import selectors
import signal
import socket
import struct
import subprocess
import sys
import termios
import threading
import time

CH_STDIN = 0
CH_STDOUT = 1
CH_STDERR = 2
CH_EXIT = 3
CH_WINCH = 4
CH_ERROR = 5
MAX_FRAME = 1 << 16

DEFAULT_SOCKET = "/tmp/omdroid-root/sock"
DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Uids whose SO_PEERCRED may connect. On the device both proots are the same
# app uid and proot's fake_id0 reports it with the fake ids, so this is our own
# getuid() alone. The host-side harness has no proot: the client runs as an
# ordinary user while the broker is root, so it names that uid with
# --allow-peer-uid. Nothing on the device passes that option.
PEER_UIDS = {os.getuid()}


ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# sudo's default env_reset keeps a small list; -E keeps everything. HOME,
# USER, LOGNAME and SHELL are always the target user's (see build_env).
ALLOWED_ENV = frozenset(
    {
        "PATH",
        "TERM",
        "LANG",
        "LANGUAGE",
        "LC_ALL",
        "LC_CTYPE",
        "LC_MESSAGES",
        "WAYLAND_DISPLAY",
        "DISPLAY",
        "XDG_RUNTIME_DIR",
        "XDG_SESSION_TYPE",
        "XDG_CURRENT_DESKTOP",
        "TMPDIR",
        "EDITOR",
        "VISUAL",
        "PAGER",
        "MAKEFLAGS",
        "SUDO_USER",
        "SUDO_UID",
        "SUDO_GID",
        "SUDO_COMMAND",
    }
)


# One line per request in <socket dir>/rootd.log so the user can see what ran
# as fake root and what it returned (the report's manual test reads this).
LOG = {"path": None, "size": 0}
LOG_LOCK = threading.Lock()


def set_log_path(path):
    LOG["path"] = path
    try:
        LOG["size"] = os.path.getsize(path)
    except OSError:
        LOG["size"] = 0


def log_request(label, code):
    path = LOG["path"]
    if not path:
        return
    line = "%s %s exit=%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), label, code)
    with LOG_LOCK:
        try:
            if LOG["size"] > (256 << 10):
                with open(path, "w"):
                    pass
                LOG["size"] = 0
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line)
            LOG["size"] += len(line)
        except OSError:
            pass


def pack(channel, payload):
    return struct.pack(">BI", channel, len(payload)) + payload


class Conn:
    """Reads the JSON line, then frames, without losing bytes across them."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = bytearray()
        self.frames = []
        self.eof = False

    def read_header(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ValueError("connection closed before the request header")
            self.buf += chunk
            if len(self.buf) > (1 << 20):
                raise ValueError("request header too large")
        line, _, rest = bytes(self.buf).partition(b"\n")
        self.buf = bytearray(rest)
        self._parse()
        return json.loads(line.decode("utf-8"))

    def _parse(self):
        while len(self.buf) >= 5:
            channel, length = struct.unpack(">BI", bytes(self.buf[:5]))
            if length > MAX_FRAME:
                raise ValueError("frame too large")
            if len(self.buf) < 5 + length:
                return
            self.frames.append((channel, bytes(self.buf[5 : 5 + length])))
            del self.buf[: 5 + length]

    def pump(self):
        chunk = self.sock.recv(MAX_FRAME)
        if not chunk:
            self.eof = True
            return False
        self.buf += chunk
        self._parse()
        return True

    def send(self, channel, payload):
        self.sock.sendall(pack(channel, payload))


def fail(conn, message, code):
    try:
        conn.send(CH_ERROR, message)
        conn.send(CH_EXIT, struct.pack(">i", code))
    except OSError:
        pass


def resolve_user(name):
    name = str(name or "root")
    try:
        return pwd.getpwnam(name)
    except KeyError:
        pass
    try:
        return pwd.getpwuid(int(name))
    except (ValueError, KeyError):
        return None


def build_env(req, pw):
    sent = req.get("env") or {}
    keep = bool(req.get("keep_env"))
    env = {}
    if isinstance(sent, dict):
        for key, value in sent.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            if not ENV_NAME.match(key):
                continue
            if keep or key in ALLOWED_ENV:
                env[key] = value
    env["HOME"] = pw.pw_dir
    env["USER"] = pw.pw_name
    env["LOGNAME"] = pw.pw_name
    env["SHELL"] = pw.pw_shell or "/bin/bash"
    env.setdefault("PATH", DEFAULT_PATH)
    env.setdefault("TERM", "dumb")
    # `sudo VAR=value cmd` assignments apply to that command only, exactly as
    # sudo does it; they are not subject to the env_reset whitelist.
    extra = req.get("env_extra") or {}
    if isinstance(extra, dict):
        for key, value in extra.items():
            if isinstance(key, str) and isinstance(value, str) and ENV_NAME.match(key):
                env[key] = value
    return env


def spawn(argv, cwd, env, pw, **kwargs):
    extra = {}
    if pw.pw_uid != os.getuid():
        extra["user"] = pw.pw_uid
    if pw.pw_gid != os.getgid():
        extra["group"] = pw.pw_gid
    return subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        close_fds=True,
        **extra,
        **kwargs,
    )


def spawn_error(conn, argv, exc):
    name = argv[0]
    if isinstance(exc, FileNotFoundError):
        code = 127
        message = "sudo: %s: command not found\n" % name
    elif isinstance(exc, PermissionError):
        code = 126
        message = "sudo: %s: Permission denied\n" % name
    else:
        code = 126
        reason = getattr(exc, "strerror", None) or str(exc)
        message = "sudo: unable to execute %s: %s\n" % (name, reason)
    log_request(name, code)
    fail(conn, message.encode(), code)


def exit_status(returncode):
    if returncode is None:
        return 1
    if returncode < 0:
        return 128 + (-returncode)
    return returncode


def run_pipes(conn, argv, cwd, env, pw):
    try:
        proc = spawn(
            argv,
            cwd,
            env,
            pw,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        spawn_error(conn, argv, exc)
        return

    out, err, inp = proc.stdout, proc.stderr, proc.stdin
    assert out is not None and err is not None and inp is not None
    lock = threading.Lock()
    state = {"out": True, "err": True}
    done = threading.Event()

    def send(channel, payload):
        with lock:
            conn.send(channel, payload)

    def pump(fd, channel, key):
        try:
            while True:
                data = os.read(fd, MAX_FRAME)
                if not data:
                    break
                send(channel, data)
        except OSError:
            pass
        finally:
            state[key] = False
            if not state["out"] and not state["err"]:
                done.set()

    pumps = [
        threading.Thread(target=pump, args=(out.fileno(), CH_STDOUT, "out"), daemon=True),
        threading.Thread(target=pump, args=(err.fileno(), CH_STDERR, "err"), daemon=True),
    ]
    for thread in pumps:
        thread.start()

    # stdin goes through a queue so a program that never reads it cannot block
    # the socket loop (sudo sleep 100 with a pipe full of input).
    writes = queue.Queue()

    def writer():
        while True:
            item = writes.get()
            if item is None:
                try:
                    inp.close()
                except OSError:
                    pass
                return
            try:
                inp.write(item)
                inp.flush()
            except (BrokenPipeError, ValueError, OSError):
                pass

    threading.Thread(target=writer, daemon=True).start()

    conn.sock.settimeout(0.5)
    client_eof = False
    stdin_closed = False
    while not done.is_set():
        if not client_eof:
            try:
                if not conn.pump():
                    client_eof = True
            except socket.timeout:
                pass
            except OSError:
                client_eof = True
        # Frames can already be parsed when the header arrived (a pipe-full of
        # stdin usually comes before the first recv), so always drain first.
        while conn.frames:
            channel, payload = conn.frames.pop(0)
            if channel == CH_STDIN:
                writes.put(payload)
        if client_eof and not stdin_closed:
            stdin_closed = True
            writes.put(None)
        if client_eof:
            # stdin is closed; the command may still be working (a pacman
            # install after `echo y | sudo pacman -S`), so wait for its
            # output to end rather than for the client.
            if done.wait(0.2):
                break
            if proc.poll() is not None and done.wait(0.5):
                break

    # Once the client stops sending, stdin is closed and the command sees EOF.
    try:
        writes.put(None)
    except Exception:
        pass
    if not done.wait(2.0):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        returncode = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        returncode = proc.wait()
    for thread in pumps:
        thread.join(timeout=0.5)
    code = exit_status(returncode)
    log_request(argv[0], code)
    try:
        conn.send(CH_EXIT, struct.pack(">i", code))
    except OSError:
        pass


def set_winsize(fd, rows, cols):
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def run_pty(conn, argv, cwd, env, pw, spec):
    try:
        rows = int(spec.get("rows") or 24)
        cols = int(spec.get("cols") or 80)
    except (TypeError, ValueError):
        rows, cols = 24, 80
    try:
        master, slave = os.openpty()
    except OSError as exc:
        # No pty in this sandbox: fall back to pipes rather than fail the
        # command outright. Interactive prompts still work for line readers.
        run_pipes(conn, argv, cwd, env, pw)
        return

    set_winsize(slave, rows, cols)
    controlling = {"ok": True}

    def preexec():
        # A failure here is reported back through Popen and handled by the retry
        # below: the flag must be set in the PARENT, never in this forked child.
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    try:
        try:
            proc = spawn(
                argv,
                cwd,
                env,
                pw,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,
            )
        except OSError:
            # proot refuses setsid in some configurations; retry without a
            # controlling terminal and signal the child ourselves below.
            controlling["ok"] = False
            proc = spawn(argv, cwd, env, pw, stdin=slave, stdout=slave, stderr=slave)
    except OSError as exc:
        os.close(slave)
        os.close(master)
        spawn_error(conn, argv, exc)
        return
    finally:
        try:
            os.close(slave)
        except OSError:
            pass

    lock = threading.Lock()
    closed = {"master": False, "sock": False}

    def send(channel, payload):
        with lock:
            conn.send(channel, payload)

    def pump_master():
        try:
            while True:
                data = os.read(master, MAX_FRAME)
                if not data:
                    break
                send(CH_STDOUT, data)
        except OSError:
            pass
        finally:
            closed["master"] = True

    threading.Thread(target=pump_master, daemon=True).start()

    conn.sock.settimeout(0.5)
    while not closed["master"]:
        try:
            if not conn.pump():
                closed["sock"] = True
                break
        except socket.timeout:
            pass
        except OSError:
            closed["sock"] = True
            break
        while conn.frames:
            channel, payload = conn.frames.pop(0)
            if channel == CH_STDIN:
                try:
                    os.write(master, payload)
                except OSError:
                    break
                if not controlling["ok"]:
                    for byte, sig in ((b"\x03", signal.SIGINT), (b"\x1a", signal.SIGTSTP)):
                        if byte in payload:
                            try:
                                os.kill(proc.pid, sig)
                            except OSError:
                                pass
            elif channel == CH_WINCH:
                try:
                    r, c = payload.decode("ascii").split()
                    set_winsize(master, int(r), int(c))
                except (ValueError, UnicodeDecodeError):
                    pass
        if proc.poll() is not None and closed["master"]:
            break

    try:
        returncode = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if not closed["sock"]:
            returncode = None
        else:
            proc.kill()
            returncode = proc.wait()
    try:
        os.close(master)
    except OSError:
        pass
    if returncode is None:
        return
    code = exit_status(returncode)
    log_request(argv[0], code)
    try:
        conn.send(CH_EXIT, struct.pack(">i", code))
    except OSError:
        pass


def run(conn, req):
    argv = req.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
        or "\x00" in "".join(argv)
    ):
        log_request("?", 1)
        fail(conn, b"omdroid-rootd: bad request: argv\n", 1)
        return
    pw = resolve_user(req.get("user") or "root")
    if pw is None:
        log_request(argv[0], 1)
        fail(conn, ("sudo: unknown user: %s\n" % req.get("user")).encode(), 1)
        return
    cwd = req.get("cwd") or pw.pw_dir
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        cwd = pw.pw_dir
    env = build_env(req, pw)
    spec = req.get("tty")
    if isinstance(spec, dict):
        run_pty(conn, argv, cwd, env, pw, spec)
    else:
        run_pipes(conn, argv, cwd, env, pw)


def handle(sock):
    conn = Conn(sock)
    try:
        try:
            cred = sock.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            _pid, peer_uid, _peer_gid = struct.unpack("3i", cred)
            if peer_uid not in PEER_UIDS:
                fail(conn, b"omdroid-rootd: peer is not this app\n", 1)
                return
        except OSError:
            pass
        try:
            req = conn.read_header()
        except (ValueError, json.JSONDecodeError) as exc:
            fail(conn, ("omdroid-rootd: bad request: %s\n" % exc).encode(), 1)
            return
        run(conn, req)
    except (BrokenPipeError, ConnectionResetError):
        pass
    except OSError:
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(description="Omdroid fake-root broker")
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    parser.add_argument(
        "--allow-peer-uid",
        type=int,
        action="append",
        default=[],
        help="also accept this peer uid (host harness only; the device never passes it)",
    )
    args = parser.parse_args(argv)
    PEER_UIDS.update(args.allow_peer_uid)

    directory = os.path.dirname(args.socket)
    if directory:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
    set_log_path(os.path.join(directory or ".", "rootd.log"))
    try:
        os.unlink(args.socket)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(args.socket)
    os.chmod(args.socket, 0o600)
    server.listen(16)
    print(
        "root-broker ready pid=%d socket=%s log=%s"
        % (os.getpid(), args.socket, LOG["path"]),
        flush=True,
    )

    def stop(_signum, _frame):
        # The session is going away (or the broker is being stopped): leave
        # without touching whatever a running command is doing.
        os._exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while True:
        try:
            client, _addr = server.accept()
        except OSError as exc:
            if exc.errno == errno.EINTR:
                continue
            raise
        threading.Thread(target=handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main(sys.argv[1:])
