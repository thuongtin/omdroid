# R11 S2 — the mobile UI starts about as fast as the desktop UI

Branch `r11/mobile-startup`, worktree `<repo>` (stream S2 of the R11 round), base `90d7494`.
Answers the owner's "mobile UI slow start" item from the R10 report: mobile hand-over
10.7-11.2 s against desktop 3.0-3.5 s on the same build.

**Result in one line:** the mobile shell ran `omamobile.quicksettings`' tile-state pass (nine serial
`timeout 3` backend probes, from `Component.onCompleted`) for ~7 s at every start — now parallel,
cached and off the start-up path — and three idle restart loops found on the way are closed. The
start-up itself did **not** get measurably faster: the marker's spread on one build is larger than
the change, and a 365 ms lazy first open rules out QML compilation as the cost. The limiter sits
inside quickshell's own start-up window and needs a profiler; that is this stream's open item.

## STATUS

| # | Step | State | Proof |
| --- | --- | --- | --- |
| 1 | Timeline instrument (evlog + process sampler), shell restart vs cold start | PASS | phase 1: two mobile cold starts and one desktop cold start on the R10 build (`p1/`), evlog + procs; `tile-state.sh` 7.13 s / 6.60 s in both mobile arms, absent in the desktop arm |
| 2 | Bisect: one omamobile plugin at a time out of the shell's plugin list | FAIL (method) | the plugin-drop arm needs a shell restart in this guest, and `omarchy-restart-shell` starts three shells per call, so its timeline mixes shells (`p5/evlog-bisect.txt`); the lazy `keepLoaded` arm gave the one usable number (sheet opens in 365 ms when compiled after boot) |
| 3 | Fix the cause, behind a switch, SOURCE.md updated | PASS | commit `3ae27b9`; `qmlformat` rc=0 on the three QML files, `sh -n` on tile-state.sh; SOURCE.md rows |
| 4 | Prove on an APK: 3 mobile + 3 desktop cold starts, alternating, target mobile within 1.5 s of desktop; gestures still pass | FAIL (target) | APK `cc12c0e3…` from `3ae27b9`, installed sha proven; mobile desktop-PASS 6.3 / 6.6 / 11.3 / 11.7 s against desktop 4.0 / 3.0 / 2.5 s — target not met, and the mobile spread (~5 s) is larger than the change; gestures: bar tap, sheet close, dock swipe-up and app open PASS, three items blocked by the switcher not closing |
| 5 | Steady state: CPU of every omamobile helper at idle over 60 s | PASS | 0 process births in 60 s idle (was: cell 5 s, call 5 s, osk 3 s); resident helpers `fit-x11.py` 0.2 % CPU, `omarchy-watch.py` 0.6 % (`p3/procs-idle.txt`, `p3/idle-ps.txt`) |
| 6 | Drawer unmapped while closed (CONTINUATION 1): ~46 MiB less with it closed, open latency ≤ 100 ms worse, gestures still pass | PENDING | commit `9f407c8`; phase 6: A = `OMDROID_DRAWER_MAPPED=1` control (buffers present), B = lazy (absent), C = tap → layer ms against the sheet as positive control, D = the gestures |

## What changed

- `rootfs/overlay/etc/phoshdroid/omamobile/plugins/omamobile.quicksettings/tile-state.sh` — the
  nine probes now run at once into per-probe files, printed in a fixed order afterwards, and the
  combined output is written to `~/.cache/omamobile/tile-state` (`OMAMOBILE_TILE_STATE_CACHE`
  overrides). Same commands, same `timeout 3` bound each; only serial became parallel.
- `…/omamobile.quicksettings/QuickSettings.qml:378-400` — the probe no longer runs from
  `Component.onCompleted`. A `FileView` reads the cache at load (a file read, no process) and a
  `Timer` runs the pass 8 s after load. `OMDROID_QS_PROBE_AT_LOAD=1` restores probe-at-load.
  Opening the sheet still re-probes through `runOpenRefresh` (`:99-120`), unchanged.
- `…/omamobile.bar/Bar.qml:95-145` — the cell and call watchers run only while the plugin they
  stream for is vendored (`omamobile.mobilenetwork`, `omamobile.call`), and their 5 s restart is
  gated the same way. Both are Omdroid stubs that exit at once, so upstream's restart-on-exit
  forked a dying process every 5 s for the whole session.
