#!/usr/bin/env python3
"""verify-mkuinput.py out.json [options] ACTION...

Writes a command stream for Android's `uinput` tool that registers a multi-touch screen (type-B
slots, INPUT_PROP_DIRECT) and plays taps and N-finger gestures. Companion of the skill's
mkuinput-touch.py, extended to pinch and three-finger moves (that one stops at two fingers).

    python3 verify-mkuinput.py out.json --steps 30 move 1500 1000 1100 1000  1700 1000 2100 1000
    adb push out.json /data/local/tmp/ && adb shell uinput /data/local/tmp/out.json

Actions (SCREEN pixels in the current orientation, played in order):
    tap SX SY
    move X0 Y0 X1 Y1 [X0 Y0 X1 Y1 ...]   one finger per start/end pair, all moving together in
                                          straight lines (2 pairs = pinch or two-finger drag,
                                          3 pairs = three-finger swipe)
    wait MS
Options:
    --natural WxH   the panel in its NATURAL orientation (default 2136x3200, the reference tablet)
    --map landscape|natural   screen->raw mapping (default landscape: raw = (W-1-sy, sx))
    --steps N       motion steps per move (default 20)      --ms N   delay between steps (default 16)

The device registers 2.5 s before the first event (shorter waits lose events) and is removed at
EOF. Calibrate the mapping with one `tap` against touchlog before trusting a move.
"""
import json
import sys


def parse(argv):
    opts = {"natural": "2136x3200", "map": "landscape", "steps": 20, "ms": 16}
    acts = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if key not in opts or i + 1 >= len(argv):
                sys.exit("verify-mkuinput.py: bad option " + a)
            opts[key] = int(argv[i + 1]) if key in ("steps", "ms") else argv[i + 1]
            i += 2
            continue
        if a == "tap":
            acts.append(("tap", [int(v) for v in argv[i + 1:i + 3]]))
            i += 3
        elif a == "wait":
            acts.append(("wait", [int(argv[i + 1])]))
            i += 2
        elif a == "move":
            j = i + 1
            vals = []
            while j < len(argv) and not argv[j].startswith("--") and argv[j].lstrip("-").isdigit():
                vals.append(int(argv[j]))
                j += 1
            if not vals or len(vals) % 4:
                sys.exit("verify-mkuinput.py: move needs groups of four numbers")
            acts.append(("move", vals))
            i = j
        else:
            sys.exit("verify-mkuinput.py: unknown action " + a)
    return opts, acts


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    out = sys.argv[1]
    opts, acts = parse(sys.argv[2:])
    W, H = (int(v) for v in opts["natural"].split("x"))
    landscape = opts["map"] == "landscape"

    def raw(sx, sy):
        return (W - 1 - sy, sx) if landscape else (sx, sy)

    cmds = []

    def add(obj):
        cmds.append(json.dumps(obj))

    def absinfo(code, top):
        return {"code": code, "info": {"value": 0, "minimum": 0, "maximum": top,
                                       "fuzz": 0, "flat": 0, "resolution": 0}}

    add({"id": 1, "command": "register", "name": "Test Touchscreen", "vid": 0x18d1, "pid": 0x4ee2,
         "bus": "usb",
         "configuration": [
             {"type": "UI_SET_EVBIT", "data": ["EV_KEY", "EV_ABS"]},
             {"type": "UI_SET_KEYBIT", "data": ["BTN_TOUCH"]},
             {"type": "UI_SET_ABSBIT", "data": ["ABS_X", "ABS_Y", "ABS_MT_SLOT", "ABS_MT_TRACKING_ID",
                                                "ABS_MT_POSITION_X", "ABS_MT_POSITION_Y"]},
             {"type": "UI_SET_PROPBIT", "data": ["INPUT_PROP_DIRECT"]}],
         "abs_info": [absinfo("ABS_X", W - 1), absinfo("ABS_Y", H - 1), absinfo("ABS_MT_SLOT", 9),
                      absinfo("ABS_MT_TRACKING_ID", 65535), absinfo("ABS_MT_POSITION_X", W - 1),
                      absinfo("ABS_MT_POSITION_Y", H - 1)]})
    add({"id": 1, "command": "delay", "duration": 2500})

    def inject(events):
        add({"id": 1, "command": "inject", "events": events})

    def delay(ms):
        add({"id": 1, "command": "delay", "duration": ms})

    syn = ["EV_SYN", "SYN_REPORT", 0]
    next_id = [1]

    def contact(points, first):
        ev = []
        for slot, (sx, sy) in enumerate(points):
            x, y = raw(sx, sy)
            ev += ["EV_ABS", "ABS_MT_SLOT", slot]
            if first:
                ev += ["EV_ABS", "ABS_MT_TRACKING_ID", next_id[0] + slot]
            ev += ["EV_ABS", "ABS_MT_POSITION_X", x, "EV_ABS", "ABS_MT_POSITION_Y", y]
        if first:
            ev += ["EV_KEY", "BTN_TOUCH", 1]
        x0, y0 = raw(*points[0])
        inject(ev + ["EV_ABS", "ABS_X", x0, "EV_ABS", "ABS_Y", y0] + syn)

    def lift(n):
        ev = []
        for slot in range(n):
            ev += ["EV_ABS", "ABS_MT_SLOT", slot, "EV_ABS", "ABS_MT_TRACKING_ID", -1]
        inject(ev + ["EV_KEY", "BTN_TOUCH", 0] + syn)
        next_id[0] += n

    def gesture(starts, ends, steps):
        contact(starts, True)
        delay(opts["ms"])
        for i in range(1, steps + 1):
            contact([(s[0] + (e[0] - s[0]) * i // steps, s[1] + (e[1] - s[1]) * i // steps)
                     for s, e in zip(starts, ends)], False)
            delay(opts["ms"])
        lift(len(starts))
        delay(500)

    for name, v in acts:
        if name == "tap":
            gesture([(v[0], v[1])], [(v[0], v[1])], 1)
        elif name == "move":
            starts = [(v[k], v[k + 1]) for k in range(0, len(v), 4)]
            ends = [(v[k + 2], v[k + 3]) for k in range(0, len(v), 4)]
            gesture(starts, ends, opts["steps"])
        elif name == "wait":
            delay(v[0])
    delay(500)
    with open(out, "w") as fh:
        fh.write("\n".join(cmds) + "\n")
    print("%s: %d commands, %d gesture(s)" % (out, len(cmds), sum(1 for n, _ in acts if n != "wait")))


if __name__ == "__main__":
    main()
