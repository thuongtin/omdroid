#!/usr/bin/env python3
"""verify-wl.py <wayland-debug.log> [--stalls verify-stalls.txt]

Reads the stderr of a client started with WAYLAND_DEBUG=1 (foot flooding its terminal) and reports
the cadence of `wl_callback#N.done` events: those are Hyprland's frame-done answers to that
client, one per output frame the client asked for, so their spacing is the compositor's frame
loop as the client sees it. The line prefix `[ 123456.789]` is the CLIENT clock in ms with a
microsecond fraction and the log is written unbuffered, so (unlike the block-buffered Hyprland
trace log) the spacing is real time.

Prints: done count, rate, gap_ms min / median / p95 / max, a histogram, the number of gaps over
50 / 100 / 190 / 390 ms, and the five largest gaps with their position. With --stalls (the control
file the phase writes, `<epoch> STOP <ms>` lines) it also says how many stalls were injected, so
the reader can check that many gaps of about that length exist.
"""
import re
import sys

DONE = re.compile(r"^\s*\[\s*([\d.]+)\]\s+wl_callback#\d+\.done\(")
BINS = [(0, 5), (5, 14), (14, 20), (20, 30), (30, 50), (50, 100), (100, 190), (190, 390), (390, 1e9)]


def main():
    args = sys.argv[1:]
    stalls = None
    pos = []
    i = 0
    while i < len(args):
        if args[i] == "--stalls":
            stalls = args[i + 1]
            i += 2
        else:
            pos.append(args[i])
            i += 1
    if len(pos) != 1:
        print(__doc__)
        sys.exit(2)
    times = []
    lines = 0
    for ln in open(pos[0], encoding="utf-8", errors="replace"):
        lines += 1
        m = DONE.match(ln)
        if m:
            times.append(float(m.group(1)))
    n = len(times)
    if n < 10:
        print("lines=%d wl_callback.done=%d (too few)" % (lines, n))
        return
    gaps = [b - a for a, b in zip(times, times[1:])]
    sg = sorted(gaps)
    span = (times[-1] - times[0]) / 1000.0
    hist = []
    for lo, hi in BINS:
        c = sum(1 for g in gaps if lo <= g < hi)
        hist.append("%s:%d" % (">=390" if hi >= 1e9 else "%g-%g" % (lo, hi), c))
    print("lines=%d done=%d span=%.1fs rate=%.1f/s" % (lines, n, span, n / span if span else 0.0))
    print("gap_ms min=%.1f median=%.1f p95=%.1f max=%.1f  >50ms:%d >100ms:%d >=190ms:%d >=390ms:%d"
          % (sg[0], sg[len(sg) // 2], sg[int(len(sg) * 0.95)], sg[-1],
             sum(g > 50 for g in gaps), sum(g > 100 for g in gaps), sum(g >= 190 for g in gaps), sum(g >= 390 for g in gaps)))
    print("hist " + " ".join(hist))
    for k in sorted(range(len(gaps)), key=lambda x: -gaps[x])[:5]:
        if gaps[k] > 50:
            print("  gap %.0f ms at t=%.3f s (done #%d)" % (gaps[k], (times[k] - times[0]) / 1000.0, k))
    if stalls:
        try:
            inj = [ln.split() for ln in open(stalls) if " STOP " in ln]
        except OSError:
            inj = []
        print("injected stalls: %s" % (", ".join("%s ms" % x[2] for x in inj) or "none"))


if __name__ == "__main__":
    main()
