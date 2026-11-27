# R11 S2 — the mobile UI starts about as fast as the desktop UI

Branch `r11/mobile-startup`, worktree `<repo>` (stream S2 of the R11 round), base `90d7494`.
Answers the owner's "mobile UI slow start" item from the R10 report: mobile hand-over
10.7-11.2 s against desktop 3.0-3.5 s on the same build.

**Result in one line:** the mobile start-up limiter is the launcher's **drawer window**, which stayed
mapped for the life of the shell and cost two 22.97 MiB `wl_shm` buffers (45.9 MiB) plus the raster of
a full-screen surface at every start. Unmapping it while it is closed takes the guest's ready marker
from **6.67-12.39 s to 3.10-3.18 s** (five alternating cold starts per arm, one APK) — level with the
desktop UI's 1.82-2.88 s. On the way the round also took `omamobile.quicksettings`' 7 s serial
tile-state pass off the boot path, cached its result, and closed three idle restart loops
(0 process births in 60 s idle).

## STATUS

| # | Step | State | Proof |
| --- | --- | --- | --- |
| 1 | Timeline instrument (evlog + process sampler), shell restart vs cold start | PASS | phase 1: two mobile cold starts and one desktop cold start on the R10 build (`p1/`), evlog + procs; `tile-state.sh` 7.13 s / 6.60 s in both mobile arms, absent in the desktop arm |
| 2 | Bisect: one omamobile plugin at a time out of the shell's plugin list | FAIL (method) | the plugin-drop arm needs a shell restart in this guest, and `omarchy-restart-shell` starts three shells per call, so its timeline mixes shells (`p5/evlog-bisect.txt`); the lazy `keepLoaded` arm gave the one usable number (sheet opens in 365 ms when compiled after boot) |
| 3 | Fix the cause, behind a switch, SOURCE.md updated | PASS | commit `3ae27b9`; `qmlformat` rc=0 on the three QML files, `sh -n` on tile-state.sh; SOURCE.md rows |
| 4 | Prove on an APK: 3 mobile + 3 desktop cold starts, alternating, target mobile within 1.5 s of desktop; gestures still pass | PASS on the marker, FAIL on `coldstart.sh`'s hand-over | phase 7, ten alternating cold starts on APK `5fdc257b…` (five per arm, one build, one hour): mobile ready marker **3.10 / 3.13 / 3.13 / 3.18 / 3.13 s** with the drawer unmapped against **6.67 / 6.73 / 11.41 / 11.70 / 12.39 s** with it mapped, and 1.82-2.88 s for the desktop UI. Mobile is 0.25-1.3 s from desktop on the marker (target met). `coldstart.sh`'s hand-over reads 6.1-6.2 s for mobile against 3.0-3.7 s for desktop, but it polls `dumpsys activity` at ~2 s resolution; gestures: bar tap, sheet close, dock swipe-up, app open PASS, three items blocked by the switcher not closing (re-run in phase 8) |
| 5 | Steady state: CPU of every omamobile helper at idle over 60 s | PASS | 0 process births in 60 s idle (was: cell 5 s, call 5 s, osk 3 s); resident helpers `fit-x11.py` 0.2 % CPU, `omarchy-watch.py` 0.6 % (`p3/procs-idle.txt`, `p3/idle-ps.txt`) |
| 6 | Drawer unmapped while closed (CONTINUATION 1): ~46 MiB less with it closed, open latency ≤ 100 ms worse, gestures still pass | PASS | commit `9f407c8`, APK `5fdc257b…`: three 23528K (22.97 MiB) `wayland-shm` mappings with the drawer mapped and **none** with it unmapped (four cold starts, two pairs); session PSS Quickshell 208/207 → 138 MB, Hyprland 269 → 178 MB; open latency 137-213 ms (one 1036 ms outlier, open item below) against a 192 ms sheet control; the drawer's settled frame viewed by the parent — clean, 19 icons in five uniform rows, first row complete, no 3× or cropped icon, no torn region (a one-frame 3× flash would need a higher-rate capture to exclude); gestures: bar tap, sheet close, drawer open and close, dock swipe-up, app open PASS |

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
  own start-up. Phase 7 shows which part: the launcher's drawer window, mapped for the life of the
  shell (below).

### Phase 7 — the drawer window is the limiter (ten alternating cold starts, one APK)

