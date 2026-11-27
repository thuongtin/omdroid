#!/usr/bin/env python3
"""verify-trace.py <ts-file> [--expect-ms 8.33] [--show N]

Reads a file written by verify-ts.py (`<epoch seconds> <line>`) and summarises the aquamarine
commit lines that AQ_TRACE=1 prints (`commit damage N rect(s)` or `commit damage (whole surface)`):

  lines=<all lines> commits=<commit lines> span=<s> rate=<per s>
  zero_rect=<n> rects=<n with N>0> whole=<n> max_rects=<N>
  gap_ms mean/median/p95/max, gaps>100ms=<n>, histogram of the commit-to-commit interval

A buffered log shows up as many commits sharing one timestamp (median gap near 0) with a few big
gaps; say so rather than reading it as a rhythm. --show N prints the first N raw lines (format).
"""
import re
import sys

COMMIT = re.compile(r"commit damage (?:(\d+) rect|\(whole surface\))")
BINS = [(0, 1), (1, 6), (6, 10), (10, 14), (14, 20), (20, 50), (50, 100), (100, 1e9)]


def main():
    args = sys.argv[1:]
    show = 0
    expect = None
    pos = []
    i = 0
    while i < len(args):
        if args[i] == "--show":
            show = int(args[i + 1])
            i += 2
        elif args[i] == "--expect-ms":
            expect = float(args[i + 1])
            i += 2
        else:
            pos.append(args[i])
            i += 1
    if len(pos) != 1:
        print(__doc__)
        sys.exit(2)
    lines = 0
    times = []
    zero = rects = whole = 0
    max_rects = 0
    raw = []
    for ln in open(pos[0], encoding="utf-8", errors="replace"):
        lines += 1
        if len(raw) < show:
            raw.append(ln.rstrip("\n"))
        sp = ln.find(" ")
        try:
            t = float(ln[:sp])
        except ValueError:
            continue
        m = COMMIT.search(ln)
        if not m:
            continue
        times.append(t)
        if m.group(1) is None:
            whole += 1
        elif int(m.group(1)) == 0:
            zero += 1
        else:
            rects += 1
            max_rects = max(max_rects, int(m.group(1)))
    for r in raw:
        print("  raw: " + r[:200])
    n = len(times)
    if n < 2:
        print("lines=%d commits=%d (too few for a rhythm) zero_rect=%d rects=%d whole=%d" % (lines, n, zero, rects, whole))
        return
    span = times[-1] - times[0]
    gaps = sorted((b - a) * 1000.0 for a, b in zip(times, times[1:]))
    gaps_raw = [(b - a) * 1000.0 for a, b in zip(times, times[1:])]
    mean = sum(gaps) / len(gaps)
    med = gaps[len(gaps) // 2]
    p95 = gaps[int(len(gaps) * 0.95)]
    big = sum(1 for g in gaps if g > 100.0)
    hist = []
    for lo, hi in BINS:
        c = sum(1 for g in gaps if lo <= g < hi)
        label = ">=100" if hi >= 1e9 else "%g-%g" % (lo, hi)
        hist.append("%s:%d" % (label, c))
    print("lines=%d commits=%d span=%.1fs rate=%.1f/s zero_rect=%d rects=%d whole=%d max_rects=%d"
          % (lines, n, span, n / span if span else 0, zero, rects, whole, max_rects))
    print("gap_ms mean=%.1f median=%.1f p95=%.1f max=%.1f gaps>100ms=%d%s"
          % (mean, med, p95, gaps[-1], big, "" if expect is None else " (expect %.2f ms)" % expect))
    print("hist " + " ".join(hist))
    if big:
        worst = [k for k in sorted(range(len(gaps_raw)), key=lambda k: -gaps_raw[k])[:5] if gaps_raw[k] > 100.0]
        for k in sorted(worst):
            print("  gap %.0f ms between t=%.3f and t=%.3f (commit #%d)" % (gaps_raw[k], times[k], times[k + 1], k))


if __name__ == "__main__":
    main()
