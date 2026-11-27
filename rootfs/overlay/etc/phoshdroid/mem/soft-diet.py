#!/usr/bin/env python3
"""Software-GPU diet (R11 S1). Started in the background by mem/session-start.sh when the
session runs on llvmpipe (OMDROID_GPU=software) and OMDROID_SOFT_DIET is not 0.

Hyprland on llvmpipe pays for every pixel it shades on the CPU, so this turns off what the
shell and the user config leave on: blur, shadows and animations. It changes the running
compositor only (`hyprctl eval`), never a dotfile, so the owner's config is untouched and
the next session starts from it again. A config reload (a theme switch) re-applies the
owner's values, so the helper listens on Hyprland's event socket and applies the diet again
after every `configreloaded`.

OMDROID_SOFT_DIET=0 turns it off; OMDROID_SOFT_DIET_LUA=<lua> replaces the settings.
Log: /tmp/omdroid-soft-diet.log (stdout of the hook's background start).
"""
import glob
import os
import shutil
import socket
import subprocess
import sys
import time

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
DEFAULT_LUA = (
    "hl.config({ decoration = { blur = { enabled = false }, shadow = { enabled = false } },"
    " animations = { enabled = false } })"
)
LUA = os.environ.get("OMDROID_SOFT_DIET_LUA") or DEFAULT_LUA


def log(msg):
    print(f"soft-diet {time.strftime('%H:%M:%S')}: {msg}", flush=True)


def find_signature(deadline):
    while time.time() < deadline:
        for sock in sorted(glob.glob(os.path.join(RUNTIME, "hypr", "*", ".socket2.sock"))):
            return os.path.basename(os.path.dirname(sock))
        time.sleep(0.5)
    return None


def apply(sig):
    exe = shutil.which("hyprctl")
    if not exe:
        log("hyprctl missing; nothing applied")
        return False
    env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=sig)
    try:
        r = subprocess.run([exe, "eval", LUA], env=env, capture_output=True, text=True, timeout=10)
    except Exception as e:  # a hung hyprctl must not end the helper
        log(f"hyprctl eval failed: {e}")
        return False
    log(f"hyprctl eval rc={r.returncode} {r.stdout.strip()[:120]} {r.stderr.strip()[:120]}")
    return r.returncode == 0


def main():
    if os.environ.get("OMDROID_SOFT_DIET", "1") == "0":
        log("off (OMDROID_SOFT_DIET=0)")
        return 0
    sig = find_signature(time.time() + 120)
    if not sig:
        log("no Hyprland instance within 120 s; giving up")
        return 1
    log(f"instance {sig}")
    for _ in range(20):  # the event socket can exist a moment before requests are served
        if apply(sig):
            break
        time.sleep(0.5)
    path = os.path.join(RUNTIME, "hypr", sig, ".socket2.sock")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(path)
    except OSError as e:
        log(f"event socket refused ({e}); the diet stays as applied once")
        return 0
    last = 0.0
    buf = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            log("event socket closed; session over")
            return 0
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.startswith(b"configreloaded") and time.time() - last > 1.0:
                last = time.time()
                time.sleep(0.3)  # let the reload finish before overriding it
                apply(sig)


if __name__ == "__main__":
    sys.exit(main())
