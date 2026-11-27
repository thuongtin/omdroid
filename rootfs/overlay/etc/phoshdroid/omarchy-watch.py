#!/usr/bin/env python3
"""Ready marker, layer-fit and UI-mode watcher for the Omarchy guest session.

Started by start.sh before cage starts. Contract halves:
  * section 2 - write $XDG_RUNTIME_DIR/omarchy-ready once the desktop is really
    drawn: Hyprland answers, one enabled monitor equals the even-rounded X root,
    and the layers omarchy-background and omarchy-bar fit its logical size.
    start.sh removes a stale marker; the host removes it too.
  * section 3 - after a live X root change, keep the shell's layers in step with
    the monitor (no session restart, no user action).
  * section 8 - when the mode changes ($HOME/.config/omdroid/ui-pin when it
    names a mode, else $HOME/.config/omdroid/ui, which the host writes on a
    dock/undock), re-apply omdroid-ui.sh and the plugin index, put the monitor
    back on the X root, restart only the shell, then reload Hyprland's config
    (config-only) for the looknfeel half. The session and its windows are never
    touched.
  * launch contract section 4 (F6) - the UI scale follows the display: the host writes
    $HOME/.config/omdroid/ui-scale (1 or 2) for the display the desktop is on, and the
    watcher puts the monitor on that scale with the same runtime rule it uses for the
    size, then the layer remedy restarts only the shell. OMDROID_SCALE_FOLLOW=0 (in
    session.env) turns it off, and a missing or unreadable file changes nothing.
  * after ready, keep the Hyprland monitor equal to the even-rounded X root:
    monitors.lua builds its mode from the start-time size, so any config reload
    (Hyprland reloads by itself when a config file changes) puts the start-time
    mode back after a dock. A runtime monitor rule (hyprctl eval) undoes it.

The X root is the authority for the size; the host hint is never consulted here.
Log: /tmp/omarchy-watch.log (guest /tmp), one line per state change.
Acting on a stale layer is capped per monitor size and logged when it gives up.

Dry run without Hyprland: OMDROID_WATCH_UI_SCRIPT / OMDROID_WATCH_INDEX_SCRIPT
point the switch at a scratch copy, OMDROID_ROOT is honoured by omdroid-ui.sh
itself, and OMARCHY_WATCH_LOG moves the log out of /tmp. `switch_ui(mode)` is the
entry point the dry run calls; with no Hyprland it applies the files and reports
the shell restart as deferred.

Hyprland is queried over its own request socket (`hypr/<signature>/.socket.sock`,
`j/monitors` / `j/layers`), so a poll forks nothing; `hyprctl` stays only for the
state-changing calls and as the fallback when the socket does not answer. The
query runs every tick until the marker is written and for 10 s after a size, mode
or shell change, then once per OMDROID_WATCH_HEARTBEAT (default 2 s).
OMDROID_WATCH_LEGACY=1 restores the old hyprctl-every-tick behaviour.
"""
import ctypes
import glob
import json
import os
import shutil
import socket
import subprocess
import time

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
MARKER = os.path.join(RUNTIME, "omarchy-ready")
LOG_PATH = os.environ.get("OMARCHY_WATCH_LOG", "/tmp/omarchy-watch.log")
# A restart that kills the shell instead of bringing it back leaves this behind, so the
# failure outlives the log and the next session can report it.
FAIL_PATH = os.path.join(os.path.expanduser("~"), ".local", "state", "omdroid", "shell-restart-failed")
POLL = 0.25          # seconds between evaluations
STABLE_S = 1.5       # a new monitor size must hold this long before we act


def _env_positive(name, default):
    """A positive float from the environment, or `default`."""
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


HEARTBEAT = _env_positive("OMDROID_WATCH_HEARTBEAT", 2.0)  # steady-state query interval
HOT_S = 10.0         # query every tick this long after a size, mode or shell change
LEGACY = os.environ.get("OMDROID_WATCH_LEGACY") == "1"  # old hyprctl-every-tick path

