#!/usr/bin/env python3
"""Ready marker, layer-fit and UI-mode watcher for the Omarchy guest session.

Started by start.sh before cage starts. Contract halves:
  * section 2 - write $XDG_RUNTIME_DIR/omarchy-ready once the desktop is really
    drawn: Hyprland answers, one enabled monitor equals the even-rounded X root,
    and the layers omarchy-background and omarchy-bar fit its logical size.
    start.sh removes a stale marker; the host removes it too.
  * section 3 - after a live X root change, keep the shell's layers in step with
    the monitor (no session restart, no user action).
  * section 8 - when the host changes $HOME/.config/omdroid/ui (dock/undock, or
    the user's pin), re-apply omdroid-ui.sh and the plugin index and restart only
    the shell, then reload Hyprland's config for the looknfeel half. The session
    and its windows are never touched.

The X root is the authority for the size; the host hint is never consulted here.
Log: /tmp/omarchy-watch.log (guest /tmp), one line per state change.
Acting on a stale layer is capped per monitor size and logged when it gives up.

Dry run without Hyprland: OMDROID_WATCH_UI_SCRIPT / OMDROID_WATCH_INDEX_SCRIPT
point the switch at a scratch copy, OMDROID_ROOT is honoured by omdroid-ui.sh
itself, and OMARCHY_WATCH_LOG moves the log out of /tmp. `switch_ui(mode)` is the
entry point the dry run calls; with no Hyprland it applies the files and reports
the shell restart as deferred.
"""
import ctypes
import glob
import json
import os
import shutil
import subprocess
import time

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
MARKER = os.path.join(RUNTIME, "omarchy-ready")
LOG_PATH = os.environ.get("OMARCHY_WATCH_LOG", "/tmp/omarchy-watch.log")
POLL = 0.25          # seconds between evaluations
STABLE_S = 1.5       # a new monitor size must hold this long before we act
RETRY_CAP = 3        # actions per monitor size, then give up loudly
OMARCHY = os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")
ACT = os.environ.get("OMARCHY_WATCH_ACT", "1") == "1"
HOME = os.environ.get("HOME", "/home/omarchy")
UI_FILE = os.path.join(HOME, ".config", "omdroid", "ui")
UI_SCRIPT = os.environ.get("OMDROID_WATCH_UI_SCRIPT", "/etc/phoshdroid/omdroid-ui.sh")
INDEX_SCRIPT = os.environ.get("OMDROID_WATCH_INDEX_SCRIPT", "/etc/phoshdroid/omarchy-plugin-index.sh")


def log(msg):
    try:
        with open(LOG_PATH, "a") as fh:
            fh.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except OSError:
        pass


x11 = ctypes.CDLL("libX11.so.6")
Window = ctypes.c_ulong
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
x11.XDefaultRootWindow.restype = Window
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XGetGeometry.argtypes = [
    ctypes.c_void_p, Window, ctypes.POINTER(Window),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
    ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
]
x11.XSetErrorHandler.restype = ctypes.c_void_p
_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda d, e: 0)
x11.XSetErrorHandler(_HANDLER)
_DPY = None


def xroot():
    """(width, height) of the X root, or None. Keeps one connection open."""
    global _DPY
    if _DPY is None:
        _DPY = x11.XOpenDisplay(os.environ.get("DISPLAY", ":0").encode())
        if not _DPY:
            return None
    root = x11.XDefaultRootWindow(_DPY)
    r, x, y = Window(), ctypes.c_int(), ctypes.c_int()
    w, h, bw, depth = (ctypes.c_uint() for _ in range(4))
    ok = x11.XGetGeometry(_DPY, root, ctypes.byref(r), ctypes.byref(x), ctypes.byref(y),
                          ctypes.byref(w), ctypes.byref(h), ctypes.byref(bw), ctypes.byref(depth))
    return (w.value, h.value) if ok else None


def signature():
    """The newest Hyprland instance dir name (this session's IPC signature)."""
    dirs = [d for d in glob.glob(os.path.join(RUNTIME, "hypr", "*")) if os.path.isdir(d)]
    if not dirs:
        return None
    return os.path.basename(max(dirs, key=os.path.getmtime))


