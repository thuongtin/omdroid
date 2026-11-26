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
| 5 | No Hyprland animations in the mobile UI | PASS (host) | `bash docs/omarchy/tools/mobile-ui-test.sh <looknfeel.lua>` -> 12 PASS, `VERDICT: PASS`: mobile idempotent (`b0f2393f`), `luac -p` ok, desktop restores the original (`d36d5ae6`); `8091f80` |
| 6 | voxtype only when a model exists | PASS (read): no change needed | `/usr/local/bin/omarchy-voxtype-daemon` exits 0 before `setsid` when no model is installed, and the image ships no model; evidence quoted below |

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

`rootfs/overlay/etc/phoshdroid/start.sh:121-139` (one block, between the stale
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
  `OMDROID_WATCH_LEGACY=1`, `OMDROID_WATCH_HEARTBEAT=1.0`).
  One line naming the file goes to the session log when it is read.
- `omdroid-ui.sh` sources the same file for the switch it owns, because it runs
  at `start.sh:87`, before this block (see step 5).

### Step 5: no animations in the mobile UI

`rootfs/overlay/etc/phoshdroid/omdroid-ui.sh`

- `looknfeel_apply` (mobile branch, after the existing rules): appends
  `hl.config({ animations = { enabled = false } })` with a three-line comment,
  unless `OMDROID_ANIMATIONS=1`. The block is still stripped and rewritten whole,
  so a second mobile run is byte-identical and `desktop` restores the original
  file byte for byte.