RETRY_CAP = 3        # actions per monitor size, then give up loudly
OMARCHY = os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")
ACT = os.environ.get("OMARCHY_WATCH_ACT", "1") == "1"
HOME = os.environ.get("HOME", "/home/omarchy")
UI_FILE = os.path.join(HOME, ".config", "omdroid", "ui")
UI_PIN = os.path.join(HOME, ".config", "omdroid", "ui-pin")
UI_SCALE = os.environ.get("OMDROID_WATCH_SCALE_FILE", os.path.join(HOME, ".config", "omdroid", "ui-scale"))
SCALE_FOLLOW = os.environ.get("OMDROID_SCALE_FOLLOW", "1") != "0"
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


def socket_request(what, sig, timeout=2.0):
    """`j/<what>` on Hyprland's request socket: parsed JSON, or None.

    Hyprland answers and closes the connection, so read to EOF. A missing
    socket, a refused connect, a read timeout or a malformed answer returns
    None, and the caller falls back to `hyprctl` for that call.
    """
    path = os.path.join(RUNTIME, "hypr", sig, ".socket.sock")
    if not os.path.exists(path):
        return None
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(path)
        sock.sendall(("j/" + what).encode())
        data = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
    except OSError:
        return None
    finally:
        sock.close()
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except ValueError:
        return None


def hypr(what, sig, timeout=2.0):
    """`j/<what>` from Hyprland: the socket first, `hyprctl -j` as the fallback.

    The fallback keeps a protocol surprise at the old behaviour (one hyprctl
    fork for that query); OMDROID_WATCH_LEGACY=1 forces it for the device A/B.
    """
    if not LEGACY:
        value = socket_request(what, sig, timeout)
        if value is not None:
            return value
    return ctl(what, sig)


def surface(it):
    """`WxH` of a layer surface dict, or `none`."""
    if not it:
        return "none"
    return f"{it.get('w')}x{it.get('h')}"


def evaluate(root=None, hypr_data=None):
    """One snapshot. Returns a dict; `missing` names what is not there yet.

    `root` and `hypr_data` let the main loop reuse the X reading it already has
    and skip the Hyprland query on ticks where nothing can have changed; the
    defaults read the root and query Hyprland now, which is what the settle and
    switch paths want.
    """
    if root is None:
        root = xroot()
    if not root:
        return {"missing": "no X display"}
    rw, rh = root
    tw, th = rw & ~1, rh & ~1
    sig = signature()
    if not sig:
        return {"missing": "no Hyprland instance dir"}
    if hypr_data is None:
        hypr_data = (hypr("monitors", sig), hypr("layers", sig))
    mons, layers = hypr_data
    if not isinstance(mons, list):
        return {"missing": "Hyprland IPC does not answer"}
    enabled = [m for m in mons if not m.get("disabled")]
    if len(enabled) != 1:
        return {"missing": f"{len(enabled)} enabled monitors"}
    m = enabled[0]
    levels = ((layers or {}).get(m.get("name"), {}) or {}).get("levels", {}) or {}
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
        "hz": m.get("refreshRate"),
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


def read_mode(path):
    """`mobile` or `desktop` from one mode file, or None when absent or anything else."""
    try:
        with open(path) as fh:
            value = fh.read().strip()
    except OSError:
        return None
    return value if value in ("mobile", "desktop") else None


def ui_mode(path=None, pin_path=None):
    """The mode the guest applies (contract section 8).

    The user's pin (`~/.config/omdroid/ui-pin`) wins while it names a mode; `auto`,
    missing or anything else defers to the host's `~/.config/omdroid/ui`. Missing
    or unknown there means `mobile`, the same default omdroid-ui.sh uses, so a
    guest started without the host writing either file behaves as before.
    """
    return read_mode(pin_path or UI_PIN) or read_mode(path or UI_FILE) or "mobile"


def wanted_scale(path=None):
    """The UI scale the host wants (1 or 2), or None when the watcher must leave it alone.

    The host (DockMonitor, LauncherActivity) writes ~/.config/omdroid/ui-scale for the
    display the desktop is on. Missing, unreadable, fractional or any other value means
    None, as does OMDROID_SCALE_FOLLOW=0: then the start-time OMARCHY_SCALE stays, which
    is exactly the behaviour before F6.
    """
    if not SCALE_FOLLOW:
        return None
    try:
        with open(path or UI_SCALE) as fh:
            value = fh.read().strip()
    except OSError:
        return None
    return {"1": 1, "2": 2}.get(value)


