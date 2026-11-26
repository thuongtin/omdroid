#!/usr/bin/env python3
"""Host test: the guest watcher asks Hyprland over its IPC socket, not via forks.

Runs on a plain Linux host: no device, no compositor, no root. A fake Hyprland
listens on `<runtime>/hypr/<sig>/.socket.sock` and answers `j/monitors` and
`j/layers` with JSON shaped like Hyprland's (captured from Hyprland 0.56.2:
`j/monitors` is a list of monitor dicts, `j/layers` a dict keyed by monitor name
with a `levels` map of layer-surface dicts). The watcher is imported as a module
with `xroot()` monkeypatched and `time` simulated, so 30 s of ticks run in
milliseconds.

Checks
  (i)   evaluate() returns the same snapshot over the socket as over hyprctl
  (ii)  a steady-state tick spawns no subprocess (30 s simulated)
  (iii) Hyprland is queried at most 0.5 times per second in steady state
  (iv)  the first Hyprland query after an X root change comes within 0.5 s
  (v)   with the socket removed, the hyprctl fallback still returns data
  (vi)  the ready marker is written as soon as the layers fit

usage: watch-ipc-test.py [--watch PATH] [-v]
Exit status 0 when every check passes.
"""
import argparse
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.realpath(__file__))
DEFAULT_WATCH = os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "rootfs", "overlay", "etc", "phoshdroid", "omarchy-watch.py"))
SIG = "w1"   # short: AF_UNIX paths are capped at ~108 bytes
TMP = ""


# ------------------------------------------------------------------ fixtures --
# Shapes copied from a live Hyprland 0.56.2 answer, trimmed to the keys the
# watcher reads (plus the neighbours that make a shape mismatch visible).

def monitor(width, height, scale=1):
    return [{
        "id": 0,
        "name": "WL-1",
        "description": "fake monitor",
        "make": "fake",
        "model": "fake",
        "serial": "fake",
        "width": width,
        "height": height,
        "physicalWidth": 300,
        "physicalHeight": 200,
        "refreshRate": 60.0,
        "x": 0,
        "y": 0,
        "activeWorkspace": {"id": 1, "name": "1"},
        "specialWorkspace": {"id": 0, "name": ""},
        "reserved": [0, 0, 0, 0],
        "scale": scale,
        "transform": 0,
        "focused": True,
        "dpmsStatus": True,
        "vrr": False,
        "disabled": False,
        "currentFormat": "XRGB8888",
        "mirrorOf": "none",
    }]


def layers(width, height):
    return {"WL-1": {"levels": {
        "0": [{"address": "0x1", "x": 0, "y": 0, "w": width, "h": height,
               "alpha": 1, "namespace": "omarchy-background", "pid": 1}],
        "1": [],
        "2": [{"address": "0x2", "x": 0, "y": 0, "w": width, "h": 44,
               "alpha": 1, "namespace": "omarchy-bar", "pid": 1}],
        "3": [],
    }}}


class Screen:
    """The fake compositor's answers; they follow the simulated X root."""

    def __init__(self, size, change_at=None, new_size=None):
        self.size = size
        self.change_at = change_at
        self.new_size = new_size

    def root(self, t):
        if self.change_at is not None and t >= self.change_at:
            return self.new_size
        return self.size

    def monitors(self, t):
        return monitor(*self.root(t))

    def layers(self, t):
        return layers(*self.root(t))


# --------------------------------------------------------------- fake Hyprland --

