#!/usr/bin/env python3
"""verify-ts.py -- prefix every stdin line with the wall-clock time it was read (seconds, 4 decimals).

Runs INSIDE the guest: `tail -n0 -F <hyprland.log> | python3 verify-ts.py > /tmp/ts.txt`. The
timestamp is the read time, so it is only as exact as the writer's flush; verify-trace.py reports
the line count and the interval spread so a block-buffered log is visible as such.
"""
import sys
import time

out = sys.stdout
for line in sys.stdin.buffer:
    out.write("%.4f %s" % (time.time(), line.decode("utf-8", "replace")))
    out.flush()
