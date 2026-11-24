#!/usr/bin/env python3
"""pixdiff.py <before.png> <after.png> [--strip H]  -- how much did the screen change?

Prints: changed=<pixels> pct=<percent> bbox=<x0,y0,x1,y1> and, with --strip H, the same for the
top H rows (the bar strip) separately. Used to judge a bar tap without eyes: an opened popup or a
redrawn item changes pixels even when no new layer surface appears.
"""
import sys

from PIL import Image, ImageChops


def stats(before, after, box=None):
    if box:
        before, after = before.crop(box), after.crop(box)
    diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
    gray = diff.convert("L")
    bbox = gray.getbbox()
    changed = sum(1 for p in gray.getdata() if p)
    total = before.size[0] * before.size[1]
    return changed, 100.0 * changed / total, bbox


def main():
    a = Image.open(sys.argv[1])
    b = Image.open(sys.argv[2])
    strip = None
    if "--strip" in sys.argv:
        strip = int(sys.argv[sys.argv.index("--strip") + 1])
    if a.size != b.size:
        print("SIZE MISMATCH %s vs %s" % (a.size, b.size))
        return
    c, p, bb = stats(a, b)
    print("changed=%d pct=%.3f bbox=%s" % (c, p, bb))
    if strip:
        c2, p2, bb2 = stats(a, b, (0, 0, a.size[0], strip))
        print("bar-strip(%dpx): changed=%d pct=%.3f bbox=%s" % (strip, c2, p2, bb2))


if __name__ == "__main__":
    main()