- `main()`: the script now reads `$HOME/.config/omdroid/session.env` itself
  (same `set -a` source as `start.sh`, guarded by `OMDROID_SESSION_ENV_READ` so
  the watcher's UI switch cannot read it twice). It has to: `start.sh:87` runs
  this script before the environment block at `start.sh:121`, so without this
  the cold start would ignore `OMDROID_ANIMATIONS=1`.
- Switch: `OMDROID_ANIMATIONS=1` in `~/.config/omdroid/session.env`. Desktop
  keeps Omarchy's own animations regardless.

### Step 6: voxtype already exits without a model (no change)

The research report named `usr/share/omarchy/bin/omarchy-voxtype-daemon`; that
file is not in the image. The command `~/.config/hypr/autostart.lua:7` runs is
`/usr/local/bin/omarchy-voxtype-daemon` (a 1.6 KB shell script). Its `start`
branch is:

```
command -v voxtype >/dev/null 2>&1 || exit 0
model_is_installed || exit 0
daemon_is_live && exit 0
... setsid ... voxtype --no-hotkey daemon
```

`model_is_installed` is `find "$HOME/.local/share/voxtype/models" -type f -size
+1M -print -quit` and the image ships **no** `.local/share/voxtype` at all (the
member list carries only `home/omarchy/.config/voxtype/config.toml`), so `start`
exits 0 before `setsid`: no resident process, so the research estimate of a
20-30 MB idle no-op is wrong and there is nothing to disable. No change made;
`OMDROID_VOXTYPE` is not introduced (it would document a switch that does not
exist). If a user installs a model later, the daemon starts normally.

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

```
$ bash docs/omarchy/tools/mobile-ui-test.sh <extracted looknfeel.lua>
PASS bash -n omdroid-ui.sh
PASS mobile block disables animations
PASS luac -p accepts the mobile file
PASS mobile applied twice is byte-identical (b0f2393f0660329b4f23ff2417ac4abc8118c60c380d5ca14624a85c052728cc)
PASS desktop restores the original bytes (d36d5ae6fe6a3b57424a26295d7b04861fcee4dd54d0403e3be6f5fe729e3273)
PASS desktop leaves no marker block
PASS OMDROID_ANIMATIONS=1 keeps the animations
PASS luac -p accepts the file without the animations line
PASS desktop restores the original bytes after the override (d36d5ae6...)
PASS session.env OMDROID_ANIMATIONS=1 is honoured by the script itself
PASS session.env read is logged
PASS desktop restores the original bytes after the session.env run (d36d5ae6...)
VERDICT: PASS
```

## Device A/B plan (the parent runs it)

Write the switch into the guest once: `~/.config/omdroid/session.env` (guest
home `/home/omarchy/.config/omdroid/session.env`, so it survives a cold start and
a reinstall; the overlay sync does not touch it). Every key is optional.

1. Watcher CPU and fork rate (steps 1-2). Switch: `OMDROID_WATCH_LEGACY=1` in
   `session.env` (old path; remove it for the new one). For each side, idle the
   desktop 30 s, then sample the watcher's own CPU and count `hyprctl`
   processes over 60 s from inside the guest:

   ```
   python3 - <<'PY'
   import os, time
   pids = [p for p in os.listdir('/proc') if p.isdigit()
           and 'omarchy-watch.py' in open('/proc/'+p+'/cmdline','rb').read().decode('utf8','replace')]
   pid = pids[0]
   def cpu(pid):
       f = open('/proc/%s/stat' % pid).read().rsplit(')', 1)[1].split()
       return (int(f[11]) + int(f[12])) / os.sysconf('SC_CLK_TCK')
   c0 = cpu(pid); t0 = time.time(); forks = 0
   while time.time() - t0 < 60:
       for p in os.listdir('/proc'):
           if p.isdigit():
               try: cmd = open('/proc/'+p+'/cmdline','rb').read()
               except OSError: continue
               if b'hyprctl' in cmd: forks += 1
       time.sleep(0.05)
   print('watcher cpu %.2fs over %.1fs, hyprctl sightings %d' % (cpu(pid)-c0, time.time()-t0, forks))
   PY
   ```

   PASS: the new side shows no `hyprctl` sightings (legacy: 8 per second, i.e.
   hundreds) and the watcher's CPU falls sharply; `/tmp/omarchy-watch.log`
   carries the one startup line with `heartbeat=2.0s legacy=off`.
2. Ready marker timing (steps 1-2): `docs/omarchy/tools/coldstart.sh` before and
   after. PASS: the marker phase is inside the pre-R10 spread (three runs each;
   a shift over the spread is a regression, not an improvement).
3. Live size change (step 2): rotate the tablet, or drive `screen.sh` to another
   size. PASS: `/tmp/omarchy-watch.log` shows the new monitor line and either
   `layers fit` or one `omarchy-restart-shell`, the bar/background come back
   within ~10 s, and the session (its apps) never restarts.
4. Guest memory (step 4): three samples per side, same wallpaper and workspace,
   `MALLOC_ARENA_MAX=2` (default) versus `MALLOC_ARENA_MAX=` (empty) in
   `session.env`. Sum `Pss` over every guest uid-1000 process from
   `/proc/<pid>/smaps_rollup`. PASS: the capped side is lower by more than the
   observed spread; report the median and min/max, never one sample.
5. Shader cache (step 4): after a session, `du -sh ~/.cache/mesa_shader_cache`
   inside the guest. PASS: it stays at or under 128 MB; the row exists to prove
   the cap reaches Mesa, not as a speed claim.
6. Animations (step 5): open/close a window and switch a workspace in `mobile`.
   PASS: transitions are instant; with `OMDROID_ANIMATIONS=1` the same actions
   animate, and `desktop` animates without the key.
7. voxtype (step 6): `pgrep -af voxtype` inside the guest after a cold start.
   PASS: nothing (no model installed). Break the glass once by creating a >1 MB
   file under `~/.local/share/voxtype/models` and confirm the daemon starts,
   then remove it.

## Risks

- The Hyprland request socket can be long enough for proot to bind it under a
  `proot-<pid>-*` name; the watcher runs inside the same proot instance, so it
  sees the same mapping `hyprctl` already uses. If a connect ever fails, every
  query falls back to `hyprctl` for that call: the pre-R10 behaviour, never
  worse, and the log shows it via nothing but slower ticks.
- A 2 s heartbeat means a genuine layer mismatch is noticed up to 2 s later than
  before; `STABLE_S` (1.5 s) and the 3-attempt cap still gate the remedy, and any
  X root change opens a 10 s window of 0.25 s queries.
- `MALLOC_ARENA_MAX=2` trades a little allocator parallelism for memory on
  thread-heavy apps (Quickshell, Hyprland). The device step measures the trade;
  `MALLOC_ARENA_MAX=` in `session.env` removes it without a rebuild.
- `MESA_SHADER_CACHE_MAX_SIZE=128M` may evict shaders sooner in very long
  sessions, costing recompiles; the 1 GB default is the worse trade on a small
  device.
- `session.env` is sourced twice per cold start when present (once here, once in
  the `start.sh` block), so it must stay plain `key=value` assignments. `start.sh`
  runs with `set -x`, so its lines also land in `/tmp/omarchy-session.log`
  (app-private): keep secrets out of it.
- `fit-x11.py` (started at `start.sh:116`) runs before the environment block, so
  it keeps the default arena count. It is one small single-purpose process.
- Killing animations changes the mobile feel on purpose; it is behind
  `OMDROID_ANIMATIONS=1` and does not touch the desktop profile.

## What I did not do

- No device and no adb: every device number is PENDING in the plan above.
- No arena or shader-cache saving is quantified: the host cannot measure them,
  and COMMON.md correction 3 forbids quoting the research number.
- No change for voxtype: its `start` already exits before spawning when no model
  is installed (step 6 evidence).
- The image's `/usr/share/omarchy`, Quickshell's render backend and
  `Background.qml`, the Kotlin host, the GPU block of `start.sh`, the X server
  and the version lines are untouched.
- No `MALLOC_TRIM_THRESHOLD_` / `MALLOC_MMAP_THRESHOLD_` (brief, and every
  syscall is costlier under proot).
- The socket path was proven on a host harness, not inside proot: the device
  item 4 watch (`hyprctl` sightings) is the proof that it connects there.