Same APK (`5fdc257b…`, commit `9f407c8`), same hour, `A` = `OMDROID_DRAWER_MAPPED=1` (the R10
behaviour, drawer mapped from start), `B` = the drawer unmapped while closed. Order A B B A A B B A A B.
Each arm's setting was read back from the live layer list after the start (`drawer=mapped` /
`drawer=unmapped`), so the arm identity is measured, not assumed.

| arm | drawer | hand-over | desktop PASS | ready marker |
| --- | --- | --- | --- | --- |
| 1 A | mapped | 13.1 | 13.4 | 12.39 |
| 2 B | unmapped | 6.1 | 6.7 | 3.10 |
| 3 B | unmapped | 6.1 | 6.7 | 3.13 |
| 4 A | mapped | 8.0 | 7.4 | 6.67 |
| 5 A | mapped | 12.8 | 12.3 | 11.70 |
| 6 B | unmapped | 6.1 | 6.6 | 3.13 |
| 7 B | unmapped | 6.2 | 6.8 | 3.18 |
| 8 A | mapped | 12.5 | 11.9 | 11.41 |
| 9 A | mapped | 8.1 | 7.5 | 6.73 |
| 10 B | unmapped | 6.1 | 6.8 | 3.13 |

- **The two arms do not overlap**: marker 3.10-3.18 s (median 3.13) unmapped against 6.67-12.39 s
  (median 11.41) mapped. The drawer window's mapping is the mobile start-up limiter, and it is the
  same window the memory stream measured at 45.9 MiB.
- Desktop UI on the same build: marker 1.82 / 2.61 / 2.88 s (phase 3/5). Mobile unmapped is 0.25-1.3 s
  from that — the brief's 1.5 s target met on the marker.
- `coldstart.sh`'s hand-over stays 6.1-6.2 s in every B arm and 8.0-13.1 s in every A arm against
  3.0-3.7 s for desktop: that metric polls `dumpsys activity activities` at ~2 s resolution and is
  not the user-visible frame; the guest's own marker is.
- The mechanism is the same one that made the panel-QML hypothesis fail: a full-screen layer surface
  (1600x941 logical = 3200x1882 px at scale 2) with two shm buffers has to be allocated, filled and
  handed to the compositor while the shell is still starting; nothing external waits.

- The earlier build (`3ae27b9`, phases 3 and 5) still had the drawer mapped, which is why its mobile
  arms spread 6.3-11.7 s; those numbers are the A arm of phase 7 seen through a noisier instrument
  (no per-arm setting read back). They are kept as the history, not as the verdict.

### Phase 8 — the drawer's memory, latency and gestures (APK `5fdc257b…`)

Memory: `mem-attrib-smaps.sh` from the memory stream (read-only), one snapshot 20 s after each
cold start. `A` = `OMDROID_DRAWER_MAPPED=1`, `B` = unmapped while closed. Order A B A B.

| arm | drawer | Quickshell PSS | Hyprland PSS | 23528K `wayland-shm` mappings |
| --- | --- | --- | --- | --- |
| 1 A | mapped | 208141 kB | 268838 kB | 3 |
| 3 A | mapped | 206753 kB | 268858 kB | 3 |
| 2 B | unmapped | 137901 kB | 177600 kB | 0 |
| 4 B | unmapped | 137625 kB | 177608 kB | 0 |

- The 23528K rows (22.97 MiB) are the drawer's two buffers the memory stream measured; one of them
  is mapped twice in Quickshell. They are present in every mapped arm and absent in every unmapped
  one — the mapped arm is the instrument's control.
