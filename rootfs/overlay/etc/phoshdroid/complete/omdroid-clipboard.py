#!/usr/bin/env python3
"""Carry text between the guest Wayland clipboard and the X display Termux:X11 serves.

Under cage nothing turns a Wayland data offer into an X selection, so the two
clipboards are separate worlds: `wl-copy` then `wl-paste` works inside Hyprland,
while an X client on :0 reads `CLIPBOARD owner=0x0`. Android only ever talks to
the X side (Xlorie forwards a selection owner's text to Android, and takes the
selection itself when Android copies), so nothing reaches Android without this.

Two directions, one process:

  Wayland -> X   `wl-paste --watch` hands us each new text; we take CLIPBOARD on
                 :0 with our own window and answer TARGETS and the text targets.
                 Xlorie's SelectionSetOwner callback then forwards it to Android.
  X -> Wayland   XFixes tells us when CLIPBOARD changes owner; an owner that is
                 not us means someone else (Xlorie, after an Android copy) has
                 text. We convert it, read the property and run `wl-copy`.

Guard: a text that equals the one we last carried in either direction is dropped,
so an Android copy does not echo back into Android through the Wayland loop.
Text only, capped at OMDROID_CLIPBOARD_MAX bytes (1 MiB), no INCR transfers and
no images.

usage: omdroid-clipboard.py [-v]
  -v   log every selection change to OMDROID_CLIPBOARD_LOG (default
       /tmp/omdroid-clipboard.log); without it only start-up and errors are logged.
Switch: OMDROID_CLIPBOARD_BRIDGE=0 keeps this from being started at all (the
complete hook reads it).
"""
import ctypes
import os
import select
import subprocess
import sys
import time

VERBOSE = "-v" in sys.argv[1:] or bool(os.environ.get("OMDROID_CLIPBOARD_DEBUG"))
LOG_PATH = os.environ.get("OMDROID_CLIPBOARD_LOG", "/tmp/omdroid-clipboard.log")
MAX_BYTES = int(os.environ.get("OMDROID_CLIPBOARD_MAX", "1048576"))
DISPLAY = os.environ.get("DISPLAY", ":0")
X_WAIT = float(os.environ.get("OMDROID_CLIPBOARD_X_WAIT", "60"))
WL_WAIT = float(os.environ.get("OMDROID_CLIPBOARD_WL_WAIT", "60"))

LOG = open(LOG_PATH, "w", buffering=1) if LOG_PATH else None


def say(msg):
    if LOG:
        LOG.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))


def debug(msg):
    if VERBOSE:
        say(msg)


# --- Xlib through ctypes -----------------------------------------------------------
x11 = ctypes.CDLL("libX11.so.6")
xfixes = ctypes.CDLL("libXfixes.so.3")

Window = ctypes.c_ulong
Atom = ctypes.c_ulong
Time = ctypes.c_ulong
Bool = ctypes.c_int

x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = Window
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XCreateSimpleWindow.restype = Window
x11.XCreateSimpleWindow.argtypes = [ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                                    ctypes.c_ulong, ctypes.c_ulong]
x11.XInternAtom.restype = Atom
x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, Bool]
x11.XSetSelectionOwner.argtypes = [ctypes.c_void_p, Atom, Window, Time]
x11.XGetSelectionOwner.restype = Window
x11.XGetSelectionOwner.argtypes = [ctypes.c_void_p, Atom]
x11.XConvertSelection.argtypes = [ctypes.c_void_p, Atom, Atom, Atom, Window, Time]
x11.XChangeProperty.argtypes = [ctypes.c_void_p, Window, Atom, Atom, ctypes.c_int,
                                ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
x11.XGetWindowProperty.argtypes = [ctypes.c_void_p, Window, Atom, ctypes.c_long,
                                   ctypes.c_long, Bool, Atom,
                                   ctypes.POINTER(Atom), ctypes.POINTER(ctypes.c_int),
                                   ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.c_ulong),
                                   ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
x11.XFree.argtypes = [ctypes.c_void_p]
x11.XSendEvent.argtypes = [ctypes.c_void_p, Window, Bool, ctypes.c_long,
                           ctypes.c_void_p]
x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
x11.XPending.argtypes = [ctypes.c_void_p]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XSync.argtypes = [ctypes.c_void_p, Bool]
x11.XConnectionNumber.argtypes = [ctypes.c_void_p]
x11.XConnectionNumber.restype = ctypes.c_int

xfixes.XFixesQueryExtension.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                        ctypes.POINTER(ctypes.c_int)]
xfixes.XFixesSelectSelectionInput.argtypes = [ctypes.c_void_p, Window, Atom, ctypes.c_ulong]

