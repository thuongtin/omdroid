#!/usr/bin/env python3
"""uhid-dock.py -- a dock keyboard and mouse that stay plugged in, for docked-input tests.

AOSP `hid` (/system/bin/hid) registers real uhid devices, so their events go through
InputReader, the accessibility input filter and the dispatcher exactly like a USB keyboard
and mouse on a dock (`adb shell input` skips the accessibility filter and cannot press a
non-primary button). `hid -` reads its JSON commands from stdin and keeps the devices
registered until stdin closes, so one long-running `hid` session gives a keyboard and a
mouse that stay attached while a test docks, undocks and kills the app around them.

    uhid-dock.py serve            # run as a background job: registers both devices
    uhid-dock.py send 'type hello world\\n'
    uhid-dock.py send 'combo gui return'      # SUPER+Return
    uhid-dock.py send 'move 10 0 20'          # 20 reports of (+10, 0)
    uhid-dock.py send 'click left'            # left | right | middle
    uhid-dock.py send 'press left' ; uhid-dock.py send 'release'
    uhid-dock.py send 'wheel -3'              # 3 clicks down (+ = up, HID convention)
    uhid-dock.py send 'quit'                  # unregisters both devices

The keyboard is a boot keyboard (8 modifier bits incl. Left GUI, six key slots, usages
0x00-0x65: Android classifies it as an alphabetic external keyboard). The mouse is a boot
mouse with 3 buttons, relative X/Y and a wheel, 8-bit signed (Android: SOURCE_MOUSE, external).
Both report bus usb. Needs TABLET_SERIAL; the FIFO and log live in UHID_DIR (default
$TMPDIR/omarchy/uhid).
"""
import json
import os
import subprocess
import sys
import time

DIR = os.path.expanduser(os.environ.get("UHID_DIR", os.path.join(os.environ.get("TMPDIR", "/tmp"), "omarchy/uhid")))
FIFO = os.path.join(DIR, "cmd.fifo")
LOG = os.path.join(DIR, "uhid.log")
ADB = os.path.expanduser("~/Android/Sdk/platform-tools/adb")
KBD, MOUSE = 1, 2

KBD_DESC = [0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7,
            0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
            0x95, 0x01, 0x75, 0x08, 0x81, 0x01,
            0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x65, 0x05, 0x07, 0x19, 0x00, 0x29, 0x65,
            0x81, 0x00, 0xC0]
MOUSE_DESC = [0x05, 0x01, 0x09, 0x02, 0xA1, 0x01, 0x09, 0x01, 0xA1, 0x00,
              0x05, 0x09, 0x19, 0x01, 0x29, 0x03, 0x15, 0x00, 0x25, 0x01, 0x95, 0x03, 0x75, 0x01,
              0x81, 0x02, 0x95, 0x01, 0x75, 0x05, 0x81, 0x01,
              0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x09, 0x38, 0x15, 0x81, 0x25, 0x7F, 0x75, 0x08,
              0x95, 0x03, 0x81, 0x06, 0xC0, 0xC0]

CHARS = {chr(ord('a') + i): 0x04 + i for i in range(26)}
CHARS.update({'1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22, '6': 0x23, '7': 0x24,
              '8': 0x25, '9': 0x26, '0': 0x27, '\n': 0x28, ' ': 0x2C, '-': 0x2D, '=': 0x2E,
              '[': 0x2F, ']': 0x30, ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36, '.': 0x37, '/': 0x38})
SHIFTED = {c.upper(): c for c in 'abcdefghijklmnopqrstuvwxyz'}
SHIFTED.update({'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8',
                '(': '9', ')': '0', '_': '-', '+': '=', '{': '[', '}': ']', ':': ';', '"': "'",
                '~': '`', '<': ',', '>': '.', '?': '/'})
NAMED = {'return': 0x28, 'enter': 0x28, 'esc': 0x29, 'escape': 0x29, 'backspace': 0x2A,
         'tab': 0x2B, 'space': 0x2C, 'up': 0x52, 'down': 0x51, 'left': 0x50, 'right': 0x4F,
         'q': 0x14, 'w': 0x1A}
MODS = {'ctrl': 0x01, 'shift': 0x02, 'alt': 0x04, 'gui': 0x08, 'super': 0x08, 'meta': 0x08}
BUTTONS = {'left': 1, 'right': 2, 'middle': 4}


def log(msg):
    with open(LOG, "a") as fh:
        fh.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))


def report(did, data):
    return {"id": did, "command": "report", "report": data}


def delay(ms, did=KBD):
    return {"id": did, "command": "delay", "duration": ms}


def kbd(mod, usage=0):
    return report(KBD, [mod, 0, usage, 0, 0, 0, 0, 0])


def tap(mod, usage):
    return [kbd(mod, 0), delay(20), kbd(mod, usage), delay(30), kbd(mod, 0), delay(20), kbd(0, 0), delay(20)]


