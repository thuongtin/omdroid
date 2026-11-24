#!/usr/bin/env python3
"""xtap.py <x> <y> [button]  -- inject a real X pointer click at root coordinates, from inside
the guest (XTest). Used as the R4 control: it proves whether the guest chain
(Xlorie -> cage -> Hyprland -> Quickshell) delivers a button press to the Omarchy bar at a point,
independently of how the host delivers its input.

X root pixels, origin top-left. Prints the pointer position X reports after the move, so a caller
can tell a motion from a click.
"""
import ctypes
import sys
import time

x11 = ctypes.CDLL("libX11.so.6")
xtst = ctypes.CDLL("libXtst.so.6")

x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
x11.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                              ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                              ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
                              ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
                              ctypes.POINTER(ctypes.c_uint)]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_ulong]
xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int,
                                      ctypes.c_ulong]


def pointer(dpy):
    root = x11.XDefaultRootWindow(dpy)
    rr = ctypes.c_ulong()
    cr = ctypes.c_ulong()
    rx, ry = ctypes.c_int(), ctypes.c_int()
    wx, wy = ctypes.c_int(), ctypes.c_int()
    mask = ctypes.c_uint()
    x11.XQueryPointer(dpy, root, ctypes.byref(rr), ctypes.byref(cr),
                      ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(wx), ctypes.byref(wy),
                      ctypes.byref(mask))
    return rx.value, ry.value


def main():
    x, y = int(sys.argv[1]), int(sys.argv[2])
    button = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        sys.exit("xtap.py: cannot open DISPLAY")
    print("pointer before:", pointer(dpy))
    xtst.XTestFakeMotionEvent(dpy, 0, x, y, 0)
    x11.XSync(dpy, 0)
    time.sleep(0.15)
    print("pointer after move:", pointer(dpy))
    xtst.XTestFakeButtonEvent(dpy, button, 1, 0)
    x11.XFlush(dpy)
    time.sleep(0.06)
    xtst.XTestFakeButtonEvent(dpy, button, 0, 0)
    x11.XFlush(dpy)
    time.sleep(0.2)
    print("pointer after click:", pointer(dpy))


if __name__ == "__main__":
    main()