XFIXES_SET_SELECTION_OWNER_NOTIFY = 1
XFIXES_SELECTION_WINDOW_DESTROY_NOTIFY = 2
XFIXES_SELECTION_CLIENT_CLOSE_NOTIFY = 4
XFIXES_SELECTION_NOTIFY_MASK = (XFIXES_SET_SELECTION_OWNER_NOTIFY
                                | XFIXES_SELECTION_WINDOW_DESTROY_NOTIFY
                                | XFIXES_SELECTION_CLIENT_CLOSE_NOTIFY)

SelectionRequest = 30
SelectionNotify = 31
PropertyNotify = 28
PropertyChangeMask = 1 << 22
CurrentTime = 0
NoEventMask = 0


class XSelectionRequestEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
                ("owner", Window), ("requestor", Window), ("selection", Atom),
                ("target", Atom), ("property", Atom), ("time", Time)]


class XSelectionEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
                ("requestor", Window), ("selection", Atom), ("target", Atom),
                ("property", Atom), ("time", Time)]


EVENT_BYTES = 192  # sizeof(XEvent) on 64-bit: 24 longs


def atom(display, name):
    return x11.XInternAtom(display, name.encode(), False)


def open_display(wait):
    """X may not exist yet: start.sh runs hooks before cage has its X server up."""
    deadline = time.time() + wait
    while True:
        dpy = x11.XOpenDisplay(DISPLAY.encode())
        if dpy:
            return dpy
        if time.time() >= deadline:
            return None
        time.sleep(0.5)


