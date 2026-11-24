#!/usr/bin/env python3
"""focustest.py <touch|mouse>  -- the R4 control test: tap the unfocused window, does focus move?

Opens two `foot` windows if fewer than two clients exist, then taps the centre of the client that
is NOT focused and prints:

  clients=<n> active_before=<addr|class> tap=<x,y screen> active_after=<...> focus_moved=yes|no

Screen coordinates: the Hyprland monitor is 3200x1970 at scale 2, so a client's logical `at`/`size`
multiply by 2 to give screen pixels. Prints the cursor position before and after as well, so a mode
with no click but with pointer motion is distinguishable from no input at all.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
THE = os.environ.get("TABLET_SERIAL") or sys.exit("focustest.py: set TABLET_SERIAL")
SCALE = 2


def hc(*reqs):
    env = dict(os.environ)
    env["TABLET_SERIAL"] = THE
    return subprocess.run([os.path.join(HERE, "hc.sh")] + list(reqs),
                          capture_output=True, text=True, timeout=180, env=env).stdout


def sections(text):
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur, buf = line[3:].strip(), []
        elif line.startswith("# control socket:"):
            continue
        else:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def state():
    sec = sections(hc("j/clients", "j/activewindow", "j/cursorpos"))
    clients = json.loads(sec["j/clients"])
    active = json.loads(sec["j/activewindow"])
    cur = json.loads(sec["j/cursorpos"])
    return clients, active, cur


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "mouse"
    clients, active, cur0 = state()
    opened = 0
    while len(clients) < 2 and opened < 4:
        hc('/dispatch hl.dsp.exec_cmd("foot")')
        opened += 1
        time.sleep(2.5)
        clients, active, _ = state()
    if len(clients) < 2:
        sys.exit("focustest.py: only %d client(s) after opening foot %d times" % (len(clients), opened))
    time.sleep(2.0)
    clients, active, cur0 = state()
    active_addr = active.get("address")
    other = None
    for c in clients:
        if c.get("address") != active_addr and c.get("mapped", True) and not c.get("hidden", False):
            other = c
            break
    if not other:
        sys.exit("focustest.py: no second visible client")
    at = other.get("at") or [0, 0]
    size = other.get("size") or [100, 100]
    x = int((at[0] + size[0] / 2.0) * SCALE)
    y = int((at[1] + size[1] / 2.0) * SCALE)
    if kind == "touch":
        cmd = ["adb", "-s", THE, "shell", "input", "touchscreen", "tap", str(x), str(y)]
    elif kind == "mouse":
        cmd = ["adb", "-s", THE, "shell", "input", "mouse", "tap", str(x), str(y)]
    elif kind == "longtouch":
        cmd = ["adb", "-s", THE, "shell", "input", "touchscreen", "swipe",
               str(x), str(y), str(x), str(y), "150"]
    else:
        sys.exit("focustest.py: unknown kind %r" % kind)
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    time.sleep(1.0)
    _, active2, cur1 = state()
    print("clients=%d active_before=%s:%s tap=%s,%s active_after=%s:%s focus_moved=%s cursor=%s,%s -> %s,%s"
          % (len(clients), active.get("class"), active_addr, x, y,
             active2.get("class"), active2.get("address"),
             "yes" if active2.get("address") != active_addr else "no",
             cur0.get("x"), cur0.get("y"), cur1.get("x"), cur1.get("y")))
    for c in clients:
        print("  client %s class=%s at=%s size=%s workspace=%s" % (
            c.get("address"), c.get("class"), c.get("at"), c.get("size"),
            (c.get("workspace") or {}).get("id")))


if __name__ == "__main__":
    main()