def ctl(what, sig, timeout=5):
    exe = shutil.which("hyprctl")
    if not exe:
        return None
    env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=sig)
    try:
        r = subprocess.run([exe, "-j", what], capture_output=True, text=True,
                           timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def surface(it):
    """`WxH` of a layer surface dict, or `none`."""
    if not it:
        return "none"
    return f"{it.get('w')}x{it.get('h')}"


def evaluate():
    """One snapshot. Returns a dict; `missing` names what is not there yet."""
    root = xroot()
    if not root:
        return {"missing": "no X display"}
    rw, rh = root
    tw, th = rw & ~1, rh & ~1
    sig = signature()
    if not sig:
        return {"missing": "no Hyprland instance dir"}
    mons = ctl("monitors", sig)
    if not isinstance(mons, list):
        return {"missing": "Hyprland IPC does not answer"}
    enabled = [m for m in mons if not m.get("disabled")]
    if len(enabled) != 1:
        return {"missing": f"{len(enabled)} enabled monitors"}
    m = enabled[0]
    layers = ctl("layers", sig) or {}
    levels = (layers.get(m.get("name"), {}) or {}).get("levels", {}) or {}
    surf = {}
    for items in levels.values():
        for it in items or []:
            surf[it.get("namespace")] = it
    scale = m.get("scale") or 1
    lw = int(round(m.get("width", 0) / scale))
    lh = int(round(m.get("height", 0) / scale))
    bg = surf.get("omarchy-background")
    bar = surf.get("omarchy-bar")
    bg_ok = bool(bg) and abs(bg["w"] - lw) <= 1 and abs(bg["h"] - lh) <= 1
    bar_ok = bool(bar) and abs(bar["w"] - lw) <= 1
    return {
        "missing": None,
        "root": (rw, rh),
        "target": (tw, th),
        "mon": (m.get("width"), m.get("height")),
        "scale": scale,
        "logical": (lw, lh),
        "bg": bg,
        "bar": bar,
        "mon_is_root": (m.get("width"), m.get("height")) == (tw, th),
        "layers_ok": bg_ok and bar_ok,
        "bg_ok": bg_ok,
        "bar_ok": bar_ok,
    }


def write_marker(st):
    text = f"ready {int(time.time())} {st['mon'][0]}x{st['mon'][1]} scale={st['scale']:g}\n"
    tmp = MARKER + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, MARKER)


def ui_mode(path=None):
    """The mode the host wrote to `~/.config/omdroid/ui`.

    Missing or anything but `mobile`/`desktop` means `mobile`, the same default
    omdroid-ui.sh uses, so a guest started without the host writing the file
    behaves exactly as it did before this round.
    """
    try:
        with open(path or UI_FILE) as fh:
            value = fh.read().strip()
    except OSError:
        return "mobile"
    return value if value in ("mobile", "desktop") else "mobile"


