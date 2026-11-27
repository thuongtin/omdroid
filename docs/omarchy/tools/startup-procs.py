#!/usr/bin/env python3
"""Which processes the guest session starts, and when (diagnostic, never shipped).

Start it from ~/.config/omdroid/session.env (see startup-timeline.sh): it covers
start.sh onwards. Writes /tmp/r11-procs.txt (the name the measurements in
docs/omarchy/r11-mobile-startup.md quote):

   <elapsed> start pid=<pid> ppid=<ppid> cmd=<command line>
   <elapsed> exit  pid=<pid> ran=<seconds> cmd=<command line>

Only the shell-related families are recorded (see MATCH); every other process on
the phone is ignored so the file stays readable. Polls /proc at 0.1 s, forks
nothing. Touching /tmp/r11-procs.mark re-bases the clock (one segment per cold
start / shell restart).
"""
import fcntl
import os
import time

_LOCK = open("/tmp/r11-procs.lock", "w")
try:
    fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    raise SystemExit(0)

MARK = "/tmp/r11-procs.mark"
SECONDS = float(os.environ.get("R11_PROCS_SECONDS", "1500"))
T0 = time.monotonic()
_mark = 0.0
try:
    _mark = os.stat(MARK).st_mtime
except OSError:
    pass
fh = open("/tmp/r11-procs.txt", "w", buffering=1)

MATCH = ("omamobile", "quickshell -n", "omarchy-launch-shell",
         "omarchy-restart-shell", "omarchy-watch.py", "fit-x11.py", "cage")

live = {}  # pid -> (cmd, first seen monotonic)


def rebase():
    global T0, _mark
    try:
        m = os.stat(MARK).st_mtime
    except OSError:
        return
    if m != _mark:
        _mark = m
        T0 = time.monotonic()
        fh.write("---- mark ----\n")


def now_rel():
    return time.monotonic() - T0


def cmdline(pid):
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as handle:
            raw = handle.read(400)
    except OSError:
        return None
    text = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    return text or None


def ppid_of(pid):
    try:
        with open("/proc/%d/stat" % pid, "rb") as handle:
            data = handle.read(600).decode("utf-8", "replace")
    except OSError:
        return 0
    # comm may hold spaces and parentheses: split on the last ')'
    try:
        return int(data[data.rindex(")") + 2:].split()[1])
    except (ValueError, IndexError):
        return 0


fh.write("start pid=%d seconds=%g\n" % (os.getpid(), SECONDS))
while now_rel() < SECONDS:
    rebase()
    seen_now = set()
    try:
        entries = os.listdir("/proc")
    except OSError:
        entries = []
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in live:
            seen_now.add(pid)
            continue
        text = cmdline(pid)
        if not text or not any(m in text for m in MATCH):
            continue
        seen_now.add(pid)
        live[pid] = (text, time.monotonic())
        fh.write("%7.2f start pid=%d ppid=%d cmd=%s\n"
                 % (now_rel(), pid, ppid_of(pid), text[:160]))
    for pid, (text, first) in list(live.items()):
        if pid not in seen_now:
            del live[pid]
            fh.write("%7.2f exit  pid=%d ran=%.2f cmd=%s\n"
                     % (now_rel(), pid, time.monotonic() - first, text[:160]))
    time.sleep(0.1)
fh.write("end\n")
