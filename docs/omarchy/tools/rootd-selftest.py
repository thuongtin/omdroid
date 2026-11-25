#!/usr/bin/env python3
"""Host-side self-test for Omdroid's fake-root broker and its sudo client.

Runs both scripts on the build machine (x86, no proot, as the current user) so
the protocol, the relay and sudo's argument handling are proven before a
tablet is involved. Nothing here needs Android or the guest rootfs.

    python3 docs/omarchy/tools/rootd-selftest.py [-v]

The broker runs as the current user, so every command's target user is the
caller (`OMDROID_ROOTD_DEFAULT_USER`), and the pty cases exercise the same
code the tablet uses when the caller's stdin is a terminal.
"""
import fcntl
import os
import pty
import select
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time
import traceback

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TOOLS, "..", "..", ".."))
BROKER = os.path.join(ROOT, "rootfs/overlay/etc/phoshdroid/omdroid-rootd.py")
SUDO = os.path.join(ROOT, "rootfs/overlay/etc/phoshdroid/sudo")
FAKEROOT = os.path.join(ROOT, "rootfs/overlay/etc/phoshdroid/fakeroot")

VERBOSE = "-v" in sys.argv[1:]
ME = __import__("pwd").getpwuid(os.getuid()).pw_name


class Context:
    def __init__(self, workdir, sock, env):
        self.workdir = workdir
        self.sock = sock
        self.env = env


CTX = None


def client_env(overrides=None):
    env = dict(os.environ)
    env["OMDROID_SUDO_SOCK"] = CTX.sock
    env["OMDROID_ROOTD_DEFAULT_USER"] = ME
    env.pop("OMDROID_ROOTD_TEST", None)
    if overrides:
        env.update(overrides)
    return env