class FakeHypr:
    """A unix socket that answers j/monitors and j/layers, then closes."""

    def __init__(self, runtime, sig, screen, clock):
        self.dir = os.path.join(runtime, "hypr", sig)
        os.makedirs(self.dir, exist_ok=True)
        self.path = os.path.join(self.dir, ".socket.sock")
        if len(self.path.encode()) > 100:
            raise OSError("test runtime path too long for AF_UNIX: %s" % self.path)
        self.screen = screen
        self.clock = clock
        self.requests = []
        self.ready = threading.Event()
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(self.path)
        self.srv.listen(16)
        self.srv.settimeout(0.05)
        self._stop = False
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        self.ready.wait(5.0)

    def _serve(self):
        self.ready.set()
        while not self._stop:
            try:
                conn, _ = self.srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                try:
                    req = conn.recv(4096).decode("utf-8", "replace").strip()
                except OSError:
                    continue
                t = self.clock.t
                self.requests.append((t, req))
                if req == "j/monitors":
                    payload = json.dumps(self.screen.monitors(t))
                elif req == "j/layers":
                    payload = json.dumps(self.screen.layers(t))
                else:
                    payload = ""
                try:
                    conn.sendall(payload.encode())
                except OSError:
                    pass

    def close(self):
        self._stop = True
        try:
            self.srv.close()
        except OSError:
            pass
        self.thread.join(5.0)
        try:
            os.unlink(self.path)
        except OSError:
            pass


# -------------------------------------------------------------- simulated time --

class Stop(Exception):
    pass


class Clock:
    """monotonic/sleep over a simulated clock; every sleep is one tick."""

    def __init__(self, start, end):
        self.t = start
        self.end = end
        self.ticks = 0
        self.on_tick = None

    def monotonic(self):
        return self.t

    def time(self):
        return int(self.t)

    def strftime(self, fmt):
        return "sim"

    def sleep(self, seconds):
        self.ticks += 1
        self.t = round(self.t + seconds, 4)
        if self.on_tick is not None:
            self.on_tick(self.t)
        if self.t >= self.end:
            raise Stop()


# ------------------------------------------- subprocess and hyprctl stand-ins --

CALLS = []
SCREEN = None
CLOCK = None


def fake_run(argv, **kwargs):
    what = str(argv[-1]) if isinstance(argv, (list, tuple)) and argv else ""
    when = CLOCK.t if CLOCK is not None else 0.0
    CALLS.append((when, what, list(argv) if isinstance(argv, (list, tuple)) else argv))
    payload = ""
    if SCREEN is not None:
        answer = SCREEN.monitors(CLOCK.t) if what == "monitors" else SCREEN.layers(CLOCK.t)
        payload = json.dumps(answer)
    return subprocess.CompletedProcess(argv, 0, payload, "")


def fake_popen(*args, **kwargs):
    CALLS.append((CLOCK.t if CLOCK is not None else 0.0, "Popen", args))
    raise AssertionError("the watcher used Popen; it must not spawn processes")


# ------------------------------------------------------------------- the test --

def load_watcher(path):
    spec = importlib.util.spec_from_file_location("omarchy_watch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def simulate(w, name, size, duration=30.0, change_at=None, new_size=None):
    """Run main() against fake Hyprland for `duration` simulated seconds."""
    global CALLS, SCREEN, CLOCK
    runtime = os.path.join(TMP, name)
    shutil.rmtree(runtime, ignore_errors=True)
    os.makedirs(os.path.join(runtime, "hypr"), exist_ok=True)
    w.RUNTIME = runtime
    w.MARKER = os.path.join(runtime, "omarchy-ready")
    w.LOG_PATH = os.path.join(runtime, "watch.log")
    screen = Screen(size, change_at, new_size)
    clock = Clock(1000.0, 1000.0 + duration)
    seen = []
    clock.on_tick = lambda t: seen.append(t) if not seen and os.path.exists(w.MARKER) else None
    CALLS = []
    SCREEN, CLOCK = screen, clock
    fake = FakeHypr(runtime, SIG, screen, clock)
    queries = []
    saved_time = w.time
    real_hypr = w.hypr
    try:
        w.time = types.SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep,
                                       strftime=clock.strftime, time=clock.time)
        w.xroot = lambda: screen.root(clock.t)

        def counted(what, sig, timeout=2.0):
            queries.append((clock.t, what))
            return real_hypr(what, sig, timeout)

        w.hypr = counted
        try:
            w.main()
        except Stop:
            pass
    finally:
        w.time = saved_time
        w.hypr = real_hypr
        fake.close()
    return {
        "runtime": runtime,
        "calls": list(CALLS),
        "queries": queries,
        "socket_requests": list(fake.requests),
        "ticks": clock.ticks,
        "seconds": duration,
        "marker": os.path.exists(w.MARKER),
        "marker_at": seen[0] if seen else None,
        "start": 1000.0,
        "log": read_text(w.LOG_PATH),
    }


