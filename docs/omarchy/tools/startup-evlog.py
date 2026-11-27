#!/usr/bin/env python3
"""Passive start-up / restart timeline for the guest session (diagnostic, never shipped).

Started from ~/.config/omdroid/session.env (see startup-timeline.sh), so it covers
start.sh from the first line. Writes /tmp/r11-evlog.txt — the name the measurements
in docs/omarchy/r11-mobile-startup.md quote.

Per line: seconds since the last mark, absolute UTC hh:mm:ss, event.
Events: the Hyprland instance dir and event socket appearing, every
openlayer/closelayer/openwindow/closewindow/monitoradded event (with its
namespace or window class), and the omarchy-ready marker.

Marks: touching /tmp/r11-evlog.mark re-bases the elapsed clock, so one file can
hold a cold start, a shell restart and a second cold start as separate segments.
It only LISTENS (socket2) and stats files, so it adds no request-socket traffic.
"""
import fcntl
import glob
import os
import socket
import time

# omdroid-ui.sh and start.sh both source session.env, so two copies start about
# 1 s apart: the first one takes the lock, the second exits before touching the log.
_LOCK = open("/tmp/r11-evlog.lock", "w")
try:
    fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    raise SystemExit(0)

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
MARK = "/tmp/r11-evlog.mark"
SECONDS = float(os.environ.get("R11_EVLOG_SECONDS", "1500"))
T0 = time.monotonic()
_mark = 0.0
try:
    _mark = os.stat(MARK).st_mtime
except OSError:
    pass
fh = open("/tmp/r11-evlog.txt", "w", buffering=1)

WANT = ("openlayer", "closelayer", "openwindow", "closewindow",
        "monitoradded", "monitoraddedv2", "monitorremoved")


def rebase():
    """Re-base the elapsed clock when the mark file is (re)touched."""
    global T0, _mark
    try:
        m = os.stat(MARK).st_mtime
    except OSError:
        return
    if m != _mark:
        _mark = m
        T0 = time.monotonic()
        fh.write("---- mark ----\n")


def log(msg):
    fh.write("%7.2f %s %s\n" % (time.monotonic() - T0, time.strftime("%H:%M:%S"), msg))


log("start pid=%d seconds=%g" % (os.getpid(), SECONDS))
sock = None
seen_dir = False
seen_marker = False
buf = b""
while time.monotonic() - T0 < SECONDS:
    rebase()
    if not seen_marker and os.path.exists(os.path.join(RUNTIME, "omarchy-ready")):
        seen_marker = True
        log("MARKER omarchy-ready")
    if sock is None:
        dirs = [d for d in glob.glob(os.path.join(RUNTIME, "hypr", "*")) if os.path.isdir(d)]
        if dirs and not seen_dir:
            seen_dir = True
            log("hypr instance dir %s" % os.path.basename(dirs[0]))
        for d in dirs:
            path = os.path.join(d, ".socket2.sock")
            if os.path.exists(path):
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    s.connect(path)
                    s.setblocking(False)
                    sock = s
                    log("socket2 connected")
                except OSError:
                    s.close()
    else:
        try:
            data = sock.recv(65536)
            if not data:
                sock = None
                log("socket2 closed")
            buf += data
            *lines, buf = buf.split(b"\n")
            for line in lines:
                text = line.decode("utf-8", "replace")
                if text.split(">>")[0] in WANT:
                    log(text[:110])
        except BlockingIOError:
            pass
        except OSError:
            sock = None
            log("socket2 error")
    time.sleep(0.05)
log("end")