def run_script(path, label, timeout=60):
    """Run one guest script; `label rc=0`, or the failing line, never an exception."""
    if not os.path.exists(path):
        return f"{label} missing ({path})"
    try:
        r = subprocess.run(["bash", path], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{label} failed: {e}"
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()
        return f"{label} rc={r.returncode}: " + (tail[-1] if tail else "no output")
    return f"{label} rc=0"


def reload_config(sig, timeout=15):
    """`hyprctl reload`, for the looknfeel half of the switch.

    Never while the monitor and the X root disagree: reload re-applies the
    start-time output mode, so it is only safe once the size has settled. The
    caller checks that and skips this, leaving the size logic to own it.
    """
    exe = shutil.which("hyprctl")
    if not exe or not sig:
        return "hyprctl missing"
    env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=sig)
    try:
        r = subprocess.run([exe, "reload"], capture_output=True, text=True,
                           timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"hyprctl reload failed: {e}"
    return f"hyprctl reload rc={r.returncode}"


def switch_ui(mode, st=None):
    """Apply a UI mode in place (contract section 8). Returns one summary line.

    Step 1, writing `$HOME/.config/omdroid/ui`, is the host's job - this runs only
    when the file already changed. Then, in this order: omdroid-ui.sh (idempotent
    and key-level, so a second run rewrites nothing), the plugin index the shell
    reads instead of scanning, a restart of the shell alone (omarchy-restart-shell,
    which brings the layers back in about 2.4 s), and finally a Hyprland config
    reload for the looknfeel.lua block - skipped when the monitor and the X root
    still differ, because reload re-applies the start-time output mode.

    Called directly by the dry run, where there is no Hyprland: the first two
    steps still run and everything after them is reported as deferred.
    """
    parts = [run_script(UI_SCRIPT, "omdroid-ui"), run_script(INDEX_SCRIPT, "plugin-index")]
    if st is None:
        st = evaluate()
    if st.get("missing"):
        parts.append("shell restart deferred: " + st["missing"])
        return "; ".join(parts)
    if not ACT:
        parts.append("shell restart off (OMARCHY_WATCH_ACT=0)")
        return "; ".join(parts)
    if not may_act():
        parts.append("shell restart rate limited (6 per 60 s, 2 s apart)")
        return "; ".join(parts)
    parts.append(act())
    took = settle()
    if took is None:
        parts.append("layers still do not fit 8 s after the restart")
    else:
        parts.append("layers fit again %.1f s after the restart" % took)
    if st.get("mon_is_root"):
        parts.append(reload_config(signature()))
    else:
        parts.append("hyprctl reload skipped: monitor and X root differ, the size logic owns it")
    return "; ".join(parts)


def act():
    """The remedy for layers that stayed behind: restart only the shell.

    Hyprland follows its parent on its own, so only the shell (and therefore
    its layer surfaces) needs to be told about the new size. `hyprctl reload`
    was measured not to move the layers (and it re-applies the start-time mode,
    which is worse after a resize); this was measured to move them.
    """
    exe = os.path.join(OMARCHY, "bin", "omarchy-restart-shell")
    if not os.path.exists(exe):
        return "omarchy-restart-shell missing"
    env = dict(os.environ)
    env.setdefault("OMARCHY_PATH", OMARCHY)
    try:
        r = subprocess.run([exe], capture_output=True, text=True, timeout=60, env=env)
        return f"omarchy-restart-shell rc={r.returncode}"
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"omarchy-restart-shell failed: {e}"


ACT_TIMES = []


def may_act():
    """At most 6 shell restarts per rolling minute, at least 2 s apart.

    omarchy-restart-shell spawns a fresh omarchy-launch-shell, so there is no
    relaunch counter to preserve; the limit only stops a display that keeps
    flapping (a resize every second) from turning into a restart loop.
    """
    now = time.monotonic()
    ACT_TIMES[:] = [t for t in ACT_TIMES if now - t < 60]
    if len(ACT_TIMES) >= 6:
        return False
    if ACT_TIMES and now - ACT_TIMES[-1] < 2.0:
        return False
    ACT_TIMES.append(now)
    return True


def settle(timeout=8.0):
    """Wait for the restarted shell to draw its layers again.

    Returns the seconds it took, or None if they are still missing: judging a
    half-built shell would fire another restart at it.
    """
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        st = evaluate()
        if not st.get("missing") and st.get("layers_ok"):
            return time.monotonic() - t0
        time.sleep(0.25)
    return None


def main():
    last_ui = ui_mode()
    log(f"start pid={os.getpid()} runtime={RUNTIME} act={'on' if ACT else 'off'} ui={last_ui}")
    ready = False
    last_missing = None
    last_key = None
    size_since = time.monotonic()
    attempts = 0
    while True:
        # The host writes the mode file; the switch itself stays in here, where
        # omdroid-ui.sh, the plugin index and the shell live (contract section 8).
        # Checked before the readiness gate so a mode change that arrives while
        # Hyprland is still starting is applied rather than dropped.
        mode = ui_mode()
        if mode != last_ui:
            log("ui mode %s -> %s, switching in place" % (last_ui, mode))
            log("ui switch: " + switch_ui(mode))
            last_ui = mode
        st = evaluate()
        if st.get("missing"):
            if st["missing"] != last_missing:
                log("waiting: " + st["missing"])
                last_missing = st["missing"]
            time.sleep(POLL)
            continue
        last_missing = None
        key = st["mon"]
        if key != last_key:
            last_key = key
            size_since = time.monotonic()
            attempts = 0
            log("monitor %dx%d scale %g, logical %dx%d, X root %dx%d, "
                "layers background=%s bar=%s" %
                (key[0], key[1], st["scale"], st["logical"][0], st["logical"][1],
                 st["root"][0], st["root"][1], surface(st["bg"]), surface(st["bar"])))
        stable = time.monotonic() - size_since
        mark_ok = st["mon_is_root"] and st["layers_ok"]
        if not ready:
            if mark_ok:
                write_marker(st)
                ready = True
                log("ready %dx%d scale %g written" %
                    (st["mon"][0], st["mon"][1], st["scale"]))
            elif not st["mon_is_root"]:
                log("not ready: monitor %dx%d != X root %dx%d (even-rounded)" %
                    (st["mon"][0], st["mon"][1], st["target"][0], st["target"][1]))
        elif not st["layers_ok"]:
            if stable >= STABLE_S:
                if attempts < RETRY_CAP:
                    attempts += 1
                    log("layers do not fit %dx%d (background=%s bar=%s, need background=%dx%d "
                        "bar width %d): attempt %d/%d" %
                        (key[0], key[1], surface(st["bg"]), surface(st["bar"]),
                         st["logical"][0], st["logical"][1], st["logical"][0],
                         attempts, RETRY_CAP))
                    if ACT:
                        if may_act():
                            log("act: " + act())
                            took = settle()
                            if took is None:
                                log("act: layers still do not fit 8 s after the restart")
                            else:
                                log("act: layers fit again %.1f s after the restart" % took)
                                attempts = 0
                        else:
                            log("act: not acting, restart rate limit reached (6 per 60 s, 2 s apart)")
                    size_since = time.monotonic()
                elif attempts == RETRY_CAP:
                    attempts += 1
                    log("giving up on %dx%d after %d attempts (background=%s bar=%s)" %
                        (key[0], key[1], RETRY_CAP, surface(st["bg"]), surface(st["bar"])))
        elif attempts:
            log("layers fit %dx%d again after %d attempt(s)" %
                (key[0], key[1], attempts))
            attempts = 0
        time.sleep(POLL)


if __name__ == "__main__":
    main()