# --- the bridge --------------------------------------------------------------------
class Bridge:
    def __init__(self, dpy):
        self.dpy = dpy
        self.root = x11.XDefaultRootWindow(dpy)
        self.a_clipboard = atom(dpy, "CLIPBOARD")
        self.a_targets = atom(dpy, "TARGETS")
        self.a_utf8 = atom(dpy, "UTF8_STRING")
        self.a_string = atom(dpy, "STRING")
        self.a_text = atom(dpy, "TEXT")
        self.a_prop = atom(dpy, "OMDROID_CLIPBOARD")
        self.window = x11.XCreateSimpleWindow(dpy, self.root, -10, -10, 1, 1, 0, 0, 0)
        self.last_text = None        # the text we believe both sides hold
        self.last_set_on_x = None    # the text we last made the X selection owner for
        self.pending = None          # text expected in the next SelectionNotify
        self.wl: "WaylandWatch | None" = None   # set once the watch starts
        self.copies = []             # live wl-copy processes, newest last
        ev = ctypes.c_int()
        er = ctypes.c_int()
        self.have_xfixes = bool(xfixes.XFixesQueryExtension(dpy, ctypes.byref(ev), ctypes.byref(er)))
        if self.have_xfixes:
            xfixes.XFixesSelectSelectionInput(dpy, self.root, self.a_clipboard,
                                              XFIXES_SELECTION_NOTIFY_MASK)
            self.xfixes_base = ev.value
            say("x: XFixes %d.%d, watching CLIPBOARD" % (ev.value, er.value))
        else:
            self.xfixes_base = None
            say("x: no XFixes, Android-to-guest copies will not be picked up")
        x11.XFlush(dpy)

    # --- X -> Wayland ---
    def handle_x_changed(self):
        owner = x11.XGetSelectionOwner(self.dpy, self.a_clipboard)
        debug("x: CLIPBOARD owner=%#x" % (owner or 0))
        if owner in (0, self.window):
            return
        self.pending = time.time()
        x11.XConvertSelection(self.dpy, self.a_clipboard, self.a_utf8, self.a_prop,
                              self.window, CurrentTime)
        x11.XFlush(self.dpy)

    def read_property(self):
        actual_type = Atom()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        after = ctypes.c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        status = x11.XGetWindowProperty(self.dpy, self.window, self.a_prop, 0,
                                        max(1, MAX_BYTES // 4), False, self.a_utf8,
                                        ctypes.byref(actual_type),
                                        ctypes.byref(actual_format),
                                        ctypes.byref(nitems), ctypes.byref(after),
                                        ctypes.byref(data))
        if status != 0 or not data:
            return None
        try:
            raw = ctypes.string_at(data, nitems.value if actual_format.value == 8
                                   else nitems.value * 4)
        finally:
            x11.XFree(ctypes.cast(data, ctypes.c_void_p))
        if after.value:
            raw = raw[:MAX_BYTES]
        try:
            text = raw.decode("utf-8", "replace")
        except Exception:
            return None
        if text and text[-1] == "\x00":
            text = text[:-1]
        return text

    def to_wayland(self, text):
        if not text or text == self.last_text:
            return
        # wl-copy can stay in the foreground while it serves the selection; a
        # blocking wait here stalls this loop, and the loop is what notices the
        # next Android copy. Start it, hand it the text, keep the handle.
        try:
            env = dict(os.environ)
            # Both halves must speak to the compositor the watch found: the hook
            # inherits WAYLAND_DISPLAY=wayland-omarchy (cage's socket), and a
            # wl-copy sent there leaves Hyprland's clipboard empty.
            if self.wl is not None and self.wl.display:
                env["WAYLAND_DISPLAY"] = self.wl.display
            proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, env=env)
            if proc.stdin is None:
                return
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
        except Exception as exc:  # noqa: BLE001 - a clipboard failure must not kill us
            say("wl-copy failed: %s" % exc)
            return
        self.copies.append(proc)
        self.copies = [p for p in self.copies if p.poll() is None][-4:]
        self.last_text = text
        # The X selection already holds this text (it came from there), so a
        # later Wayland change carrying the same text must not re-own it: that
        # would hand Xlorie the same clipboard again.
        self.last_set_on_x = text
        say("x -> wayland: %d chars" % len(text))

    # --- Wayland -> X ---
    def own_selection(self, text):
        self.last_text = text
        self.last_set_on_x = text
        x11.XSetSelectionOwner(self.dpy, self.a_clipboard, self.window, CurrentTime)
        x11.XFlush(self.dpy)
        say("wayland -> x: %d chars" % len(text))

    def to_x(self, text):
        if not text:
            return
        if text == self.last_text and text == self.last_set_on_x:
            return
        self.own_selection(text)

    def serve_request(self, ev):
        if ev.selection != self.a_clipboard or self.last_set_on_x is None:
            return
        reply = XSelectionEvent()
        reply.type = SelectionNotify
        reply.display = self.dpy
        reply.requestor = ev.requestor
        reply.selection = ev.selection
        reply.target = ev.target
        reply.time = ev.time
        reply.property = ev.property
        text = self.last_set_on_x.encode("utf-8")[:MAX_BYTES]
        if ev.target == self.a_targets:
            targets = (Atom * 4)(self.a_utf8, self.a_string, self.a_text,
                                 atom(self.dpy, "text/plain;charset=utf-8"))
            x11.XChangeProperty(self.dpy, ev.requestor, ev.property, ctypes.c_ulong(4),
                                32, 0, ctypes.cast(targets, ctypes.c_char_p), 4)
            debug("x: answered TARGETS for %#x" % ev.requestor)
        elif ev.target in (self.a_utf8, self.a_string, self.a_text,
                           atom(self.dpy, "text/plain;charset=utf-8")):
            x11.XChangeProperty(self.dpy, ev.requestor, ev.property, self.a_utf8, 8, 0,
                                ctypes.cast(ctypes.c_char_p(text), ctypes.c_char_p),
                                len(text))
            debug("x: answered %d chars for %#x" % (len(text), ev.requestor))
        else:
            reply.property = 0  # refuse
            debug("x: refused target %#x" % ev.target)
        x11.XSendEvent(self.dpy, ev.requestor, False, NoEventMask, ctypes.byref(reply))
        x11.XFlush(self.dpy)

    # --- the loop ---
    def pump_wl(self):
        if not self.wl:
            return
        text = self.wl.take()
        if text is not None:
            self.to_x(text)
        self.wl.check()

    def run(self):
        fd = x11.XConnectionNumber(self.dpy)
        while True:
            try:
                r, _, _ = select.select([fd], [], [], 0.05)
            except InterruptedError:
                continue
            while x11.XPending(self.dpy):
                buf = ctypes.create_string_buffer(EVENT_BYTES)
                x11.XNextEvent(self.dpy, buf)
                etype = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int)).contents.value
                if etype == SelectionRequest:
                    self.serve_request(ctypes.cast(buf, ctypes.POINTER(
                        XSelectionRequestEvent)).contents)
                elif etype == SelectionNotify:
                    if self.pending:
                        self.pending = None
                        self.to_wayland(self.read_property())
                elif self.xfixes_base is not None and etype == self.xfixes_base:
                    self.handle_x_changed()
            self.pump_wl()