- Session PSS drops by ~68 MiB (Quickshell) and ~89 MiB (Hyprland) with the drawer unmapped. Not all
  of that is the 23528K mappings: opening the drawer in a B session adds 32.5 MB to Hyprland with no
  new ≥20 MB row (its shadow buffers), and a close leaves ~20 MB of built drawer state in Quickshell.
  The 52.2 MB anonymous block in Hyprland is present in **both** arms, so it is not the drawer (it is
  the memory stream's open item).
- Three states in one B session: closed 137625 / 177608 (no 23528K rows) → drawer opened 138085 /
  210116 → closed again 158877 / 175888. Unmapping frees the compositor's side at close; Quickshell
  keeps the drawer's built scene graph until the next session.

Open latency (device clock: `date +%s%3N` immediately before the injected tap, against the evlog's
`openlayer` epoch): dock tap → drawer layer mapped **1036 / 213 / 137 ms** (the first tap after a
close is an outlier), bar tap → sheet layer **192 ms** (positive control: same instrument, also a
lazily loaded panel). The layer maps during the `omarchy-shell` summon IPC that the always-mapped
build pays as well; the only added cost is the 24 ms pre-map frame.

Gestures, each from a verified clean layer list:

| item | signal | verdict |
| --- | --- | --- |
| bar tap | `omamobile-quicksettings` layer appears | PASS |
| sheet swipe up | sheet layer gone | PASS |
| dock tap | `omamobile-launcher` layer appears | PASS |
| drawer swipe down | drawer layer gone (unmapped again) | PASS |
| dock swipe-up | `omamobile-switcher` layer appears | PASS |
| switcher swipe up | switcher still listed | not a documented gesture — R5 closes it by tapping a card or the Home button; recorded, not a regression |
| app open (`foot`) | client `foot` + `omamobile-home-strip` | PASS |
| pill short swipe | recents opened instead of home | the documented injected-swipe hazard (R5: injected moves arrive ~0.4 s apart, so a slow swipe reads as a pause and opens recents) |
| back edge from x = 20 | no change | needs the R5 byte-logger window to prove Escape; untested here (a second `foot` of my own opened, ws 1, 2 windows) |

Screenshots under `<scratch>/p8/shots/`. **`r11s2-p8-drawer-open.png` was viewed by the parent** (this
stream cannot see images): "a clean drawer — header 'Apps', 19 app icons in five rows on a uniform grid,
the first row complete (Basecamp, Chromium, Discord, Disk Usage, Docker, Document Viewer), every icon the
same size and correctly positioned, no 3× oversized or cropped icon, no empty band where icons should be,
no torn region; the search field and the extra-key bar both correct." Recorded with its caveat: a settled
frame proves the grid settles correctly and does not by itself prove a single frame was never drawn at the
wrong scale — that would need a higher-rate capture. The rest stay PENDING-VISION: `bar-tap`, `qs-close`,
`drawer-closed`, `dock-swipe-up`, `switcher-close`, `foot-open`, `pill-short-swipe`, `back-edge`, `final`.

### Phase 6 — partial (two instrument bugs, recorded so they are not repeated)

- `timeout 120 adb_ shell …` cannot work: `adb_` is a shell function, so `timeout` answers
  `failed to run command 'adb_'` and every smaps capture came back as one line. Run the function
  directly; `timeout` only wraps external commands.
- The latency post-processor unpacked three values from a two-field tap file; it raised
  `ValueError: not enough values to unpack` and wrote no latency at all.
- Its gesture rows ran with the quick-settings sheet still open (the latency control's `KEYCODE_BACK`
  does not close a layer-shell panel), so the dock tap landed on the sheet. The gesture matrix is
  re-run from a clean state in phase 8.
- What survived: the same-build A/B on the ready marker (13.7 s mapped vs 3.7 s unmapped, n=1) and
  the confirmation that both arms ran the setting they were given (`drawer mapped` / `drawer
  unmapped` read from the live layer list 6 s after the start).

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

- **The visual check on unmapping** (the defect that made upstream keep the window mapped) is answered
  for the settled frame: the parent viewed `r11s2-p8-drawer-open.png` — clean drawer, 19 icons in five
  uniform rows, first row complete, no 3× or cropped icon, no torn region, search field and key bar
  correct. **Not** answered: whether a single frame was ever drawn at the wrong scale; that needs a
  high-rate capture of a drawer opening.
- **Open item, not a blocker: the 1036 ms first dock tap** in phase 8 (taps 2-3: 213 and 137 ms). It is
  the first tap after a five-process `smaps` walk, which reads ~2 200 mappings per process inside the
  app's own cgroup on this box; the two fast taps followed an idle tablet. Read it as contention from the
  instrument, not from the drawer path — a clean repeat on an idle box would confirm it, and the sheet
  control (192 ms, also a lazy panel) shows the same instrument sees no such cost when it is not being
  hammered.
- **`coldstart.sh`'s hand-over metric is quantised at ~2 s** (one `dumpsys activity activities` per
  poll); the guest's ready marker is the precise signal this round used. A true hand-over number needs
  the display activity's first frame.
- **Two gesture items are unresolved as measurements, not as defects**: the switcher has no close
  swipe in the R5 recipe (tap a card or the Home button), and the injected pill swipe reads as a pause
  and opens recents. Both need the R5 recipes or a finger.
- **Still open from the memory stream, untouched here**: the 52.2 MB anonymous block in Hyprland,
  present in both arms of this stream's A/B too.
