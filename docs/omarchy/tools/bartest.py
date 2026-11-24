#!/usr/bin/env python3
"""bartest.py <kind> [y]  -- tap the nine R4 bar targets and print one CSV line per target.

kind: touch       adb shell input touchscreen tap X Y
      longtouch  adb shell input touchscreen swipe X Y X Y 150   (a held finger)
      mouse      adb shell input mouse tap X Y
      slowdrag   adb shell input touchscreen swipe X Y X Y+? ... (not used here)

Each row records what changed across the tap: the active workspace id, the layer namespaces
(and how many), the client count, the active window class/title, and the X cursor position.
Between targets it returns to workspace 1 with `hl.dsp.focus({ workspace = "1" })`, so a
workspace tap has something to move away from.

Requires TABLET_SERIAL in the environment, and a live session (hc.sh). Prints:

  target,x,y,ws_before,ws_after,layers_after_new,clients_before,clients_after,win_after,cursor_before,cursor_after

`layers_after_new` is the layer namespaces that appeared (comma joined, "-" when none), and
`win_after` is the class:title of the active window after the tap. A row that ends with
ws_after != ws_before, or a non "-" layers_after_new, reacted.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
THE = os.environ.get("TABLET_SERIAL")
if not THE:
    sys.exit("bartest.py: set TABLET_SERIAL")

SNAP_REQS = ["j/activeworkspace", "j/layers", "j/clients", "j/activewindow", "j/cursorpos"]

TARGETS = [
    ("omarchy", 45),
    ("ws1", 87),
    ("ws2", 128),
    ("ws3", 170),
    ("ws4", 211),
    ("ws5", 253),
    ("net", 3052),
    ("vol", 3105),
    ("disp", 3160),
]


def hc(reqs):
    """Run hc.sh with the given requests, return the raw text."""
    env = {k: v for k, v in os.environ.items()}
    env["TABLET_SERIAL"] = THE or ""
    return subprocess.run(
        [os.path.join(HERE, "hc.sh")] + reqs,
        capture_output=True, text=True, timeout=180, env=env,
    ).stdout


def sections(text):
    """Split hc.sh output into {request: body} on the '## <req>' markers."""
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


def snap(reset=False):
    reqs = (["/dispatch hl.dsp.focus({ workspace = \"1\" })"] if reset else []) + SNAP_REQS
    sec = sections(hc(reqs))
    d = {}
    try:
        d["ws"] = json.loads(sec["j/activeworkspace"]).get("id")
    except Exception:
        d["ws"] = "?"
    layers = []
    try:
        for level, items in json.loads(sec["j/layers"]).get("levels", {}).items():
            for it in items:
                layers.append(it.get("namespace", "?"))
    except Exception:
        pass
    d["layers"] = layers
    try:
        d["clients"] = len(json.loads(sec["j/clients"]))
    except Exception:
        d["clients"] = "?"
    try:
        w = json.loads(sec["j/activewindow"])
        d["win"] = "%s:%s" % (w.get("class", "?"), (w.get("title") or "")[:24])
    except Exception:
        d["win"] = "?"
    try:
        c = json.loads(sec["j/cursorpos"])
        d["cursor"] = "%s,%s" % (c.get("x"), c.get("y"))
    except Exception:
        d["cursor"] = "?,?"
    return d


def tap(kind, x, y):
    if kind == "touch":
        cmd = ["adb", "-s", THE, "shell", "input", "touchscreen", "tap", str(x), str(y)]
    elif kind == "longtouch":
        cmd = ["adb", "-s", THE, "shell", "input", "touchscreen", "swipe",
               str(x), str(y), str(x), str(y), "150"]
    elif kind == "slowdrag":
        cmd = ["adb", "-s", THE, "shell", "input", "touchscreen", "swipe",
               str(x), str(y), str(x + 40), str(y), "1200"]
    elif kind == "mouse":
        cmd = ["adb", "-s", THE, "shell", "input", "mouse", "tap", str(x), str(y)]
    else:
        sys.exit("bartest.py: unknown kind %r" % kind)
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "touch"
    y = int(sys.argv[2]) if len(sys.argv) > 2 else 26
    only = sys.argv[3] if len(sys.argv) > 3 else None
    sleep_s = float(os.environ.get("BARTEST_SETTLE", "0.9"))
    print("target,x,y,ws_before,ws_after,layers_after_new,clients_before,clients_after,win_after,cursor_before,cursor_after")
    for name, x in TARGETS:
        if only and name != only:
            continue
        before = snap(reset=True)
        tap(kind, x, y)
        time.sleep(sleep_s)
        after = snap(reset=False)
        new = [n for n in after["layers"] if n not in before["layers"]] or ["-"]
        print(",".join(str(v) for v in (
            name, x, y, before["ws"], after["ws"], "|".join(new),
            before["clients"], after["clients"], after["win"],
            before["cursor"], after["cursor"],
        )))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