class WaylandWatch:
    """wl-paste --watch runs a command on every clipboard change; it is not a
    stream. So the command drops the new text into a file with an atomic
    rename, and the bridge polls that file. No framing problem for multi-line
    text, and a half-written read cannot happen."""

    def __init__(self):
        self.proc = None
        self.path = os.environ.get("OMDROID_CLIPBOARD_FILE",
                                   "/tmp/omdroid-clipboard.dat")
        self.last_retry = 0.0
        self.display = None
        self.stamp = None
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def command(self):
        sink = ('cat > "%s.new" && mv -f "%s.new" "%s"'
                % (self.path, self.path, self.path))
        return ["wl-paste", "--watch", "sh", "-c", sink]

    def start(self, wait):
        """The session's clipboard lives on Hyprland's socket, which is not the
        WAYLAND_DISPLAY start.sh exports (that one is cage's). A candidate whose
        wl-paste exits at once is the wrong compositor, so take the first socket
        where the watch stays alive."""
        deadline = time.time() + wait
        while True:
            for name in self.candidates():
                env = dict(os.environ)
                env["WAYLAND_DISPLAY"] = name
                try:
                    proc = subprocess.Popen(self.command(), stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, env=env)
                except FileNotFoundError:
                    say("wl-paste is not installed; guest-to-Android copies are off")
                    return False
                except Exception:  # noqa: BLE001
                    continue
                for _ in range(20):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                if proc.poll() is None:
                    self.proc = proc
                    self.display = name
                    say("wayland: watching %s" % name)
                    return True
            if time.time() >= deadline:
                say("no Wayland compositor accepted wl-paste (tried %s)"
                    % ", ".join(self.candidates()))
                self.proc = None
                return False
            time.sleep(1.0)

    @staticmethod
    def candidates():
        seen = []
        name = os.environ.get("WAYLAND_DISPLAY")
        if name:
            seen.append(name)
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        if runtime and os.path.isdir(runtime):
            # Hyprland starts after cage, so it owns the later socket number.
            for entry in sorted(os.listdir(runtime), reverse=True):
                if entry.startswith("wayland-") and not entry.endswith(".lock"):
                    if entry not in seen:
                        seen.append(entry)
        return seen

    def check(self):
        """Hyprland can restart under us; wl-paste dies with it, so bring the
        watch back rather than going quietly one-way."""
        if self.proc is not None and self.proc.poll() is None:
            return
        now = time.time()
        if now - self.last_retry < 5.0:
            return
        self.last_retry = now
        if self.start(0):
            say("wl-paste watch restarted")

    def take(self):
        """The newest text from the guest clipboard, once per change."""
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        stamp = (st.st_mtime_ns, st.st_size)
        if stamp == self.stamp:
            return None
        self.stamp = stamp
        try:
            with open(self.path, "rb") as fh:
                raw = fh.read(MAX_BYTES)
        except OSError:
            return None
        return raw.decode("utf-8", "replace")


def main():
    dpy = open_display(X_WAIT)
    if not dpy:
        say("no X display %s after %.0fs; giving up" % (DISPLAY, X_WAIT))
        return 1
    bridge = Bridge(dpy)
    say("started: display %s, window %#x" % (DISPLAY, bridge.window))
    wl = WaylandWatch()
    have_wl = wl.start(WL_WAIT)
    if have_wl:
        bridge.wl = wl
    else:
        say("running X -> none: no Wayland clipboard to speak to")
    try:
        bridge.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