- `…/omamobile.launcher/Launcher.qml:515-548` — `omamobile-osk-watch` (a binary of the unported
  `omamobile.keyboard` plugin) and its 3 s restart run only while that plugin is vendored. It
  could not exec at all, so the timer relaunched a failing exec every 3 s.
- `…/omamobile.launcher/Launcher.qml:776-800` — the drawer window unmaps while it is closed:
  `visible: drawerAlwaysMapped || opened || warm || settle.running`; `open()` maps it and waits one
  mapped frame (24 ms) before the slide, and the dock's tap sets `warm` before its IPC summon
  (`:486-493`). `OMDROID_DRAWER_MAPPED=1` restores the always-mapped window.
- `…/omamobile/SOURCE.md` — one row per changed upstream file, with the measurement that forced it.

## Host proof

- Build from `3ae27b9`: `assembleDebug` rc=0 (58 s), `:app:test` 180 tests / 0 failed; APK sha256
  `cc12c0e3…`, 1,124,731,539 bytes, kept at `<scratch>/apk/omdroid-r11s2-3ae27b9.apk`.
- The image inside that APK is the round's `rootfs.bin` (unchanged); the build log's
  `IMAGE!=REPO start.sh` line is that difference (the image predates this round's `start.sh`,
  which S1 and S4 own) and does not matter here: the guest's `/etc/phoshdroid` is re-synced from
  the APK's guest overlay on every cold start, and all four changed files travel that way.
- `qmlformat` (host, `/usr/lib/qt6/bin/qmlformat`) rc=0 on `QuickSettings.qml`, `Bar.qml`,
  `Launcher.qml`; `sh -n` clean on `tile-state.sh`.
- The leak gate (build-machine home paths, scratch paths, the device serial, the model number)
  printed nothing before commit `3ae27b9`; this report uses `<repo>`, `<scratch>` and
  `<adb serial>`.

## Device proof