def scale_matches(st, want):
    """True when the monitor already runs the wanted scale (or none is wanted)."""
    return want is None or abs((st.get("scale") or 1) - want) < 0.01


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
    """`hyprctl reload config-only`, for the looknfeel half of the switch.

    config-only: a full reload re-applies the monitor rule, and monitors.lua
    builds that rule from the START-TIME size, so after a dock it would put the
    session-start mode back (r7 device round: 3200x1970 on a 1920x914 cage).
    """
    exe = shutil.which("hyprctl")
    if not exe or not sig:
        return "hyprctl missing"
    env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=sig)
    try:
        r = subprocess.run([exe, "reload", "config-only"], capture_output=True, text=True,
                           timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"hyprctl reload config-only failed: {e}"
    return f"hyprctl reload config-only rc={r.returncode}"


def fit_monitor(st, timeout=10, scale=None):
    """Put the Hyprland monitor on the even-rounded X root with a runtime rule.

    Hyprland follows cage on its own, but every config reload (an explicit one,
    or Hyprland's autoreload when omdroid-ui.sh edits looknfeel.lua) re-applies
    monitors.lua, whose mode is the size at session start. `hyprctl eval` with
    `hl.monitor` puts the current size back at once (measured on the tablet:
    3200x1970 -> 1920x914 in one call); scale and refresh are kept, unless `scale`
    names the one the host wants (F6): then the same rule carries it, and the GDK
    scale that monitors.lua exported at start follows in a second, best-effort call
    (apps started after it get the new GDK_SCALE).
    """
    exe = shutil.which("hyprctl")
    sig = signature()
    if not exe or not sig:
        return "monitor fit skipped: no hyprctl or Hyprland instance"
    tw, th = st["target"]
    hz = st.get("hz") or 120.0
    new_scale = st["scale"] if scale is None else scale
    lua = ('hl.monitor({ output = "", mode = "%dx%d@%.3f", position = "auto", '
           'scale = %g, transform = 0 })' % (tw, th, hz, new_scale))
    env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=sig)
    try:
        r = subprocess.run([exe, "eval", lua], capture_output=True, text=True,
                           timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"monitor fit failed: {e}"
    line = f"monitor fit {tw}x{th} scale {new_scale:g} rc={r.returncode}"
    if scale is not None and abs(scale - st["scale"]) >= 0.01:
        try:
            r2 = subprocess.run([exe, "eval", 'hl.env("GDK_SCALE", "%d")' % int(round(scale))],
                                capture_output=True, text=True, timeout=timeout, env=env)
            line += f"; GDK_SCALE {int(round(scale))} rc={r2.returncode}"
        except (OSError, subprocess.TimeoutExpired) as e:
            line += f"; GDK_SCALE failed: {e}"
    return line


# Non-empty while a UI switch could not restart the shell because of the rate
# limit: the main loop restarts it as soon as the limit allows, so the old UI
# is never left on screen (it used to be dropped for good).
PENDING_RESTART = []


def switch_ui(mode, st=None):
    """Apply a UI mode in place (contract section 8). Returns one summary line.

    Step 1, writing the mode file, is the host's job (or the user's pin) - this
    runs only when the mode already changed. Then, in this order: omdroid-ui.sh
    (idempotent and key-level, so a second run rewrites nothing), the plugin
    index the shell reads instead of scanning, the monitor put back on the X root
    when a config reload moved it (omdroid-ui.sh edits looknfeel.lua and Hyprland
    reloads on its own), a restart of the shell alone (omarchy-restart-shell,
    about 2.4 s; queued when the rate limit is reached, never dropped), and a
    config-only Hyprland reload for the looknfeel.lua block.

    Called directly by the dry run, where there is no Hyprland: the first two
    steps still run and everything after them is reported as deferred.
    """
    parts = [run_script(UI_SCRIPT, "omdroid-ui"), run_script(INDEX_SCRIPT, "plugin-index")]
    if st is None:
        st = evaluate()
    if st.get("missing"):
        parts.append("shell restart deferred: " + st["missing"])
        return "; ".join(parts)
    want = wanted_scale()
    if not st.get("mon_is_root") or not scale_matches(st, want):
        parts.append(fit_monitor(st, scale=want))
        time.sleep(0.5)
    if not ACT:
        parts.append("shell restart off (OMARCHY_WATCH_ACT=0)")
        return "; ".join(parts)
    if not may_act():
        PENDING_RESTART[:] = [mode]
        parts.append("shell restart rate limited (6 per 60 s, 2 s apart), queued")
        return "; ".join(parts)
    PENDING_RESTART[:] = []
    parts.append(act())
    took = settle()
    if took is None:
        verdict, facts = shell_after_failure()
        if verdict == "failed":
            write_failure(facts)
            parts.append("shell restart FAILED (%s), not retried" % facts)
        else:
            parts.append("layers still do not fit 8 s after the restart (%s)" % facts)
    else:
        parts.append("layers fit again %.1f s after the restart" % took)
    parts.append(reload_config(signature()))
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


def shell_processes():
    """How many Quickshell shell processes run, or None when that cannot be told.

    `omarchy-launch-shell` runs `quickshell -n -p $OMARCHY_PATH/shell` in the background, so a
    restart that leaves none at all has lost the shell; a restart that leaves one is a shell that
    may still be drawing.
    """
    exe = shutil.which("pgrep")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-c", "-f", "quickshell .*-p "],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode == 1:
        return 0
    if r.returncode != 0:
        return None
    try:
        return int((r.stdout or "").strip())
    except ValueError:
        return None


def shell_after_failure():
    """`(verdict, facts)` when a restart did not bring the layers back.

    `failed` means the restart lost the shell (no shell layers at all, or no Quickshell process):
    repeating it would repeat the crash, so the caller stops instead of using the retry budget.
    `unfit` means the layers are there but do not fit yet, which is what the retry is for.
    `unknown` is a reading that cannot decide either way; it is retried like `unfit`, the old
    behaviour, and logged as such.
    """
    st = evaluate()
    if st.get("missing"):
        return "unknown", "no reading: " + st["missing"]
    procs = shell_processes()
    facts = "layers background=%s bar=%s quickshell=%s" % (
        surface(st.get("bg")), surface(st.get("bar")),
        "unknown" if procs is None else procs)
    if (st.get("bg") is None and st.get("bar") is None) or procs == 0:
        return "failed", facts
    return "unfit", facts


def write_failure(facts):
    """Record a failed restart on disk (best effort, never fatal)."""
    try:
        os.makedirs(os.path.dirname(FAIL_PATH), exist_ok=True)
        with open(FAIL_PATH, "w") as fh:
            fh.write("%s shell restart failed, not retried: %s\n"
                     % (time.strftime("%Y-%m-%d %H:%M:%S"), facts))
    except OSError:
        pass


def main():
    last_ui = ui_mode()
    log("start pid=%d runtime=%s act=%s ui=%s heartbeat=%.1fs legacy=%s" %
        (os.getpid(), RUNTIME, "on" if ACT else "off", last_ui, HEARTBEAT,
         "on" if LEGACY else "off"))
    ready = False
    last_missing = None
    last_key = None
    size_since = time.monotonic()
    attempts = 0
    fits = 0
    scale_fits = 0
    last_want = wanted_scale()
    limited = False
    last_root = None
    last_sig = None
    last_query = 0.0
    hot_until = 0.0
    hypr_data = None
    while True:
        now = time.monotonic()
        root = xroot()
        if root != last_root:
            # A rotation, a fold or a dock: ask Hyprland at once and keep asking
            # every tick while the size settles. The first reading is not a
            # change; the pre-ready path already queries every tick.
            if last_root is not None:
                hot_until = now + HOT_S
            last_root = root
        sig = signature()
        if sig != last_sig:
            if last_sig is not None:
                hot_until = now + HOT_S
            last_sig = sig
        # Ask Hyprland while the session is not ready yet, for HOT_S after any
        # change that can move the monitor or the layers, on the steady
        # heartbeat, or until a first answer arrived. Other ticks read only the
        # X root, which forks nothing.
        if (LEGACY or not ready or hypr_data is None or now < hot_until
                or now - last_query >= HEARTBEAT):
            hypr_data = (hypr("monitors", sig) if sig else None,
                         hypr("layers", sig) if sig else None)
            last_query = now
        # The host writes the mode file (and the user may pin one); the switch
        # itself stays in here, where omdroid-ui.sh, the plugin index and the
        # shell live (contract section 8). Checked before the readiness gate so a
        # mode change that arrives while Hyprland is still starting is applied
        # rather than dropped.
        want = wanted_scale()
        if want != last_want:
            log("ui-scale %s -> %s" % (last_want, want))
            last_want = want
            scale_fits = 0
        mode = ui_mode()
        if mode != last_ui:
            log("ui mode %s -> %s, switching in place" % (last_ui, mode))
            log("ui switch: " + switch_ui(mode))
            last_ui = mode
            hot_until = time.monotonic() + HOT_S
            hypr_data = None
        st = evaluate(root, hypr_data)
        if st.get("missing"):
            if st["missing"] != last_missing:
                log("waiting: " + st["missing"])
                last_missing = st["missing"]
            time.sleep(POLL)
            continue
        last_missing = None
        if PENDING_RESTART and ACT and may_act():
            queued = PENDING_RESTART[0]
            PENDING_RESTART[:] = []
            log("ui switch to %s: queued shell restart: %s" % (queued, act()))
            took = settle()
            if took is None:
                verdict, facts = shell_after_failure()
                if verdict == "failed":
                    write_failure(facts)
                log("ui switch to %s: %s" % (queued, "shell restart FAILED (%s), not retried" % facts
                                              if verdict == "failed" else
                                              "layers still do not fit 8 s after the restart (%s)" % facts))
            else:
                log("ui switch to %s: layers fit again %.1f s after the restart" % (queued, took))
            hot_until = time.monotonic() + HOT_S
            hypr_data = None
            continue
        key = st["mon"]
        if key != last_key:
            last_key = key
            size_since = time.monotonic()
            attempts = 0
            fits = 0
            scale_fits = 0
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
        elif not st["mon_is_root"]:
            # A config reload put the start-time mode back (see fit_monitor).
            if stable >= STABLE_S and fits < RETRY_CAP:
                fits += 1
                log("monitor %dx%d != X root %dx%d (even-rounded): %s, attempt %d/%d" %
                    (key[0], key[1], st["target"][0], st["target"][1],
                     fit_monitor(st, scale=want), fits, RETRY_CAP))
                size_since = time.monotonic()
                hot_until = size_since + HOT_S
                hypr_data = None
        elif not scale_matches(st, want):
            # F6: the host wants another scale (a dock or undock moved the desktop to a
            # display with another density, or a config reload put the start-time scale
            # back). The same runtime rule as the size fit; the layers then no longer fit
            # the new logical size and the remedy below restarts only the shell.
            if stable >= STABLE_S and scale_fits < RETRY_CAP:
                scale_fits += 1
                log("monitor scale %g != ui-scale %d: %s, attempt %d/%d" %
                    (st["scale"], want, fit_monitor(st, scale=want), scale_fits, RETRY_CAP))
                size_since = time.monotonic()
                hot_until = size_since + HOT_S
                hypr_data = None
        elif not st["layers_ok"]:
            if stable >= STABLE_S:
                if attempts < RETRY_CAP:
                    if ACT and not may_act():
                        # A rate-limited pass is not an attempt: wait for the
                        # limit instead of giving up with stale layers on screen.
                        if not limited:
                            log("layers do not fit %dx%d, restart rate limit reached "
                                "(6 per 60 s, 2 s apart): waiting" % (key[0], key[1]))
                            limited = True
                    else:
                        limited = False
                        attempts += 1
                        log("layers do not fit %dx%d (background=%s bar=%s, need background=%dx%d "
                            "bar width %d): attempt %d/%d" %
                            (key[0], key[1], surface(st["bg"]), surface(st["bar"]),
                             st["logical"][0], st["logical"][1], st["logical"][0],
                             attempts, RETRY_CAP))
                        if ACT:
                            log("act: " + act())
                            took = settle()
                            if took is None:
                                verdict, facts = shell_after_failure()
                                if verdict == "failed":
                                    # The restart lost the shell. A retry would repeat the crash
                                    # (S1: a second stock restart leaves a black screen), so the
                                    # budget ends here and the desktop is left alone until the
                                    # size changes again or the user acts.
                                    write_failure(facts)
                                    log("act: shell restart FAILED (%s): not retrying, "
                                        "the desktop is left for the next size change or user "
                                        "action" % facts)
                                    attempts = RETRY_CAP + 2
                                else:
                                    log("act: layers still do not fit 8 s after the restart (%s)"
                                        % facts)
                            else:
                                log("act: layers fit again %.1f s after the restart" % took)
                                attempts = 0
                            hot_until = time.monotonic() + HOT_S
                            hypr_data = None
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
