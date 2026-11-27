#!/usr/bin/env python3
"""verify-trace.py <ts-file> [--expect-ms 16.67] [--show N]

Reads a file written by verify-ts.py (`<epoch seconds> <line>`) and summarises the aquamarine
commit lines that AQ_TRACE=1 prints: `commit damage N rect(s)` (N=0: nothing changed),
`commit damage N rect(s) (whole surface)` (the old wire form) and the scheduleFrame lines.

Important limit, measured in R11: Hyprland's log is block-buffered (about 8 KB per flush, so one
flush every ~0.5 s at 60 commits/s), so the read time of a line is the FLUSH time, not the commit
time. The per-commit gap is therefore meaningless (median 0 ms, then a ~500 ms jump). What the
file does carry is the commit COUNT per flush and the time between flushes, so the script reports:

  rate        commits per second over the whole window (and per flush block: min / median / max)
  interval    per block, (time between this flush and the previous one) / (commits in the block):
              the mean commit-to-commit interval of that block, in ms
  excess_ms   per block, duration - commits * median_interval: the time the loop lost in that
              block. A stall of S ms inside a block shows up as excess_ms ~ S, so `blocks with
              excess >= 100` is the "no stall over 100 ms" check, to a resolution of one block.

The first and last blocks of a window are dropped (the tail starts and stops mid-block).
"""
import re
import sys

COMMIT = re.compile(r"commit damage (\d+) rect\(s\)( \(whole surface\))?")
SCHED = re.compile(r"scheduleFrame")
CLUSTER_S = 0.005


def median(v):
    s = sorted(v)
    return s[len(s) // 2] if s else 0.0


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
    sched = 0
    zero = rects = whole = 0
    max_rects = 0
    events = []
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
        if SCHED.search(ln):
            sched += 1
        m = COMMIT.search(ln)
        if not m:
            continue
        n = int(m.group(1))
        if m.group(2):
            whole += 1
        elif n == 0:
            zero += 1
        else:
            rects += 1
            max_rects = max(max_rects, n)
        events.append(t)
    for r in raw:
        print("  raw: " + r[:200])
    commits = len(events)
    if commits < 10:
        print("lines=%d commits=%d (too few) zero_rect=%d rects=%d whole=%d" % (lines, commits, zero, rects, whole))
        return
    blocks = []  # [t_first, count, t_last]: consecutive commit lines read within CLUSTER_S
    for t in events:
        if blocks and t - blocks[-1][2] <= CLUSTER_S:
            blocks[-1][1] += 1
            blocks[-1][2] = t
        else:
            blocks.append([t, 1, t])
    span = events[-1] - events[0]
    print("lines=%d commits=%d sched_lines=%d span=%.1fs rate=%.1f/s zero_rect=%d rects=%d whole_surface=%d max_rects=%d"
          % (lines, commits, sched, span, commits / span if span else 0.0, zero, rects, whole, max_rects))
    if len(blocks) < 5:
        print("flush blocks=%d (too few for a block analysis)" % len(blocks))
        return
    rows = []
    for k in range(1, len(blocks) - 1):
        rows.append(((blocks[k][0] - blocks[k - 1][0]) * 1000.0, blocks[k][1]))
    interval = [d / c for d, c in rows]
    med_iv = median(interval)
    excess = [d - c * med_iv for d, c in rows]
    rates = [c / (d / 1000.0) for d, c in rows]
    big100 = sum(1 for e in excess if e >= 100.0)
    big50 = sum(1 for e in excess if e >= 50.0)
    print("blocks=%d (of %d, first and last dropped) block_ms min/med/max=%.0f/%.0f/%.0f commits_per_block min/med/max=%d/%d/%d"
          % (len(rows), len(blocks), min(d for d, _ in rows), median([d for d, _ in rows]), max(d for d, _ in rows),
             min(c for _, c in rows), median([c for _, c in rows]), max(c for _, c in rows)))
    print("interval_ms per block min/med/max=%.2f/%.2f/%.2f%s  rate_per_s per block min/med/max=%.1f/%.1f/%.1f"
          % (min(interval), med_iv, max(interval), "" if expect is None else " (panel period %.2f ms)" % expect,
             min(rates), median(rates), max(rates)))
    print("excess_ms per block max=%.0f; blocks with excess >= 50 ms: %d, >= 100 ms: %d" % (max(excess), big50, big100))
    for k in sorted(range(len(excess)), key=lambda x: -excess[x])[:4]:
        if excess[k] >= 50.0:
            print("  block %d: %.0f ms for %d commits, excess %.0f ms" % (k, rows[k][0], rows[k][1], excess[k]))


if __name__ == "__main__":
    main()