def run_client(args, stdin=b"", cwd=None, env_extra=None, timeout=30):
    proc = subprocess.run(
        [sys.executable, SUDO] + args,
        input=stdin,
        cwd=cwd or CTX.workdir,
        env=client_env(env_extra),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_fakeroot(args, stdin=b"", cwd=None, env_extra=None, timeout=30):
    proc = subprocess.run(
        [sys.executable, FAKEROOT] + args,
        input=stdin,
        cwd=cwd or CTX.workdir,
        env=client_env(env_extra),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_client_pty(args, writes, rows=40, cols=100, timeout=15):
    """Run the client with stdin on a real pty, so its stdin is a terminal."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    proc = subprocess.Popen(
        [sys.executable, SUDO] + args,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=CTX.workdir,
        env=client_env(),
        start_new_session=True,
    )
    os.close(slave)
    output = bytearray()

    def reader():
        while True:
            try:
                data = os.read(master, 65536)
            except OSError:
                return
            if not data:
                return
            output.extend(data)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    time.sleep(0.35)
    for chunk in writes:
        os.write(master, chunk)
        time.sleep(0.15)
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, 9)
        proc.wait()
        code = "TIMEOUT"
    thread.join(timeout=1)
    try:
        os.close(master)
    except OSError:
        pass
    return code, bytes(output)


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def argv_passthrough():
    code, out, err = run_client(["echo", "a", "b", "c"])
    return code == 0 and out == b"a b c\n" and err == b"", (code, out, err)


@case
def cwd_is_the_callers():
    work = os.path.join(CTX.workdir, "sub")
    os.makedirs(work, exist_ok=True)
    code, out, err = run_client(["pwd", "-P"], cwd=work)
    expected = os.path.realpath(work).encode() + b"\n"
    return code == 0 and out == expected, (code, out, expected)


@case
def stdin_is_streamed():
    code, out, _ = run_client(["cat"], stdin=b"x\ny\n")
    return code == 0 and out == b"x\ny\n", (code, out)


@case
def tee_writes_the_file():
    target = os.path.join(CTX.workdir, "tee.out")
    code, out, _ = run_client(["tee", target], stdin=b"hi\n")
    with open(target, "rb") as handle:
        written = handle.read()
    return code == 0 and out == b"hi\n" and written == b"hi\n", (code, out, written)


@case
def stdout_and_stderr_stay_apart():
    code, out, err = run_client(["sh", "-c", "echo out; echo err >&2"])
    return code == 0 and out == b"out\n" and err == b"err\n", (code, out, err)


@case
def exit_code_passes_through():
    code, _, _ = run_client(["sh", "-c", "exit 7"])
    return code == 7, code


@case
def false_returns_one():
    code, _, _ = run_client(["false"])
    return code == 1, code


@case
def signal_exit_is_128_plus_signal():
    code, _, _ = run_client(["sh", "-c", "kill -TERM $$"])
    return code == 143, code


@case
def missing_command_is_127():
    code, _, err = run_client(["definitely-not-a-command-xyz"])
    return code == 127 and b"command not found" in err, (code, err)


@case
def pty_reads_a_line():
    code, out = run_client_pty(["bash", "-c", "read x; echo got:$x"], [b"hello\n"])
    return code == 0 and b"got:hello" in out, (code, out)


@case
def pty_window_size():
    code, out = run_client_pty(["stty", "size"], [], rows=40, cols=100)
    return code == 0 and b"40 100" in out, (code, out)


@case
def pty_ctrl_c_kills_the_child():
    started = time.time()
    code, out = run_client_pty(["sleep", "100"], [b"\x03"], timeout=10)
    elapsed = time.time() - started
    return code == 130 and elapsed < 6.0, (code, round(elapsed, 2), out)


@case
def noninteractive_flag():
    code, _, _ = run_client(["-n", "true"])
    return code == 0, code


@case
def preserve_env_flag():
    code, out, _ = run_client(
        ["-E", "sh", "-c", "echo ${OMDROID_ROOTD_TEST:-unset}"],
        env_extra={"OMDROID_ROOTD_TEST": "kept"},
    )
    code2, out2, _ = run_client(
        ["sh", "-c", "echo ${OMDROID_ROOTD_TEST:-unset}"],
        env_extra={"OMDROID_ROOTD_TEST": "kept"},
    )
    return (
        code == 0
        and code2 == 0
        and out == b"kept\n"
        and out2 == b"unset\n",
        (code, out, code2, out2),
    )


@case
def run_as_another_user():
    code, out, _ = run_client(["-u", ME, "id", "-un"])
    return code == 0 and out.strip() == ME.encode(), (code, out)


@case
def unknown_user_fails():
    code, _, err = run_client(["-u", "no-such-user-xyz", "id"])
    return code == 1 and b"unknown user" in err, (code, err)


@case
def login_shell_runs_root_shell():
    code, out, _ = run_client(["-u", ME, "-i"], stdin=b"echo hi; exit\n")
    return code == 0 and b"hi" in out, (code, out)


@case
def plain_shell_runs_shell():
    code, out, _ = run_client(["-u", ME, "-s"], stdin=b"echo s; exit\n")
    return code == 0 and b"s" in out, (code, out)


@case
def validate_and_reset_are_noops():
    code1, out1, err1 = run_client(["-v"])
    code2, out2, err2 = run_client(["-k"])
    return (code1, out1, err1) == (0, b"", b"") and (code2, out2, err2) == (
        0,
        b"",
        b"",
    ), (code1, out1, err1, code2, out2, err2)


@case
def list_says_everything_is_allowed():
    code, out, _ = run_client(["-l"])
    return code == 0 and b"NOPASSWD: ALL" in out, (code, out)


@case
def help_and_version():
    code_h, out_h, _ = run_client(["-h"])
    code_v, out_v, _ = run_client(["-V"])
    return (
        code_h == 0
        and b"usage:" in out_h
        and code_v == 0
        and b"omdroid sudo" in out_v,
        (code_h, out_h, code_v, out_v),
    )


@case
def double_dash_ends_options():
    code, out, _ = run_client(["--", "/bin/echo", "--x"])
    return code == 0 and out == b"--x\n", (code, out)


@case
def unknown_flag_is_a_usage_error():
    code, _, err = run_client(["-Z", "true"])
    return code == 1 and b"invalid option" in err and b"usage:" in err, (code, err)


@case
def assignment_before_the_command():
    code, out, _ = run_client(["OMDROID_TEST=1", "sh", "-c", "echo $OMDROID_TEST"])
    return code == 0 and out == b"1\n", (code, out)


@case
def no_command_is_a_usage_error():
    code, _, err = run_client([])
    return code == 1 and b"usage:" in err, (code, err)


@case
def concurrent_requests():
    slow = subprocess.Popen(
        [sys.executable, SUDO, "sleep", "1.5"],
        cwd=CTX.workdir,
        env=client_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.15)
    started = time.time()
    code, out, _ = run_client(["echo", "fast"])
    elapsed = time.time() - started
    slow.wait(timeout=10)
    return (
        code == 0 and out == b"fast\n" and elapsed < 1.0 and slow.returncode == 0,
        (code, out, round(elapsed, 2), slow.returncode),
    )


@case
def broker_absent_fails_fast():
    env = client_env({"OMDROID_SUDO_SOCK": os.path.join(CTX.workdir, "nope.sock")})
    started = time.time()
    proc = subprocess.run(
        [sys.executable, SUDO, "true"],
        cwd=CTX.workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    elapsed = time.time() - started
    return (
        proc.returncode == 1 and b"not running" in proc.stderr and elapsed < 2.0,
        (proc.returncode, proc.stderr, round(elapsed, 2)),
    )


@case
def fakeroot_full_env_is_passed():
    # makepkg runs its package step as `fakeroot -- bash ... makepkg -F`, so the
    # shim must hand over the whole environment (no -E) and set FAKEROOTKEY.
    code, out, err = run_fakeroot(
        ["sh", "-c", "echo ${OMDROID_ROOTD_TEST:-unset}; echo ${FAKEROOTKEY:+key}"],
        env_extra={"OMDROID_ROOTD_TEST": "kept"},
    )
    return code == 0 and out == b"kept\nkey\n", (code, out, err)


@case
def fakeroot_cwd_is_the_callers():
    work = os.path.join(CTX.workdir, "fakeroot-sub")
    os.makedirs(work, exist_ok=True)
    code, out, err = run_fakeroot(["pwd", "-P"], cwd=work)
    expected = os.path.realpath(work).encode() + b"\n"
    return code == 0 and out == expected, (code, out, expected, err)


@case
def fakeroot_exit_code_passes_through():
    code, out, err = run_fakeroot(["sh", "-c", "exit 9"])
    return code == 9, (code, out, err)


@case
def fakeroot_stdin_is_streamed():
    code, out, err = run_fakeroot(["cat"], stdin=b"pkg\n")
    return code == 0 and out == b"pkg\n", (code, out, err)


@case
def fakeroot_version():
    code, out, _ = run_fakeroot(["-v"])
    code2, out2, _ = run_fakeroot(["--version"])
    return (
        code == 0 and code2 == 0 and out.startswith(b"fakeroot version")
        and out2 == out,
        (code, out, code2, out2),
    )


@case
def fakeroot_no_command_is_a_usage_error():
    code, _, err = run_fakeroot([])
    return code == 1 and b"usage:" in err, (code, err)


@case
def fakeroot_unsupported_option_is_an_error():
    # A saved fake state cannot survive the broker (one process per request),
    # so -s must fail loudly rather than pretend it worked.
    code, _, err = run_fakeroot(["-s", "state", "true"])
    return code == 1 and b"not supported" in err, (code, err)


def main():
    global CTX
    tmp = tempfile.mkdtemp(prefix="rootd-selftest-", dir=os.environ.get("TMPDIR"))
    sock = os.path.join(tmp, "omdroid-root", "sock")
    ctx = Context(
        workdir=os.path.join(tmp, "work"),
        sock=sock,
        env={},
    )
    os.makedirs(ctx.workdir, exist_ok=True)
    CTX = ctx

    broker = subprocess.Popen(
        [sys.executable, BROKER, "--socket", sock],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        if os.path.exists(sock):
            try:
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                probe.connect(sock)
                probe.close()
                break
            except OSError:
                pass
        time.sleep(0.05)
    else:
        broker.kill()
        print("FAIL: the broker never listened on", sock)
        return 1

    failures = 0
    try:
        for fn in CASES:
            try:
                ok, detail = fn()
            except Exception:
                ok, detail = False, traceback.format_exc(limit=2)
            print(("PASS " if ok else "FAIL ") + fn.__name__)
            if not ok or VERBOSE:
                print("     %r" % (detail,))
            if not ok:
                failures += 1
    finally:
        try:
            os.killpg(broker.pid, 15)
        except OSError:
            pass
        try:
            broker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(broker.pid, 9)
            except OSError:
                pass
        log = broker.stdout.read().decode("utf-8", "replace") if broker.stdout else ""
        if VERBOSE:
            print("--- broker log ---\n" + log)

    print("\n%d/%d passed" % (len(CASES) - failures, len(CASES)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
