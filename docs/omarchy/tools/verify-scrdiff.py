#!/usr/bin/env python3
"""verify-scrdiff.py <before.png> <after.png> [--crop out.png] [--clock x0,y0,x1,y1]

Exact screenshot difference for the forced-repaint check (r10-damage.md check 4). Two screenshots
of an unchanged desktop are bit-identical on the tablet, so every changed pixel after a forced
full repaint is either the bar clock turning over or a pixel the damage path left stale.

Prints one line:
  changed=N changed_gt8=N max_diff=N bbox=x0,y0,x1,y1 outside_clock=N bbox_outside=x0,y0,x1,y1 verdict=V
verdict is ZERO (identical), CLOCK_ONLY (every changed pixel lies inside the clock box) or
CHANGED (look at the crop). The default clock box is the mobile bar's left end (x 141-160,
y 29-58 on the 3200 px tablet, padded); pass --clock for the desktop bar. With --crop and any
change, writes before | after | diff of the bounding box (padded, up to 4x) so a reviewer can
look at it; with no change it writes nothing.
"""
import sys

import numpy as np
from PIL import Image


def box(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def fmt(b):
    return "none" if b is None else "%d,%d,%d,%d" % b


def main():
    args = sys.argv[1:]
    crop = None
    clock = (130, 20, 180, 70)
    pos = []
    i = 0
    while i < len(args):
        if args[i] == "--crop":
            crop = args[i + 1]
            i += 2
        elif args[i] == "--clock":
            clock = tuple(int(v) for v in args[i + 1].split(","))
            i += 2
        else:
            pos.append(args[i])
            i += 1
    if len(pos) != 2:
        print(__doc__)
        sys.exit(2)
    a = Image.open(pos[0]).convert("RGB")
    b = Image.open(pos[1]).convert("RGB")
    if a.size != b.size:
        print("size differs %s vs %s verdict=CHANGED" % (a.size, b.size))
        return
    na = np.asarray(a).astype(np.int16)
    nb = np.asarray(b).astype(np.int16)
    d = np.abs(na - nb).max(axis=2)
    ch = d > 0
    n = int(ch.sum())
    big = int((d > 8).sum())
    peak = int(d.max())
    bb = box(ch)
    inside = np.zeros_like(ch)
    x0, y0, x1, y1 = clock
    inside[y0:y1, x0:x1] = True
    outside = ch & ~inside
    n_out = int(outside.sum())
    bb_out = box(outside)
    verdict = "ZERO" if n == 0 else ("CLOCK_ONLY" if n_out == 0 else "CHANGED")
    print("changed=%d changed_gt8=%d max_diff=%d bbox=%s outside_clock=%d bbox_outside=%s verdict=%s"
          % (n, big, peak, fmt(bb), n_out, fmt(bb_out), verdict))
    if crop and bb is not None:
        pad = 80
        cx0, cy0 = max(bb[0] - pad, 0), max(bb[1] - pad, 0)
        cx1, cy1 = min(bb[2] + pad, a.size[0]), min(bb[3] + pad, a.size[1])
        box_ = (cx0, cy0, cx1, cy1)
        ca, cb = a.crop(box_), b.crop(box_)
        dm = Image.fromarray(np.where(ch[cy0:cy1, cx0:cx1, None], np.array([255, 0, 255], np.uint8),
                                      (np.asarray(ca) // 4).astype(np.uint8)).astype(np.uint8))
        w, h = ca.size
        scale = max(1, min(4, 2400 // (3 * w)))
        gap = 12
        sheet = Image.new("RGB", (3 * w * scale + 2 * gap, h * scale), (40, 40, 40))
        for k, im in enumerate((ca, cb, dm)):
            sheet.paste(im.resize((w * scale, h * scale), Image.Resampling.NEAREST), (k * (w * scale + gap), 0))
        sheet.save(crop)
        print("crop=%s box=%s scale=%d (before | after | diff in magenta)" % (crop, box_, scale))


if __name__ == "__main__":
    main()
