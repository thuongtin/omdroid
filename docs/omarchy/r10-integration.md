# R10 integration: memory, speed and hardware round, merged and measured

The four R10 streams merged on `r10/integration` (from `main` at 0.0.18, `3c79b08`), built
once, and measured on the tablet against 0.0.18. Stream reports: `r10-guest-diet.md` (S1),
`r10-gpu-fallback.md` (S2), `r10-image-size.md` (S3), `r10-damage.md` (S4).

## Tree and build

| Item | Value |
| --- | --- |
| Merges | `r10/image-size` (`a064dd8`), `r10/gpu-fallback` (`8ce1b6d`), `r10/guest-diet` (`97d2d9e`), `r10/aquamarine-damage` (`f2584e7`) |
| Extra commit | `3a9306d` fix(rootfs): pack the guest image with numeric root ownership (every one of the 83,316 members of the old images carried the builder's user name) |
| `termux-app` gitlink | `3e3b93a5` (16 KB link flag), a fast-forward of the fork's `phoshdroid-integration`; **not on GitHub yet** (API: no commit for that SHA), push before any release |
| Merge conflicts | none |
| Shell gates | `bash -n` on `start.sh`, `session-child.sh`, `omdroid-ui.sh`, the packager, `build-chain.sh`; `py_compile` on the watcher |
| Stream tests on the merged tree | `watch-ipc-test.py` PASS 6/6, `session-env-test.sh` PASS, `mobile-ui-test.sh` PASS |
| Gradle | `:app:test :app:lintDebug` BUILD SUCCESSFUL; 180 unit tests, 0 failed; lint 37 warnings, 0 errors |
| APK built from `f2584e7` | sha256 `bef783d7a7aa1806bd72e118ff0f68b50ad670a22d42f980fe67e86977dfa52e`, **1,124,728,775 B** (0.0.18: 1,715,790,990 B, so 34.4 % smaller) |
| Guest image | `rootfs.bin` 999,547,702 B, zstd, 68,343 members, every member owned `0/0`, 0 pruned paths left, 17,026 headers and `libc_nonshared.a` kept |
| Overlay | the APK's 68 guest-overlay files equal the repo byte for byte; inside the image `start.sh`, `session-child.sh`, `fit-x11.py`, `omarchy-watch.py`, `omarchy-plugin-index.sh`, `omdroid-ui.sh` and `lib/libaquamarine.so.13` (`35a9ffd4c5653649`) equal the repo |
| 16 KB pages | every `lib/arm64-v8a` and `lib/x86_64` library: 14 at `0x4000`, 2 at `0x10000` |
| Leak scan | `libXlorie.so` home paths 0 on all four ABIs; 0 hits in the small APK entries; 0 in the image stream |
| Host extraction of the real image | the real `AssetExtractor` over `rootfs.bin`: 17.8 s, 61,908 files plus the marker, 3,528,869,198 B, 0 skipped hard links |

## Device run 1: arms and correctness (tablet, Android 16, 4 KB pages, 23:21-23:35 UTC)

Each arm is a cold start of the R10 build with one switch in `~/.config/omdroid/session.env`,
30 s idle, per-thread CPU of the app over 10 s, two memory samples 60 s apart. The 0.0.18 row
is the baseline measured earlier the same day.

| Arm | Switch | Hand-over | Desktop | X11Server threads (10 s) | App CPU (60 s) | `hyprctl` in 10 s | Total PSS (MB) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0.18 | as shipped | 8.7 s | 8.1 s | 77.2-79.9 % | 85.8 % | 54 | 606.4 (+43.0 swap) |
| R | none, first start after install | 11.9 s | 12.1 s | 1.3 % + 1.1 % | 2.5 % | 0 | 668.3 |
| A-damage | `AQ_WAYLAND_FULL_DAMAGE=1` | 10.7 s | 10.1 s | 47.3 % (+ Thread-10 38.4 / 38.2 / 11.2 %) | 135.3 % | 0 | 715.2 |
| A-watch | `OMDROID_WATCH_LEGACY=1` | **7.1 s** | **6.6 s** | 1.2 % + 1.1 % | 2.2 % | 49 | 690.6 |
| A-malloc | `MALLOC_ARENA_MAX=` (no cap) | 10.8 s | 10.3 s | 1.3 % + 1.2 % | 2.5 % | 0 | 690.6 |
| R2 | none | 10.9 s | 10.4 s | 1.2 % + 1.1 % | 2.5 % | 0 | 688.7 |

- **Idle CPU: PASS.** The X server goes from 77-80 % of a core to about 1 % per thread, and the
  full-damage arm on the same build brings the load back (135 % for the app), so the
  committed-damage patch accounts for the saving.
- **Watcher forks: PASS.** 0 `hyprctl` processes in 10 s, 49 with the legacy switch.
- **`MALLOC_ARENA_MAX=2`: no measurable idle gain.** 688.7 MB with the cap and 690.6 MB without it.
- **Load (default arm):** typing 20 x `abcde` into foot over 10 s cost X11Server 4.8 % and the
  two renderer threads 5.3 % each; a scrolling foot cost 12.1 % and 16.6 % / 16.5 %.

Correctness against a forced full repaint (`scrdiff.py`, exact pixel compare, one run each).
**Correction (2026-11-27):** the forcing step these runs used (`debug.vfr = false`) repaints
nothing on this build, so a match here says nothing either way; the corrected check and its
result are in the note at the end of this file.

| Scenario | Changed pixels | Verdict |
| --- | --- | --- |
| idle | 0 | PASS |
| foot opened | 0 | PASS |
| foot closed | 364, bbox (141,29)-(160,58) | PASS: the bar clock turned 23:33 -> 23:34 between the shots (viewed) |
| scrolling foot, stopped | 0 | PASS |
| rotated to 2136x3035 | 0 | PASS |
| rotated back | 0 | PASS |

The watcher took each rotation with one monitor fit and no shell restart.

## Device run 2: fresh extraction and the GPU setting (23:35-23:44 UTC)

- **Fresh extraction of the R10 image** (owner guest moved aside, app re-extracted, then the
  owner guest put back): `launch: rootfs-extracted 104112ms`. The same procedure on the same
  tablet with the 0.0.17-era image took 283,904 ms (26 Nov, 16:22), so **63 % less**. That
  compares whole images: prune and codec change together. Probe PASS on the fresh guest,
  `du -sh` 3.4 G (was 3.8 G), and `yay -S cbonsai` (an AUR package that compiles C) built and
  installed in 2 m 15 s, then was removed. The owner guest is back (probe PASS).
- **EGL in the live session (Auto -> kgsl):** freedreno, `Adreno (TM) 830v1`, OpenGL ES 3.2
  Mesa 26.3.0-devel, `glClear+glFinish OK`.
- **Software GPU arm: INVALID, redone in run 3.** The script wrote the setting with a heredoc,
  and `run-as` mksh could not create its temporary file (`/data/local/...: Permission denied`),
  so that session still ran kgsl.

## Device run 3: watcher timing, software GPU, 0.0.18 in the same hour (23:56-00:12 UTC)

**Hand-over, three rounds of three arms** (cold starts of the R10 build; each session also
started a passive Hyprland event logger from `session.env`):

| Arm | Hand-over (s) | Desktop (s) |
| --- | --- | --- |
| N: shipped watcher (IPC socket) | 11.0 / 10.9 / 11.2 | 10.5 / 10.4 / 10.7 |
| L: `OMDROID_WATCH_LEGACY=1` (hyprctl every tick) | 10.8 / 10.8 / 10.7 | 10.3 / 10.3 / 10.2 |
| B: shipped watcher plus one busy core for 15 s | 9.7 / 9.7 / 9.7 | 9.2 / 9.2 / 9.1 |

The watcher costs no start-up time (run 1's 7.1 s legacy arm was an outlier). Extra CPU
load alone made the shell come up 1.2 s sooner, so start-up is bound by how fast the CPU
clocks up, not by the watcher. The event log shows where the time goes: the wallpaper layer
opens about 1.8 s into the session, while the bar and the mobile launcher open only at about
8.7 s, and the marker follows within 0.1 s.

**Software GPU setting** (`gpu_mode=software` written while the app was stopped, then
removed again):

| Check | Software | kgsl, same hour |
| --- | --- | --- |
| Host log | `gpu: preference=software kgsl-usable=true -> software source=setting` | `-> kgsl source=auto` |
| Session env | `MESA_LOADER_DRIVER_OVERRIDE=swrast`, `GALLIUM_DRIVER=llvmpipe` | `kgsl` |
| EGL in the session | `llvmpipe (LLVM 22.1.8, 128 bits)`, OpenGL ES 3.2, `glClear+glFinish OK` | freedreno, Adreno 830 |
| Cold start | hand-over 13.8 s, desktop 13.2 s, probe PASS | 11.0 s / 10.4 s |
| Idle (60 s) | Hyprland 445.6 MB PSS, 2.0 % CPU; total 929.7 MB | Hyprland about 205-212 MB; total about 690-700 MB |
| Typing into foot (10 s) | Hyprland **496.1 %** of one core (513.9 MB); total 511.5 % | Hyprland 30.9 %, app 20.1 %; total 55.5 % |

**PASS as a fallback:** a device without a usable KGSL node still gets a working desktop. It
costs about 240 MB more in Hyprland and five cores while typing, so the software path wants
the blur and shadows off before it is usable day to day.

**Memory and start-up against 0.0.18 in the same hour** (two cold starts per build:
R10, then 0.0.18 installed over it twice, then R10 again; same guest, same tablet state):

| Build | Hand-over | Desktop | Total PSS | App + X | Hyprland | Quickshell | App CPU idle | All CPU idle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R10 (a) | 10.8 s | 10.3 s | 697.3 MB | 184.3 | 211.6 | 244.9 | 2.5 % | 11.9 % |
| 0.0.18 (a) | 10.0 s | 10.3 s | 714.3 MB | 185.4 | 207.2 | 266.1 | 130.2 % | 154.1 % |
| 0.0.18 (b) | 9.7 s | 9.2 s | 694.9 MB | 184.5 | 211.0 | 243.8 | 134.0 % | 158.7 % |
| R10 (b) | 11.0 s | 10.5 s | 689.6 MB | 185.1 | 204.6 | 243.9 | 2.6 % | 12.1 % |

- **Idle memory: no change.** The two builds sit within each other's spread (689.6-697.3 MB
  against 694.9-714.3 MB). 0.0.18 now shows the same app layout as R10 (one 24.6 MB ashmem
  `LorieBuffer`, `dumpsys meminfo` 274.9-276.2 MB), so the lower baseline from earlier in the
  day was session state, not something R10 added. `MALLOC_ARENA_MAX=2` and animations off
  moved nothing measurable at idle.
- **Idle CPU: 154-159 % of a core down to about 12 %** for the whole session.
- **Start-up: R10 is 0.7-1.0 s slower to hand over** in the same hour (10.7-11.2 s against
  9.7-10.0 s); desktop 10.2-10.7 s against 9.2-10.3 s. The watcher, the damage patch
  (`AQ_WAYLAND_FULL_DAMAGE=1`, run 1), the malloc cap and the shader-cache cap (the cache is
  2.4 MB) do not explain it; the busy-core arm suggests the busier 0.0.18 clocks the CPU up
  sooner.

## Device run 4: where the cold start goes (00:14-00:17 UTC)

Six cold starts in the order M D F M D F. A single passive event logger timed each session
from the moment `omdroid-ui.sh` read `session.env`, which is about the session start. The
owner had no `ui-pin` before the run and has none after it; the final cold start passed.

| Arm | Hand-over | Desktop | First bar | Wallpaper | Mobile dock | Launcher and final bar | Marker |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M: mobile UI (the default) | 10.8 / 10.8 s | 10.3 / 10.3 s | 2.41 s, closed again at once | 2.51-2.61 s | 5.52 / 9.54 s | 9.54-9.64 s | 9.74 / 9.84 s |
| D: desktop UI (`ui-pin` = `desktop`) | **3.5 / 3.5 s** | **3.0 / 3.0 s** | 2.11-2.12 s | 2.32-2.52 s | - | - | 2.62 / 2.52 s |
| F: mobile with `AQ_WAYLAND_FULL_DAMAGE=1` | 9.9 / 9.9 s | 9.4 / 9.4 s | 2.41-2.52 s, closed again | 2.61-2.72 s | 5.32-5.42 s | 8.53-8.73 s | 8.83 / 8.83 s |

- **The mobile UI costs 7.3 s of every cold start.** In both UIs the shell is up by about
  2.5 s. In mobile mode it then closes its first bar and brings it back only with the mobile
  launcher and back layers, 7 s later. This is the largest start-up lever left, and R10 did
  not introduce it.
- **Full damage starts the mobile UI 0.9 s sooner.** That is the size of R10's gap to 0.0.18,
  so the gap comes from the CPU clocking up later when the X server is idle. It is the price
  of the idle-CPU saving, not a defect in one change; the busy-core arm of run 3 points the
  same way.
- The arms repeat to within 0.1 s, so the marker time is precise enough to bisect the mobile
  plugins one at a time.

## Device run 5: toast fades, and foot on a fresh guest (00:19-00:23 UTC)

| Check | Result |
| --- | --- |
| Toast fade x3 (`notify-send -t 2500`, judged 10 s later against a forced repaint; the step repainted nothing, see the correction above) | `changed=0` x3: PASS (not evidence). This is the case where `debug.vfr = true` left a remnant; committed damage with `vfr = false` leaves none |
| foot open and close x2 | `changed=0` x4: PASS |
| foot on the fresh R10 guest (swapped in again) | opens: a `foot` client maps, prompt `[omarchy@localhost ~]$` (viewed), foot 1.27.0 exits 0, locale `C.UTF-8`. Run 2 shot it 4 s after a 2-minute `yay` build, too early |
| Fresh guest cold start | hand-over 12.8 s (first sessions build their caches), probe PASS |

Owner guest put back (probe PASS, 10.9 s); the 3.4 G test guest was then deleted from the
tablet. `omarchy-upgraded-20261126` (the earlier round's upgraded guest) is untouched.

## Verdict

| Goal | Result |
| --- | --- |
| Faster at idle | **PASS**: session idle CPU 154-159 % of a core -> about 12 % (X server 77-80 % -> about 1 % per thread); no stale pixels in 13 forced-repaint checks (one diff was the clock turning over; those checks are corrected at the end of this file, and the corrected check on 24 scenario comparisons also found no stale pixels) |
| Faster first start | **PASS**: rootfs extraction 283.9 s -> 104.1 s; APK 1.72 GB -> 1.12 GB |
| Faster cold start | **FAIL, small**: 0.7-1.0 s slower than 0.0.18 in the same hour (CPU clocks up later). The mobile UI costs 7.3 s of every cold start (desktop UI 3.5 s); that is the next lever |
| Less memory at idle | **No change**: 689-697 MB against 695-714 MB in the same hour |
| Less storage | **PASS**: guest 3.8 G -> 3.4 G, APK -34 % |
| More hardware | **PASS on this tablet, unproven elsewhere**: software GPU draws the desktop with llvmpipe (heavy: 446 MB Hyprland, five cores while typing); 16 KB LOAD alignment in every 64-bit library (the tablet has 4 KB pages, so no 16 KB device ran it); phantom-process check logged `nothing to do` here |

## Not done in this round

- `AQ_TRACE` frame-rhythm check (S4 check 5) and three runs of every rotation scenario (one run each).
- Codec A/B on the same tree (S3 step 6): extraction compares the whole old and new images.
- `onTrimMemory` / `onLowMemory` logging was never triggered (no memory pressure applied).
- No 16 KB-page device and no non-Adreno device was available.
- Nothing is pushed: the `termux-app` commit must reach the fork before `r10/integration`
  can be merged. **Update (2026-11-27):** `3e3b93a5` is on `zweck/termux-app`
  `phoshdroid-integration` (fast-forward from `3274badd`), and `r10/integration` was released as
  0.0.19-alpha (`docs/omarchy/r10-release-0.0.19.md`).

## Correction: the stale-pixel check (2026-11-27)

The forcing step used above (`hl.config({ debug = { vfr = false } })`, `r10/device/run5.sh:23`)
produces no damaged commits when `vfr` is already false (`r11-memory.md` lines 298-317), so those
checks could not show a stale pixel. The check was redone with a step proven to repaint: a control
painted a 400x250 rectangle into the live desktop (`verify-xcorrupt`), a bare `vfr = false`
re-assert left the remnant in place, and a forcing step with damaged rects (`force_A`, about 54
rects per commit) cleared it; the control was repeated in the scenario session (TRY_OK). With that
step: 24 scenario comparisons (three toast fades, three terminal opens, three closes, three
scroll stops, three scroll closes, three rotations each way) showed `changed=0` against the forced
frame apart from the bar clock and a 24-pixel bar corner whose pixels differ by 1. Log:
`r11/verify/p9-repaint2.log` (APK `bef783d7`, the R10 build).

## Questions runs 1 and 2 left, settled by run 3

1. ~~Hand-over slower with the new watcher~~: not the watcher (run 3).
2. ~~Idle PSS higher than the 0.0.18 baseline~~: session state; 0.0.18 measures the same now (run 3).
3. ~~Software GPU on the device~~: works, heavy (run 3).
