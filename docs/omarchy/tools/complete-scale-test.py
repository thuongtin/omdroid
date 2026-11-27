#!/usr/bin/env python3
"""Host test (F6): the guest watcher moves the monitor to the scale the host wants.

Runs on a plain Linux host: no device, no compositor. The watcher is imported as a
module, Hyprland is a small fake that answers the watcher's own queries from a state
the fake `hyprctl eval` and `omarchy-restart-shell` change, and time is simulated
(one `sleep` = one tick), so a minute of watcher life runs in milliseconds.

Scenarios (each is its own watcher run)
  dock     scale 2 at start, the host writes ui-scale 1 at t=12 (docked on a 1920x1080
           monitor), 2 at t=45 (undocked): one scale fit and ONE shell restart each way,
           the monitor ends on the wanted scale, the marker was written once
  follow0  the same events with OMDROID_SCALE_FOLLOW=0: no scale fit, no restart
           (positive control: the same harness sees the fit in `dock`)
  nofile   no ui-scale file ever: nothing happens
  junk     the file holds 1.5, then 3, then garbage: nothing happens (integers 1 and 2 only)
  reload   a config reload puts the start-time scale back (what omdroid-ui.sh edits do):
           the watcher fits it again, up to the retry cap, and logs it

usage: complete-scale-test.py [--watch PATH] [-v]       exit status 0 = every check passed
"""
import argparse
import importlib.util
import os
import re
import sys
import tempfile
import types

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
DEFAULT_WATCH = os.path.normpath(os.path.join(
    HERE, "..", "..", "..", "rootfs", "overlay", "etc", "phoshdroid", "omarchy-watch.py"))


class Stop(Exception):
    pass


class Clock:
    def __init__(self, end, on_tick):
        self.t = 0.0
        self.end = end
        self.on_tick = on_tick

    def monotonic(self):
        return self.t

    def time(self):
        return int(self.t)

    def strftime(self, fmt):
        return "sim"

    def sleep(self, seconds):
        self.t = round(self.t + seconds, 4)
        if self.on_tick:
            self.on_tick(self.t)
        if self.t >= self.end:
            raise Stop()


class Comp:
    """The fake compositor: one monitor on the X root, layers drawn at the last shell start."""

    def __init__(self, root, scale):
        self.root = root
        self.scale = scale
        self.layer_scale = scale          # the scale the shell laid its layers out for
        self.evals = []
        self.restarts = 0

    def logical(self, scale):
        return (round(self.root[0] & ~1) / scale, round(self.root[1] & ~1) / scale)

    def monitors(self):
        return [{"name": "WL-1", "width": self.root[0] & ~1, "height": self.root[1] & ~1,
                 "scale": self.scale, "refreshRate": 120.0, "disabled": False}]

    def layers(self):
        w, h = self.logical(self.layer_scale)
        return {"WL-1": {"levels": {
            "0": [{"namespace": "omarchy-background", "w": w, "h": h}],
            "2": [{"namespace": "omarchy-bar", "w": w, "h": 44}]}}}


class FakeSubprocess:
    TimeoutExpired = TimeoutError

    def __init__(self, comp):
        self.comp = comp

    def run(self, cmd, **kw):
        res = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) > 2 and cmd[1] == "eval":
            m = re.search(r"scale = ([0-9.]+)", cmd[2])
            if m:
                self.comp.scale = float(m.group(1))
                self.comp.evals.append(cmd[2])
            else:
                self.comp.evals.append(cmd[2])
        elif cmd[0].endswith("omarchy-restart-shell"):
            self.comp.restarts += 1
            self.comp.layer_scale = self.comp.scale
        return res