def read_text(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return ""


def rounds(queries):
    """Hyprland query rounds: one `monitors` request each."""
    return [t for t, what in queries if what == "monitors"]


def check_snapshots(w):
    """(i) socket and hyprctl return the same snapshot; (v) fallback works."""
    runtime = os.path.join(TMP, "sp")
    shutil.rmtree(runtime, ignore_errors=True)
    os.makedirs(os.path.join(runtime, "hypr"), exist_ok=True)
    w.RUNTIME = runtime
    screen = Screen((2560, 1440))
    clock = Clock(1000.0, 1e12)
    CALLS.clear()
    global SCREEN, CLOCK
    SCREEN, CLOCK = screen, clock
    w.xroot = lambda: screen.root(clock.t)
    fake = FakeHypr(runtime, SIG, screen, clock)
    saved_which = shutil.which
    saved_legacy = w.LEGACY
    try:
        via_socket = w.evaluate()
        shutil.which = lambda name: "/usr/bin/hyprctl" if name == "hyprctl" else None
        w.LEGACY = True
        via_hyprctl = w.evaluate()
        w.LEGACY = False
        fake.close()          # the socket is gone: only hyprctl can answer now
        fallback = w.evaluate()
    finally:
        shutil.which = saved_which
        w.LEGACY = saved_legacy
        fake.close()
    same = True
    if via_socket.get("missing") is not None:
        print("FAIL (i) socket path did not produce a snapshot: %r" % via_socket.get("missing"))
        same = False
    elif via_socket != via_hyprctl:
        print("FAIL (i) socket and hyprctl snapshots differ")
        for key in sorted(set(via_socket) | set(via_hyprctl)):
            if via_socket.get(key) != via_hyprctl.get(key):
                print("         %s: socket=%r hyprctl=%r" % (key, via_socket.get(key), via_hyprctl.get(key)))
        same = False
    else:
        print("PASS (i) evaluate() is identical over the socket and over hyprctl")
    if not same:
        return [False, False]
    if fallback.get("missing") is not None or fallback != via_socket:
        print("FAIL (v) hyprctl fallback with the socket removed: %r" % fallback.get("missing"))
        return [True, False]
    print("PASS (v) with the socket removed the hyprctl fallback returns the same snapshot")
    return [True, True]


def check_steady(w):
    """(ii) no subprocess per tick; (iii) <= 0.5 queries/s; (vi) marker on time."""
    sim = simulate(w, "st", (2560, 1440), duration=30.0)
    no_fork = True
    if sim["calls"]:
        print("FAIL (ii) steady state spawned %d subprocess(es): %r" %
              (len(sim["calls"]), sim["calls"][:3]))
        no_fork = False
    else:
        print("PASS (ii) 0 subprocesses in %d ticks over %.1f s" % (sim["ticks"], sim["seconds"]))
    # Positive control: the same counter must see the legacy path fork. Without
    # this, "0 subprocesses" could just mean the counter cannot fire.
    saved_legacy = w.LEGACY
    w.LEGACY = True
    control = simulate(w, "lc", (2560, 1440), duration=2.0)
    w.LEGACY = saved_legacy
    if not control["calls"]:
        print("FAIL (ii) positive control: the legacy path spawned nothing, so the counter proves nothing")
        no_fork = False
    else:
        print("     control: OMDROID_WATCH_LEGACY=1 spawned %d subprocesses in %.1f s" %
              (len(control["calls"]), control["seconds"]))
    rate = len(rounds(sim["queries"])) / sim["seconds"]
    slow = True
    if rate > 0.5 + 1e-6:
        print("FAIL (iii) %.2f Hyprland queries per second (limit 0.5): %d rounds" %
              (rate, len(rounds(sim["queries"]))))
        slow = False
    else:
        print("PASS (iii) %d Hyprland query rounds in %.1f s (%.2f/s, limit 0.50/s)" %
              (len(rounds(sim["queries"])), sim["seconds"], rate))
    early = True
    if not sim["marker"]:
        print("FAIL (vi) no ready marker after %.1f s" % sim["seconds"])
        early = False
    elif sim["marker_at"] is None or sim["marker_at"] - sim["start"] > 0.5:
        print("FAIL (vi) ready marker written at %r (start %.2f)" % (sim["marker_at"], sim["start"]))
        early = False
    else:
        print("PASS (vi) ready marker written %.2f s after the first tick" %
              (sim["marker_at"] - sim["start"]))
    return [no_fork, slow, early]


def check_change(w):
    """(iv) a root size change is asked about within 0.5 s."""
    change_at = 1005.0
    sim = simulate(w, "ch", (2560, 1440), duration=30.0,
                   change_at=change_at, new_size=(1920, 1080))
    after = [t for t in rounds(sim["queries"]) if t >= change_at]
    ok = True
    if not after:
        print("FAIL (iv) no Hyprland query after the X root change")
        ok = False
    elif after[0] - change_at > 0.5:
        print("FAIL (iv) first query %.2f s after the X root change (limit 0.5)" %
              (after[0] - change_at))
        ok = False
    else:
        print("PASS (iv) first Hyprland query %.2f s after the X root change" %
              (after[0] - change_at))
    if sim["calls"]:
        print("FAIL (iv) the size change spawned %d subprocess(es)" % len(sim["calls"]))
        ok = False
    return [ok]


def main():
    global TMP
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--watch", default=DEFAULT_WATCH, help="path to omarchy-watch.py")
    parser.add_argument("-v", "--verbose", action="store_true", help="print the simulated watcher log")
    args = parser.parse_args()

    watch = os.path.realpath(args.watch)
    if not os.path.isfile(watch):
        sys.exit("no watcher at %s" % watch)
    try:
        compile(open(watch).read(), watch, "exec")
    except SyntaxError as e:
        sys.exit("watcher does not compile: %s" % e)

    TMP = tempfile.mkdtemp(prefix="watch-ipc-test.")
    os.environ["XDG_RUNTIME_DIR"] = TMP
    os.environ["HOME"] = TMP
    os.environ["OMARCHY_WATCH_LOG"] = os.path.join(TMP, "watch.log")
    os.environ.pop("OMDROID_WATCH_LEGACY", None)
    os.environ.pop("OMDROID_WATCH_HEARTBEAT", None)
    try:
        w = load_watcher(watch)
    except (OSError, SyntaxError) as e:
        sys.exit("cannot import %s: %s" % (watch, e))

    saved_run, saved_popen = subprocess.run, subprocess.Popen
    subprocess.run = fake_run
    subprocess.Popen = fake_popen
    try:
        results = []
        for check in (check_snapshots, check_steady, check_change):
            results.extend(check(w))
    finally:
        subprocess.run, subprocess.Popen = saved_run, saved_popen
        if args.verbose:
            for name in ("st", "ch", "lc"):
                path = os.path.join(TMP, name, "watch.log")
                print("\n--- %s log (%s) ---\n%s" % (name, path, read_text(path)))
        shutil.rmtree(TMP, ignore_errors=True)

    passed = sum(1 for r in results if r)
    total = len(results)
    verdict = "PASS" if passed == total == 6 else "FAIL"
    print("VERDICT: %s (%d/%d checks)" % (verdict, passed, total))
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
