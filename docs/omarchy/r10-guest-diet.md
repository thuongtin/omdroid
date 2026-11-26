# R10 S1: guest diet (watcher, malloc, mobile session)

Stream S1 of the R10 memory round. Worktree `proot-post-r10-guest`, branch
`r10/guest-diet`, base `bbf908d`. Host numbers here were measured on the build
machine; device claims are PENDING with the command the parent runs and what
PASS looks like.

## STATUS

| # | Step | Status | Proof |
|---|---|---|---|
| 1 | Hyprland queries over the IPC socket, not `hyprctl` forks | PASS (host) | `watch-ipc-test.py` checks (i) socket and `hyprctl` return the same snapshot and (v) the fallback answers with the socket removed; `7a32550` |
| 2 | Poll Hyprland only when something can have changed | PASS (host) | check (ii) 0 subprocesses in 120 ticks over 30 s, (iii) 15 rounds / 30 s = 0.50/s (limit 0.50), (iv) 0.00 s after a root change, (vi) marker at 0.25 s; positive control 16 forks in 2 s on the legacy path; `b5d6e1e`, `014ec35` |
| 3 | Host test harness `docs/omarchy/tools/watch-ipc-test.py` | PASS (host) | `python3 docs/omarchy/tools/watch-ipc-test.py` -> `VERDICT: PASS (6/6 checks)`, exit 0; watcher also passes `python3 -m py_compile` |
| 4 | Session environment knobs in `start.sh` (arenas, shader cache, `session.env`) | PASS (host) | `bash docs/omarchy/tools/session-env-test.sh` -> 9 PASS, `VERDICT: PASS`; block at line 121, watcher at 144; `e941011` |
| 5 | No Hyprland animations in the mobile UI | PENDING | |
| 6 | voxtype only when a model exists | PENDING | |

## What changed

### Step 1: queries over Hyprland's request socket

`rootfs/overlay/etc/phoshdroid/omarchy-watch.py`

- `socket_request(what, sig, timeout=2.0)`: one `j/<what>` request on
  `$XDG_RUNTIME_DIR/hypr/<signature>/.socket.sock`, read to EOF, parsed JSON,
  or `None` on a missing socket, a refused connect, a read timeout or a bad
  answer.
- `hypr(what, sig)`: the socket first, then the old `ctl()` (`hyprctl -j`) for
  that call, so a protocol surprise degrades to the pre-R10 behaviour.
  `OMDROID_WATCH_LEGACY=1` (module constant `LEGACY`) forces the old path.
- `ctl()` is unchanged and still serves every state-changing call
  (`hyprctl eval`, `hyprctl reload config-only`); `act()` still runs
  `omarchy-restart-shell`.
- `evaluate(root=None, hypr_data=None)` now takes the answers it should use, so
  the main loop can reuse them; with no argument it behaves as before.

### Step 2: a cadence that only asks when something can have changed

`rootfs/overlay/etc/phoshdroid/omarchy-watch.py`, `main()`

- Read `xroot()` every tick (0.25 s, in-process `XGetGeometry`, no fork).
- Query Hyprland on a tick only while the ready marker is not written, for 10 s
  after an X root size change, a UI mode change or a shell restart, until the
  first answer arrives, or on the steady heartbeat `OMDROID_WATCH_HEARTBEAT`
  (default 2.0 s). The first reading is not treated as a change.
- The monitor/layer snapshot is cached between queries, so the size and
  layer-fit decisions of the old loop are unchanged, only their input is at most
  one heartbeat old.
- `OMDROID_WATCH_LEGACY=1` restores both the old forking path and the
  query-every-tick cadence, for the device A/B.
- `settle()` and `switch_ui()` still call `evaluate()` with no argument, i.e.
  fresh queries, which is what the restart path needs.

### Step 3: host harness

`docs/omarchy/tools/watch-ipc-test.py` (new, runs on this Linux host; no device,
no compositor, no root): a fake Hyprland on `<runtime>/hypr/<sig>/.socket.sock`
answers `j/monitors` and `j/layers` with JSON shaped like Hyprland 0.56.2's
(answer captured from a live compositor), the watcher is imported with
`xroot()` monkeypatched and `time` simulated (one tick = one `sleep(0.25)`), and
`subprocess.run`/`Popen` plus the socket server are counted.

### Step 4: session environment knobs

`rootfs/overlay/etc/phoshdroid/start.sh:120-138` (one block, between the stale
ready-marker removal and the watcher launch; the GPU block is untouched)

- `export MALLOC_ARENA_MAX=2`: caps the glibc per-thread arenas. COMMON.md
  correction 3 applies: glibc sizes its arena count from the kernel CPU count,
  not the fake `cpuinfo`, so the saving is a device measurement and no number is
  quoted here.
- `export MESA_SHADER_CACHE_MAX_SIZE=128M`: the default allows 1 GB of shader
  cache in the guest home.
- No `MALLOC_MMAP_THRESHOLD_` / `MALLOC_TRIM_THRESHOLD_`: both change the glibc
  syscall pattern and every syscall is costlier under proot.
- Then `$HOME/.config/omdroid/session.env`, when present: `set -a`, source,
  `set +a`, so any plain `key=value` line there overrides the defaults above
  (`MALLOC_ARENA_MAX=` drops the cap, `OMDROID_ANIMATIONS=1`,
  `OMDROID_VOXTYPE=1`, `OMDROID_WATCH_LEGACY=1`, `OMDROID_WATCH_HEARTBEAT=1.0`).
  One line naming the file goes to the session log when it is read.
- `omdroid-ui.sh` sources the same file for the two switches it owns, because it
  runs at `start.sh:87`, before this block (see step 5).

## Host proof

```
$ python3 docs/omarchy/tools/watch-ipc-test.py
PASS (i) evaluate() is identical over the socket and over hyprctl
PASS (v) with the socket removed the hyprctl fallback returns the same snapshot
PASS (ii) 0 subprocesses in 120 ticks over 30.0 s
     control: OMDROID_WATCH_LEGACY=1 spawned 16 subprocesses in 2.0 s
PASS (iii) 15 Hyprland query rounds in 30.0 s (0.50/s, limit 0.50/s)
PASS (vi) ready marker written 0.25 s after the first tick
PASS (iv) first Hyprland query 0.00 s after the X root change
VERDICT: PASS (6/6 checks)
rc=0
```

`python3 -m py_compile rootfs/overlay/etc/phoshdroid/omarchy-watch.py` passes.
Before the change the same cadence was 8 `hyprctl` forks per second (the
positive control above measures 8 per second through the legacy switch on this
harness).

```
$ bash docs/omarchy/tools/session-env-test.sh
PASS bash -n start.sh
PASS session environment block found (19 lines)
PASS no MALLOC_MMAP_THRESHOLD_ / MALLOC_TRIM_THRESHOLD_
PASS block at line 121, watcher at 144, GPU block at 47
PASS default MALLOC_ARENA_MAX|MESA_SHADER_CACHE_MAX_SIZE|legacy|animations (values:2|128M||)
PASS no session.env: nothing sourced, no log line
PASS session.env overrides arenas and switches (values:4|128M|1|1)
PASS the read file is named in the session log line
PASS an empty MALLOC_ARENA_MAX drops the cap (values:|128M||)
VERDICT: PASS
```

## Device A/B plan (the parent runs it)

(filled at the end)

## Risks

(filled at the end)

## What I did not do

(filled at the end)
