#!/usr/bin/env python3
"""verify-xcorrupt.py [x y w h]

Runs INSIDE the guest (`DISPLAY=:0 python3 verify-xcorrupt.py 1400 900 400 250`). Paints a solid
rectangle straight into the X window of the nested compositor (cage's output window, the largest
top-level window of the Xlorie display) with core X drawing, bypassing Hyprland and cage. Nothing in
the compositor chain knows the pixels changed, so they stay on screen exactly like a stale remnant
would: a damage path that under-reports leaves them alone, and only a repaint that really covers
that area removes them.

That makes it the POSITIVE CONTROL of the forced-repaint method (r10-damage.md check 4):
  1. screenshot S0 (clean), paint, screenshot S1: S1 must differ from S0 (the instrument sees a remnant);
  2. a step that claims to repaint everything: screenshot S2: S2 must equal S0 (clock box excluded),
     i.e. the step really reached the whole output. A step that leaves S2 == S1 repaints nothing.
Default rectangle: 400x250 at (1400, 900), magenta, well clear of the bar and the dock.
"""
import ctypes
import sys

# mode: "paint" (default, the original call shape), "read" (read the rect back from the window) or
# "paint-read" (paint, then read it back through the same connection, a few ms later). The read-back proves
# WHERE the paint landed: in the window cage composites. With AQ_WAYLAND_FULL_DAMAGE=1 every commit sends the
# whole surface, so the next frame repairs the paint before any screenshot can catch it; the read-back is then
# the only way to show that the draw itself worked and the screen simply repainted over it.
argv = sys.argv[1:]
mode = "paint"
if argv and argv[0] in ("read", "paint", "paint-read"):
    mode = argv.pop(0)
x, y, w, h = (int(v) for v in argv[:4]) if len(argv) >= 4 else (1400, 900, 400, 250)

x11 = ctypes.CDLL("libX11.so.6")
Window = ctypes.c_ulong
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = Window
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XQueryTree.argtypes = [
    ctypes.c_void_p, Window, ctypes.POINTER(Window), ctypes.POINTER(Window),
    ctypes.POINTER(ctypes.POINTER(Window)), ctypes.POINTER(ctypes.c_uint),
]
x11.XGetGeometry.argtypes = [
    ctypes.c_void_p, Window, ctypes.POINTER(Window), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
]
x11.XCreateGC.restype = ctypes.c_void_p
x11.XCreateGC.argtypes = [ctypes.c_void_p, Window, ctypes.c_ulong, ctypes.c_void_p]
x11.XSetForeground.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
x11.XFillRectangle.argtypes = [ctypes.c_void_p, Window, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
x11.XFree.argtypes = [ctypes.c_void_p]
x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

dpy = x11.XOpenDisplay(b":0")
if not dpy:
    print("verify-xcorrupt: cannot open :0")
    sys.exit(1)
root = x11.XDefaultRootWindow(dpy)
r, p = Window(), Window()
kids = ctypes.POINTER(Window)()
n = ctypes.c_uint()
x11.XQueryTree(dpy, root, ctypes.byref(r), ctypes.byref(p), ctypes.byref(kids), ctypes.byref(n))
best, best_area, best_geom = None, 0, None
for i in range(n.value):
    win = kids[i]
    rr = Window()
    gx_, gy_ = ctypes.c_int(), ctypes.c_int()
    gw, gh, bw, dp = ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint()
    if x11.XGetGeometry(dpy, win, ctypes.byref(rr), ctypes.byref(gx_), ctypes.byref(gy_), ctypes.byref(gw),
                        ctypes.byref(gh), ctypes.byref(bw), ctypes.byref(dp)):
        if gw.value * gh.value > best_area:
            best, best_area, best_geom = win, gw.value * gh.value, (gx_.value, gy_.value, gw.value, gh.value)
if best is None:
    print("verify-xcorrupt: no top-level window under the root")
    sys.exit(2)
def read_back():
    """Print what the window's pixels hold in the rect right now (XGetImage, no compositor involved)."""
    x11.XGetImage.restype = ctypes.c_void_p
    x11.XGetImage.argtypes = [ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
                              ctypes.c_ulong, ctypes.c_int]
    class XImage(ctypes.Structure):
        _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int), ("xoffset", ctypes.c_int),
                    ("format", ctypes.c_int), ("data", ctypes.c_void_p), ("byte_order", ctypes.c_int),
                    ("bitmap_unit", ctypes.c_int), ("bitmap_bit_order", ctypes.c_int),
                    ("bitmap_pad", ctypes.c_int), ("depth", ctypes.c_int),
                    ("bytes_per_line", ctypes.c_int), ("bits_per_pixel", ctypes.c_int)]
    img = x11.XGetImage(dpy, best, x, y, w, h, 0xFFFFFFFF, 2)
    if not img:
        print("verify-xcorrupt: XGetImage failed")
        return None
    im = ctypes.cast(img, ctypes.POINTER(XImage)).contents
    if im.bits_per_pixel != 32:
        print("verify-xcorrupt: read-back needs 32-bit pixels, got %d" % im.bits_per_pixel)
        return None
    buf = (ctypes.c_ubyte * (im.bytes_per_line * h)).from_address(im.data)
    cnt, common = {}, (0, 0, 0)
    for j in range(h):
        row = j * im.bytes_per_line
        for i in range(w):
            o = row + i * 4
            px = (buf[o + 2], buf[o + 1], buf[o])
            cnt[px] = cnt.get(px, 0) + 1
    common = max(cnt.items(), key=lambda kv: kv[1])
    cx, cy = w // 2, h // 2
    o = cy * im.bytes_per_line + cx * 4
    centre = (buf[o + 2], buf[o + 1], buf[o])
    x11.XDestroyImage = getattr(x11, "XDestroyImage", None)
    print("verify-xcorrupt: read-back of %dx%d at %d,%d from window 0x%x: centre=%s, magenta %d of %d px, "
          "most common %s (%d px)" % (w, h, x, y, best, centre, cnt.get((255, 0, 255), 0), w * h, common[0], common[1]))
    return centre

if mode in ("paint", "paint-read"):
    gc = x11.XCreateGC(dpy, best, 0, None)
    x11.XSetForeground(dpy, gc, 0xFF00FF)
    x11.XFillRectangle(dpy, best, gc, x, y, w, h)
    x11.XFlush(dpy)
    x11.XSync(dpy, 0)
    print("verify-xcorrupt: painted %dx%d at %d,%d into window 0x%x (geometry %s, %d top-level windows)" % (w, h, x, y, best, best_geom, n.value))
if mode in ("read", "paint-read"):
    read_back()
x11.XCloseDisplay(dpy)