def load(path, tmp, env):
    for k, v in env.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location("omarchy_watch_f6", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.RUNTIME = tmp
    mod.MARKER = os.path.join(tmp, "omarchy-ready")
    mod.LOG_PATH = os.path.join(tmp, "watch.log")
    mod.UI_FILE = os.path.join(tmp, "ui")
    mod.UI_PIN = os.path.join(tmp, "ui-pin")
    mod.UI_SCALE = os.path.join(tmp, "ui-scale")
    os.makedirs(os.path.join(tmp, "omarchy", "bin"), exist_ok=True)
    open(os.path.join(tmp, "omarchy", "bin", "omarchy-restart-shell"), "w").close()
    mod.OMARCHY = os.path.join(tmp, "omarchy")
    return mod


def run(path, events, end, follow=True, root=(3200, 1971), scale=2, reload_at=()):
    """events: [(t, text-or-None)] written to ui-scale at t (None removes the file)."""
    tmp = tempfile.mkdtemp(prefix="f6-")
    comp = Comp(root, scale)
    env = {"OMDROID_SCALE_FOLLOW": "1" if follow else "0"}
    mod = load(path, tmp, env)
    pending = list(events)
    reloads = list(reload_at)
    start_scale = scale

    def on_tick(t):
        while pending and pending[0][0] <= t:
            _, text = pending.pop(0)
            if text is None:
                try:
                    os.unlink(mod.UI_SCALE)
                except OSError:
                    pass
            else:
                with open(mod.UI_SCALE, "w") as fh:
                    fh.write(text)
        while reloads and reloads[0] <= t:
            reloads.pop(0)
            comp.scale = start_scale        # monitors.lua re-applies the start-time scale
    clock = Clock(end, on_tick)
    mod.time = clock
    mod.xroot = lambda: comp.root
    mod.signature = lambda: "sig"
    mod.hypr = lambda what, sig, timeout=2.0: comp.monitors() if what == "monitors" else comp.layers()
    mod.subprocess = FakeSubprocess(comp)
    mod.shutil = types.SimpleNamespace(which=lambda name: "/bin/" + name)
    try:
        mod.main()
    except Stop:
        pass
    log = open(mod.LOG_PATH).read() if os.path.exists(mod.LOG_PATH) else ""
    return comp, log, os.path.exists(mod.MARKER)


def check(name, ok, detail, results, verbose):
    results.append((name, ok))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  -- " + detail) if (verbose or not ok) else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", default=DEFAULT_WATCH)
    ap.add_argument("-v", action="store_true")
    args = ap.parse_args()
    res = []
    v = args.v

    # The ui-scale file is the authority, so a session starts with it equal to the env scale.
    comp, log, marker = run(args.watch, [(0.0, "2\n"), (12.0, "1\n"), (45.0, "2\n")], 80)
    scales = [re.search(r"scale = ([0-9.]+)", e).group(1) for e in comp.evals if "hl.monitor" in e]
    check("dock: marker written once the desktop is up", marker, log[:200], res, v)
    check("dock: one scale fit down and one back up", scales == ["1", "2"], "evals=%s" % scales, res, v)
    check("dock: GDK_SCALE follows in its own call",
          sum(1 for e in comp.evals if "GDK_SCALE" in e) == 2, str(comp.evals), res, v)
    check("dock: one shell restart per direction", comp.restarts == 2, "restarts=%d" % comp.restarts, res, v)
    check("dock: ends on the wanted scale, layers fit", comp.scale == 2 and comp.layer_scale == 2,
          "scale=%g layers=%g" % (comp.scale, comp.layer_scale), res, v)
    check("dock: the log names both changes", "ui-scale 2 -> 1" in log and "ui-scale 1 -> 2" in log, log[-600:], res, v)

    comp, log, _ = run(args.watch, [(0.0, "2\n"), (12.0, "1\n")], 40, follow=False)
    check("follow0: no scale fit and no restart with OMDROID_SCALE_FOLLOW=0",
          not comp.evals and comp.restarts == 0 and comp.scale == 2, "evals=%s restarts=%d" % (comp.evals, comp.restarts),
          res, v)

    comp, log, marker = run(args.watch, [], 40)
    check("nofile: nothing happens without a ui-scale file", not comp.evals and comp.restarts == 0 and marker,
          "evals=%s" % comp.evals, res, v)

    comp, log, _ = run(args.watch, [(0.0, "2\n"), (10.0, "1.5\n"), (20.0, "3\n"), (30.0, "garbage\n")], 50)
    check("junk: only the integers 1 and 2 are taken", not comp.evals and comp.restarts == 0 and comp.scale == 2,
          "evals=%s" % comp.evals, res, v)

    comp, log, _ = run(args.watch, [(0.0, "1\n")], 60, scale=1, reload_at=(15.0,))
    # start scale 1 == wanted 1: a reload to 1 changes nothing; now wanted 2 over a start scale 1
    comp2, log2, _ = run(args.watch, [(0.0, "2\n")], 60, scale=1)
    scales2 = [re.search(r"scale = ([0-9.]+)", e).group(1) for e in comp2.evals if "hl.monitor" in e]
    check("start-time scale differs from the file: the file wins once", scales2 == ["2"] and comp2.restarts == 1,
          "evals=%s restarts=%d" % (scales2, comp2.restarts), res, v)
    comp3, log3, _ = run(args.watch, [(0.0, "2\n"), (12.0, "1\n")], 70, reload_at=(30.0, 40.0, 50.0, 60.0))
    fits3 = [e for e in comp3.evals if "hl.monitor" in e]
    check("reload: a reload that undoes the scale is fitted again, capped (retry cap 3 per size)",
          2 <= len(fits3) <= 1 + 3, "fits=%d" % len(fits3), res, v)

    failed = [n for n, ok in res if not ok]
    print("\n%d checks, %d failed" % (len(res), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
