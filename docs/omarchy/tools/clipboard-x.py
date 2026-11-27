#!/usr/bin/env python3
"""Read or write the X CLIPBOARD selection on the display Termux:X11 serves.

A probe for the clipboard bridge, in the guest:

  clipboard-x.py read             owner id and the text, or owner=0x0
  clipboard-x.py write TEXT [SEC] take CLIPBOARD with TEXT and answer requests for
                                  SEC seconds (default 6), then exit

`write` stands in for Xlorie: when Android copies, Xlorie takes the selection and
answers conversions, and a client that does the same drives the bridge's
X-to-Wayland half.
"""
import ctypes
import os
import select
import sys
import time

x11 = ctypes.CDLL("libX11.so.6")
Window = ctypes.c_ulong
Atom = ctypes.c_ulong
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = Window
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XCreateSimpleWindow.restype = Window
x11.XCreateSimpleWindow.argtypes = [ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                                    ctypes.c_ulong, ctypes.c_ulong]
x11.XInternAtom.restype = Atom
x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
x11.XSetSelectionOwner.argtypes = [ctypes.c_void_p, Atom, Window, ctypes.c_ulong]
x11.XGetSelectionOwner.restype = Window
x11.XGetSelectionOwner.argtypes = [ctypes.c_void_p, Atom]
x11.XConvertSelection.argtypes = [ctypes.c_void_p, Atom, Atom, Atom, Window, ctypes.c_ulong]
x11.XGetWindowProperty.argtypes = [ctypes.c_void_p, Window, Atom, ctypes.c_long, ctypes.c_long,
                                   ctypes.c_int, Atom, ctypes.POINTER(Atom),
                                   ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
x11.XChangeProperty.argtypes = [ctypes.c_void_p, Window, Atom, Atom, ctypes.c_int,
                                ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
x11.XSendEvent.argtypes = [ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
x11.XPending.argtypes = [ctypes.c_void_p]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XConnectionNumber.argtypes = [ctypes.c_void_p]
x11.XConnectionNumber.restype = ctypes.c_int
x11.XFree.argtypes = [ctypes.c_void_p]

SelectionRequest, SelectionNotify = 30, 31
MAX = 1 << 20


class Req(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("owner", Window), ("requestor", Window),
                ("selection", Atom), ("target", Atom), ("property", Atom),
                ("time", ctypes.c_ulong)]


class Notify(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("requestor", Window), ("selection", Atom),
                ("target", Atom), ("property", Atom), ("time", ctypes.c_ulong)]


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("read", "write"):
        print(__doc__)
        return 2
    dpy = x11.XOpenDisplay(os.environ.get("DISPLAY", ":0").encode())
    if not dpy:
        print("no display")
        return 1
    root = x11.XDefaultRootWindow(dpy)
    clip = x11.XInternAtom(dpy, b"CLIPBOARD", False)
    utf8 = x11.XInternAtom(dpy, b"UTF8_STRING", False)
    targets = x11.XInternAtom(dpy, b"TARGETS", False)
    prop = x11.XInternAtom(dpy, b"OMDROID_PROBE", False)
    win = x11.XCreateSimpleWindow(dpy, root, -10, -10, 1, 1, 0, 0, 0)
    x11.XFlush(dpy)

    if args[0] == "read":
        owner = x11.XGetSelectionOwner(dpy, clip)
        print("owner=%#x" % (owner or 0))
        if not owner:
            return 0
        x11.XConvertSelection(dpy, clip, utf8, prop, win, 0)
        x11.XFlush(dpy)
        deadline = time.time() + 2.0
        fd = x11.XConnectionNumber(dpy)
        while time.time() < deadline:
            select.select([fd], [], [], 0.05)
            while x11.XPending(dpy):
                buf = ctypes.create_string_buffer(192)
                x11.XNextEvent(dpy, buf)
                t = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int)).contents.value
                if t != SelectionNotify:
                    continue
                at = Atom()
                af = ctypes.c_int()
                n = ctypes.c_ulong()
                after = ctypes.c_ulong()
                data = ctypes.POINTER(ctypes.c_ubyte)()
                st = x11.XGetWindowProperty(dpy, win, prop, 0, MAX // 4, False, utf8,
                                            ctypes.byref(at), ctypes.byref(af),
                                            ctypes.byref(n), ctypes.byref(after),
                                            ctypes.byref(data))
                if st != 0 or not data:
                    print("text=<unreadable>")
                    return 1
                raw = ctypes.string_at(data, n.value)
                x11.XFree(ctypes.cast(data, ctypes.c_void_p))
                print("text=%r" % raw.decode("utf-8", "replace"))
                return 0
        print("text=<no SelectionNotify>")
        return 1

    text = args[1].encode() if len(args) > 1 else b""
    secs = float(args[2]) if len(args) > 2 else 6.0
    x11.XSetSelectionOwner(dpy, clip, win, 0)
    x11.XFlush(dpy)
    owner = x11.XGetSelectionOwner(dpy, clip)
    print("owner=%#x %s" % (owner or 0, "ours" if owner == win else "NOT OURS"))
    deadline = time.time() + secs
    answered = 0
    fd = x11.XConnectionNumber(dpy)
    while time.time() < deadline:
        select.select([fd], [], [], 0.05)
        while x11.XPending(dpy):
            buf = ctypes.create_string_buffer(192)
            x11.XNextEvent(dpy, buf)
            t = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int)).contents.value
            if t != SelectionRequest:
                continue
            ev = ctypes.cast(buf, ctypes.POINTER(Req)).contents
            reply = Notify()
            reply.type, reply.display = SelectionNotify, dpy
            reply.requestor, reply.selection = ev.requestor, ev.selection
            reply.target, reply.time = ev.target, ev.time
            reply.property = ev.property
            if ev.target == targets:
                arr = (Atom * 2)(utf8, x11.XInternAtom(dpy, b"STRING", False))
                x11.XChangeProperty(dpy, ev.requestor, ev.property, ctypes.c_ulong(4), 32, 0,
                                    ctypes.cast(arr, ctypes.c_char_p), 2)
            elif ev.target == utf8:
                x11.XChangeProperty(dpy, ev.requestor, ev.property, utf8, 8, 0,
                                    ctypes.c_char_p(text), len(text))
            else:
                reply.property = 0
            x11.XSendEvent(dpy, ev.requestor, 0, 0, ctypes.byref(reply))
            x11.XFlush(dpy)
            answered += 1
    print("answered=%d" % answered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