def mouse(buttons, dx=0, dy=0, wheel=0):
    s8 = lambda v: max(-127, min(127, int(v))) & 0xFF
    return report(MOUSE, [buttons & 7, s8(dx), s8(dy), s8(wheel)])


def translate(line, state):
    words = line.split()
    if not words:
        return []
    cmd, args = words[0], words[1:]
    out = []
    if cmd == "type":
        text = line[len("type "):].encode().decode("unicode_escape")
        for ch in text:
            if ch in SHIFTED:
                out += tap(MODS['shift'], CHARS[SHIFTED[ch]])
            elif ch in CHARS:
                out += tap(0, CHARS[ch])
    elif cmd == "combo":
        mod = 0
        for m in args[:-1]:
            mod |= MODS[m]
        key = args[-1]
        usage = NAMED.get(key, CHARS.get(key, int(key, 0) if key.startswith("0x") else 0))
        out += tap(mod, usage)
    elif cmd == "key":
        key = args[0]
        out += tap(0, NAMED.get(key, CHARS.get(key, int(key, 0) if key.startswith("0x") else 0)))
    elif cmd == "move":
        dx, dy = int(args[0]), int(args[1])
        n = int(args[2]) if len(args) > 2 else 1
        for _ in range(n):
            out += [mouse(state["buttons"], dx, dy), delay(8, MOUSE)]
    elif cmd == "click":
        b = BUTTONS[args[0]]
        out += [mouse(state["buttons"] | b), delay(60, MOUSE), mouse(state["buttons"]), delay(30, MOUSE)]
    elif cmd == "press":
        state["buttons"] |= BUTTONS[args[0]]
        out += [mouse(state["buttons"]), delay(30, MOUSE)]
    elif cmd == "release":
        state["buttons"] = 0
        out += [mouse(0), delay(30, MOUSE)]
    elif cmd == "wheel":
        n = int(args[0])
        step = 1 if n > 0 else -1
        for _ in range(abs(n)):
            out += [mouse(state["buttons"], 0, 0, step), delay(40, MOUSE)]
    elif cmd == "sleep":
        out += [delay(int(float(args[0]) * 1000))]
    return out


def serve():
    serial = os.environ["TABLET_SERIAL"]
    os.makedirs(DIR, exist_ok=True)
    if not os.path.exists(FIFO):
        os.mkfifo(FIFO)
    proc = subprocess.Popen([ADB, "-s", serial, "shell", "-T", "hid", "-"], stdin=subprocess.PIPE,
                            stdout=open(os.path.join(DIR, "hid.out"), "ab"), stderr=subprocess.STDOUT)
    assert proc.stdin is not None
    stdin = proc.stdin

    def write(events):
        for e in events:
            stdin.write((json.dumps(e) + "\n").encode())
        stdin.flush()

    write([{"id": KBD, "command": "register", "name": "r8 dock keyboard", "vid": 0x18d1, "pid": 0x4ee1,
            "bus": "usb", "descriptor": KBD_DESC},
           {"id": MOUSE, "command": "register", "name": "r8 dock mouse", "vid": 0x18d1, "pid": 0x4ee2,
            "bus": "usb", "descriptor": MOUSE_DESC},
           delay(2500)])
    log("serve pid=%d hid pid=%d registered keyboard id %d and mouse id %d" % (os.getpid(), proc.pid, KBD, MOUSE))
    state = {"buttons": 0}
    while True:
        with open(FIFO) as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line == "quit":
                    write([mouse(0), kbd(0, 0), delay(200)])
                    stdin.close()
                    proc.wait(timeout=30)
                    log("quit: hid exited rc=%s, devices unregistered" % proc.returncode)
                    return
                try:
                    events = translate(line, state)
                    write(events)
                    log("sent %r (%d hid commands)" % (line, len(events)))
                except Exception as exc:  # a bad command must not kill the devices
                    log("bad command %r: %s" % (line, exc))
            if proc.poll() is not None:
                log("hid exited rc=%s" % proc.returncode)
                return


def send(line):
    if not os.path.exists(FIFO):
        sys.exit("uhid-dock: no server (run: uhid-dock.py serve)")
    for _ in range(50):  # the server reopens the FIFO after each writer: retry ENXIO briefly
        try:
            fd = os.open(FIFO, os.O_WRONLY | os.O_NONBLOCK)
            break
        except OSError:
            time.sleep(0.1)
    else:
        sys.exit("uhid-dock: server not reading %s" % FIFO)
    with os.fdopen(fd, "w") as fh:
        fh.write(line + "\n")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "serve":
        serve()
    elif len(sys.argv) >= 3 and sys.argv[1] == "send":
        send(" ".join(sys.argv[2:]))
    else:
        sys.exit(__doc__)
