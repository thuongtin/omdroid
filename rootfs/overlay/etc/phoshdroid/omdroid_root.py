#!/usr/bin/env python3
"""Client side of the Omdroid fake-root broker, shared by sudo and fakeroot.

ProotService starts a second proot of the guest with `-0` (fake root) running
/etc/phoshdroid/omdroid-rootd.py. Two commands talk to it:

  sudo      - Omarchy's scripts want root; it builds a sudo-like environment.
  fakeroot  - makepkg runs its package step as `fakeroot -- bash ... makepkg -F`;
              the shim passes its own environment through, because makepkg
              expects the build environment intact (FAKEROOTKEY above all).

The wire format is one JSON request line, then frames both ways:
struct ">BI" (channel, length) and the payload.
    0 stdin   1 stdout   2 stderr   3 exit code  4 window size  5 error text

Nothing here grants real privilege: the guest is the Android app's own uid
inside its private storage.
"""
import fcntl
import json
import os
import signal
import socket
import struct
import sys
import termios
import threading
import tty

CH_STDIN = 0
CH_STDOUT = 1
CH_STDERR = 2
CH_EXIT = 3
CH_WINCH = 4
CH_ERROR = 5
MAX_FRAME = 1 << 16

DEFAULT_SOCKET = "/tmp/omdroid-root/sock"
# OMDROID_ROOTD_SOCK is the general name; OMDROID_SUDO_SOCK is what the host
# harness has always set for the sudo client, so it stays supported.
SOCKET_VARS = ("OMDROID_ROOTD_SOCK", "OMDROID_SUDO_SOCK")


def socket_path():
    for name in SOCKET_VARS:
        value = os.environ.get(name)
        if value:
            return value
    return DEFAULT_SOCKET


def write_all(fd, data):
    while data:
        written = os.write(fd, data)
        data = data[written:]


def terminal_size(fd=0):
    try:
        rows, cols = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 8))[:2]
    except OSError:
        return 0, 0
    return rows or 24, cols or 80


def tty_spec():
    """The window size to ask the broker for, or None when stdin is no tty."""
    if not os.isatty(0):
        return None
    rows, cols = terminal_size(0)
    return {"rows": rows, "cols": cols}


class Screen:
    """Raw mode on the caller's terminal, restored on every exit path."""

    def __init__(self):
        self.saved = None
        self.resized = False

    def enter(self):
        if not os.isatty(0):
            return
        try:
            self.saved = termios.tcgetattr(0)
            tty.setraw(0)
        except termios.error:
            self.saved = None

    def leave(self):
        if self.saved is None:
            return
        try:
            termios.tcsetattr(0, termios.TCSAFLUSH, self.saved)
        except termios.error:
            pass
        self.saved = None

    def window_size(self):
        rows, cols = terminal_size(0)
        return "%d %d" % (rows, cols)


def relay(request, prog, path=None):
    """Send one request to the broker, relay its frames, return the exit code."""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(2.0)
    try:
        client.connect(path or socket_path())
    except OSError:
        sys.stderr.write(
            "%s: the root broker is not running (start the Omdroid session)\n" % prog
        )
        return 1
    client.settimeout(None)

    screen = Screen()

    def restore_and_exit(signum, _frame):
        screen.leave()
        raise SystemExit(128 + signum)

    def mark_resized(_signum, _frame):
        screen.resized = True

    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGQUIT):
        signal.signal(signum, restore_and_exit)
    signal.signal(signal.SIGWINCH, mark_resized)

    screen.enter()
    exit_code = 1
    try:
        client.sendall(json.dumps(request).encode("utf-8") + b"\n")
        send_lock = threading.Lock()

        def send_frame(channel, payload):
            with send_lock:
                client.sendall(struct.pack(">BI", channel, len(payload)) + payload)

        # stdin is pumped from its own thread: a fd that cannot be polled (a
        # regular file, /dev/null: epoll answers EPERM) must not break the
        # client, and a program that never reads stdin must not block us.
        def pump_stdin():
            while True:
                try:
                    chunk = os.read(0, MAX_FRAME)
                except OSError:
                    chunk = b""
                if not chunk:
                    break
                try:
                    send_frame(CH_STDIN, chunk)
                except OSError:
                    return
            try:
                client.shutdown(socket.SHUT_WR)
            except OSError:
                pass

        threading.Thread(target=pump_stdin, daemon=True).start()

        client.settimeout(0.25)
        buffer = bytearray()
        frames = []

        def parse_frames():
            while len(buffer) >= 5:
                channel, length = struct.unpack(">BI", bytes(buffer[:5]))
                if length > MAX_FRAME:
                    raise OSError("oversized frame")
                if len(buffer) < 5 + length:
                    return
                frames.append((channel, bytes(buffer[5 : 5 + length])))
                del buffer[: 5 + length]

        done = False
        while not done:
            try:
                chunk = client.recv(MAX_FRAME)
            except socket.timeout:
                chunk = None
            except OSError:
                chunk = b""
            if chunk is not None:
                if not chunk:
                    break
                buffer += chunk
                parse_frames()
                while frames:
                    channel, payload = frames.pop(0)
                    if channel == CH_STDOUT:
                        write_all(1, payload)
                    elif channel == CH_STDERR:
                        write_all(2, payload)
                    elif channel == CH_ERROR:
                        write_all(2, payload)
                    elif channel == CH_EXIT:
                        exit_code = struct.unpack(">i", payload[:4])[0]
                        done = True
                        break
            if screen.resized:
                screen.resized = False
                try:
                    send_frame(CH_WINCH, screen.window_size().encode("ascii"))
                except OSError:
                    pass
    finally:
        screen.leave()
    return exit_code
