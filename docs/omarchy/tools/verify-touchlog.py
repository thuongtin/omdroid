#!/usr/bin/env python3
"""verify-touchlog.py <touchlog.out>

Summarises the output of touchlog (docs/omarchy/tools/touchlog.c): per touch id the first and last
surface-local position, how many motion events it carried, how many ids were down AT ONCE (the
number of fingers a client really saw), and whether any `cancel` arrived (the compositor took the
gesture back). Pointer events are counted too, so a gesture that leaked into the pointer path shows.
"""
import re
import sys

EV = re.compile(r"^\s*([\d.]+) touch (down|motion|up) id=(-?\d+)(?: x=([-\d.]+) y=([-\d.]+))?")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    ids = {}
    down = set()
    peak = 0
    cancels = 0
    pointer = 0
    frames = 0
    seat = ""
    for ln in open(sys.argv[1], encoding="utf-8", errors="replace"):
        if "seat caps" in ln:
            seat = ln.strip()
        if "touch cancel" in ln:
            cancels += 1
        if "touch frame" in ln:
            frames += 1
        if re.search(r"\bpointer\b", ln) and "seat caps" not in ln:
            pointer += 1
        m = EV.match(ln)
        if not m:
            continue
        t, kind, tid = float(m.group(1)), m.group(2), int(m.group(3))
        rec = ids.setdefault(tid, {"first": None, "last": None, "motion": 0, "down_t": None, "up_t": None})
        if m.group(4) is not None:
            pos = (float(m.group(4)), float(m.group(5)))
            if rec["first"] is None:
                rec["first"] = pos
            rec["last"] = pos
        if kind == "down":
            down.add(tid)
            rec["down_t"] = t
            peak = max(peak, len(down))
        elif kind == "motion":
            rec["motion"] += 1
        else:
            down.discard(tid)
            rec["up_t"] = t
    print(seat or "(no seat line)")
    for tid in sorted(ids):
        r = ids[tid]
        print("id=%d first=%s last=%s motion_events=%d down_t=%s up_t=%s" % (tid, r["first"], r["last"], r["motion"], r["down_t"], r["up_t"]))
    print("distinct_ids=%d max_simultaneous=%d cancels=%d frames=%d pointer_lines=%d" % (len(ids), peak, cancels, frames, pointer))


if __name__ == "__main__":
    main()