Instrument: `r11-evlog.py` (Hyprland socket2 listener, rebased on a mark file) and
`r11-procs.py` (0.1 s `/proc` poll of the session's own process family), both started from
`session.env`. Times are seconds after the instrument started (session.env is read early in
`start.sh`), event names as Hyprland reports them.

### The build under test

- Phase 1: the R10 integration build, `0.0.18`, sha256 `bef783d7…` (`<adb serial>`).
- Phase 3 (all six arms): the APK built from `3ae27b9`, sha256 `cc12c0e3…`, 1,124,731,539 B;
  `INSTALL: PASS` with the installed sha read back equal, and all four changed files sha-equal
  between the APK's `assets/guest-overlay` and the repo.

### Phase 1 — on the R10 build (the cause)

| Arm | hand-over | desktop PASS | bar | background | dock | launcher | back | marker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mobile cold 1 | 10.8 | 10.3 | 2.37 (stock bar, closes 2.43) | 2.63 | 5.55 | 9.55 | 9.55 | 9.80 |
| mobile cold 2 | 10.7 | 10.2 | 2.38 (closes 2.38) | 2.44 | 9.05 | 9.11 | 9.16 | 9.26 |
| desktop cold | 3.5 | 3.0 | 2.03 | 2.30 | — | — | — | 2.50 |

`tile-state.sh` ran 2.51 → 9.64 s in mobile cold 1 (7.13 s) and 2.51 → 9.11 s in mobile cold 2
(6.60 s); the mobile layers mapped within 0.1 s of its exit, and the desktop arm has no
`omamobile.quicksettings` and no such child. A shell restart reproduces the delay, so it is not
a cold-cache effect.

### Phase 3 — on this branch's APK, six cold starts, D M M D D M

| Arm | UI | hand-over | desktop PASS | bar | background | dock | launcher | back | marker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | D | 3.7 | 4.0 | 2.57 | 2.83 | — | — | — | 2.88 |
| 2 | M | 11.1 | 11.3 | 2.68 | 2.78 | 10.22 | 10.22 | 10.32 | 10.37 |
| 3 | M | 6.8 | 6.3 | 7.81 | 2.57 | 5.49 | 5.54 | 7.81 | 7.81 |
| 4 | D | 3.6 | 3.0 | 2.12 | 2.41 | — | — | — | 2.61 |
| 5 | D | 3.0 | 2.5 | 1.51 | 1.77 | — | — | — | 1.82 |
| 6 | M | 6.2 | 6.6 | 2.38 | 2.58 | 5.41 | 5.56 | 8.13 | 8.13 |

- **The pass is off the start-up path.** In every mobile arm `tile-state.sh` starts only with
  the 8 s timer, long after the layers are up (`procs-2`: shell 1.66 s, first `tile-state.sh`
  11.08 s) and takes 0.11 s instead of 6.6-7.1 s, so the parallel rewrite works too.
- **The pass is off the start-up path, but it was not the limiter.** In every mobile arm
  `tile-state.sh` now starts only with the 8 s timer (`procs-2`: shell 1.66 s, first
  `tile-state.sh` 11.08 s) and takes 0.11 s instead of 6.6-7.1 s. **The marker did not follow:**
  mobile marker 9.80 / 9.26 s on the R10 build against 7.81 / 8.13 / 10.37 / 10.87 s on the fixed
  build (mean 9.5 vs 9.3). Phase 1's "layers map when the pass exits" was a correlation between two
  effects of the same busy window, not causation.
- **No child process runs in the late window** (`procs-3`: shell 1.56 s, next child 10.61 s), and
  the bar/background still appear at 2.4-3.1 s as on desktop, so the 5-8 s is inside quickshell's
  own start-up (services, the full-screen wallpaper's first raster, four async panel completions)
  on the main thread.
- **Target not met, and the spread swallows the difference.** Mobile desktop-PASS on the fixed
  build: 6.3, 6.6, 11.3, 11.7 s (phase 3 arms 3/6 and phase 3 arm 2 + phase 5 control) against
  desktop 4.0, 3.0, 2.5 s. The run-to-run spread on mobile (~5 s) is larger than the change
  measured, so this round cannot claim a start-up win; it can claim the mechanism change (a 7 s
  serial fork storm and three restart loops gone from the boot path).

### Gestures, mobile arm of phase 3 (direct touch, quick swipes, `<adb serial>`)

`hc.sh j/devices` listed `touch: ["wl_touch"]`. Each item judged by its own signal, in order:

| Item | Injection | Signal | Verdict |
| --- | --- | --- | --- |
| bar tap → quick settings | tap 1600,44 | `omamobile-quicksettings` layer appears | PASS |
| sheet swipe up → close | swipe 1600,1200 → 300, 200 ms | layer gone | PASS |
| dock tap → drawer | tap 1600,1900 | `omamobile.launcher state` answered `rc=0` with no JSON; layers unchanged (the drawer is inside the launcher window) | INCONCLUSIVE |
| dock swipe-up → switcher | swipe 1600,1872 → 1400, 150 ms | `omamobile-switcher` layer appears | PASS |
| switcher swipe up → close | swipe 1600,1800 → 600, 200 ms | switcher layer still listed | NOT REPRODUCED |
| app open | `hl.dsp.exec_cmd("foot")` | `clients: foot`, `omamobile-home-strip` layer appears | PASS |
| pill swipe up → home | swipe 1600,1900 → 1500, 150 ms | no workspace change (ws 1, 1 window) | NOT REPRODUCED |
| back edge | swipe 20,1000 → 700,1000 | no change; 2 foot clients (my own second `exec`) | NOT REPRODUCED |

The three misses are one cascade, not three faults: the switcher never closed, so the pill and
back swipes landed on its full-screen overlay. R6 proved every one of these with the same
injection on the R5 build, so the likely cause is my swipe start point on the switcher, not a
regression — it needs one re-run, or a finger. Screenshots (this stream cannot see images):
`r11s2-p4-bar-tap.png`, `qs-close`, `dock-tap`, `drawer-close`, `dock-swipe-up`,
`switcher-close`, `foot-open`, `pill-short-swipe`, `back-edge`, `home`, `final` — all under
`<scratch>/p3/shots/`, PENDING-VISION.

### Steady state (phase 3, 60 s idle on the fixed build)

- **0 process births in the 60 s window** after the mark (`procs-idle.txt`: the last mark is the
  only one, and nothing starts after it). On the R10 build the same window carried the bar's
  cell watcher and call watcher every 5 s and the launcher's missing `omamobile-osk-watch` every
  3 s.
- Resident helpers: `fit-x11.py` 0.2 % CPU (etimes 124 s), `omarchy-watch.py` 0.6 % (`idle-ps.txt`).
  Nothing else in the omamobile family stays alive.

### Phase 5 — the two attribution attempts (same APK, `<scratch>/p5/`)

- **The restart-based arms are unusable.** `omarchy-restart-shell` under proot starts more than one
  shell (R5 and R10 both recorded three launches per call), and the segment boundary is a mark file
  touched just before the command, so the timeline contains layers opening at mark+0.10 s — not a
  fresh shell — and mixes two or three shells. The plugin-drop bisect and the lazy `keepLoaded` A/B
  are recorded (`evlog-bisect.txt`, `evlog-lazy.txt`) and not interpreted.
- **One solid datum came out of the lazy arm:** with `omamobile.quicksettings` and
  `omamobile.switcher` at `keepLoaded: false`, the first bar tap opened the sheet in **365 ms**
  (`first bar tap with lazy quicksettings: 365 ms`, layer list includes `omamobile-quicksettings`).
  Loading QuickSettings.qml (2139 lines + its two panels) on demand therefore costs ~0.4 s, so QML
  compilation is **not** what makes a mobile start take 5-11 s.
- The same phase's control cold start, identical build and files, marked ready at **10.87 s** against
  7.81 and 8.13 s in phase 3: the spread is real and is not a build difference.
- Consequence: the limiter is inside quickshell's start-up window (service init, the full-screen
  wallpaper's first raster, the async panel completions on the main thread), not the plugin set, its
  QML size, or an external child. Pinning it needs an instrument this stream did not build: `qs log`
  with timing categories, per-surface `WAYLAND_DEBUG` timestamps, or `perf` on the shell process.

## Switches

- `OMDROID_QS_PROBE_AT_LOAD=1` in `~/.config/omdroid/session.env` → the probe runs at load again
  (the old behaviour, for an A/B on the merged build).
- `OMDROID_DRAWER_MAPPED=1` → the launcher's drawer window stays mapped for the life of the shell
  (45.9 MiB of `wl_shm` buffers) instead of unmapping while it is closed.
- `OMAMOBILE_TILE_STATE_CACHE` → where the pass caches its output (`~/.cache/omamobile/tile-state`).

## Risks

- The sheet now starts from the previous session's cached state; a tile that changed while no
  session ran (a theme switch, a modem state) shows stale for the first 8 s or until the sheet is
  opened, which re-probes. With no cache the tiles are simply dimmed for those 8 s.
- The deferred pass still runs on the shell's own thread pool; parallel it is bounded by the
  slowest probe (3 s), not by nine serial ones.

## Not done

- **The start-up target is not met and the limiter is not yet pinned.** Next step is an instrument
  inside the shell, not another A/B: `qs log` with timing categories on a live start, per-surface
  `WAYLAND_DEBUG` timestamps (`omarchy-bar`, `omamobile-dock`, `omamobile-launcher`,
  `omamobile-back`), or `perf record` on the shell process across a cold start. Then re-test the
  candidates that remain (the wallpaper's first raster, the audio/network service probes, the
  incubator completions) one at a time.
- **The six-arm comparison needs more runs.** Four mobile cold starts on the fixed build gave
  6.3, 6.6, 11.3, 11.7 s; two on the R10 build gave 10.2 and 10.3 s. A same-hour A/B of at least
  five alternating runs per build is needed before any number here is quoted as a win.
- **Three gesture items need a re-run or a finger** (pill swipe, back edge, switcher close). The
  switcher's own close swipe is the one that failed first; the other two ran with its overlay still
  up.
- **The shell-restart A/B method is unusable under proot** (`omarchy-restart-shell` starts three
  shells). Any future bisect must use cold starts plus a per-boot build, or measure inside one
  shell with a mark taken after the shell has settled.
