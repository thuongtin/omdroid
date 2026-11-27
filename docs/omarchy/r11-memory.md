# R11 S1: memory, and a software-GPU mode a phone can live with

Branch `r11/memory` (from `90d7494`). Stream S1 of R11. Evidence labels: **measured**, **read**,
**estimated**. Every device number was taken on the tablet; every A/B is in the same hour.

## STATUS TABLE

| # | Step | Status | Proof |
| --- | --- | --- | --- |
| 1 | Attribution (R10 build, Quickshell + Hyprland + app) | PASS | tables below; device phase 1, log `<scratch>/mem/phase1.log`, rows `<scratch>/mem/phase1/attrib/rows.txt` |
| 2 | Quickshell fixes (through `mem/`) | PASS (memory), fidelity noted | `47e1aee`: wallpaper `sourceSize`: Quickshell wallpaper block 77.7 -> 26.3 MiB, Quickshell heap 143.2 -> 91.3 / 92.3 MB in both candidate arms (phase 2, below); picture unchanged to my eye, fine-detail energy 36 % lower (measured, below); `OMDROID_MEM_QML=0` restores the file |
| 3 | aquamarine swapchain 3 -> 2 (`AQ_WAYLAND_SWAPCHAIN`) | PASS on memory, CPU and commit rhythm; correctness by before/after frames (no working repaint control) | `f97dda7`: -12.0 MB in Hyprland and -12.0 MB in the app in all candidate arms; typing CPU -6.3..-9.5 points, scrolling -3.2..-6.7 (timed windows, 4 arms); commit rhythm idle 604 vs 610, scrolling 375 vs 337 (not lower), ring never exhausted (the trace line is live: 1,859 cap lines); cold start +0.3 s. Correctness: the forced-repaint step did NOT repaint (0 damaged commits of 256 and 233), so the "0 changed" table proves nothing about remnants; compared with the frame before the event instead: window open+close 0 px, toast area clean (bar shows clock and an unread badge), the phase 2 rotation residual did NOT reproduce: 8 round-trip comparisons on both builds (C B B C, phase 7) differ only in the bar (clock, wifi icon), the wallpaper is pixel-identical |
| 4 | Hyprland extras (logo, cursor, render options) | NOTHING TO CUT, 52 MiB block unattributed | read: logo, splash and blur and shadows are off in the image config (`default/hypr/looknfeel.lua`), `XCURSOR_SIZE` 24; read-back in a live session: `damage_tracking` 2, `direct_scanout` 0, border 0, rounding 0. The 52 MiB Hyprland anonymous block is not the ring and I have no lever for it (a guess, not tested: two monitor-size render targets of 24 MiB each) |
| 5 | Software-GPU diet (`OMDROID_GPU=software`) | DIET FAIL, REVERTED `41e272f`; one lead with a measurement, not shipped | `70fef09`: blur, shadows and animations already read `false` before the diet (phase 3, 4 arms): typing Hyprland CPU 448-498 % with the diet, 474-520 % without. Typing costs 8 llvmpipe workers at 60-69 % each. Levers: `LP_NUM_THREADS` 2/4 sit at 197/384 % (not a fix), `vfr` -25..-30 % (risk, not shipped), the rest nothing. **Lead (phase 6, one session per arm): a quarter of the pixels (X root 1600x984 at scale 1 instead of 3200x1970 at scale 2) types at 147 % against 455 %, Hyprland -254 MB, session -400 MB, desktop intact (viewed); needs a smaller X-server surface in software mode, a host change handed to the parent.** The intermittent high-CPU state of phase 5 (4 of 4 sessions) did not recur in 3 of 3 default-thread sessions of phases 6 and 7 and is unexplained |
| 6 | Optional: `TERMUX_X11_FORCE_FLIP=1` (report only) | NO EFFECT EXPECTED (read), not run | `termux-x11/app/src/main/cpp/lorie/InitOutput.c:799-803`: `loriePresentFlip` returns FALSE for a pixmap with `priv->mem` (cage's MIT-SHM frames, the only kind this chain presents) before the `TERMUX_X11_FORCE_FLIP` test is reached, and the flag is read by the in-process X server through `getenv`, so only the host app could set it; the check at 799 also compares `root.width` with `drawable.height` |

## Step 1: attribution on the R10 build (measured)

Build under test: the R10 integration APK (`versionName 0.0.18-alpha`, sha256 `bef783d7...`), mobile
UI, kgsl, a cold start, 60 s settle, then three `smaps_rollup` snapshots 60 s apart and one
per-mapping `smaps` dump (`docs/omarchy/tools/mem-attrib-smaps.sh` + `mem-attrib.py`).

Session total (median of 3): **698.7 MB PSS** (698-699), private dirty 332.6 MB, swap PSS 0.1 MB,
idle CPU **12.3 %** of one core. `dumpsys meminfo` of the app: TOTAL PSS 273-282 MB, Graphics
115.8-118.6 MB, EGL mtrack 90 MB.

| component | PSS MB | private dirty MB |
| --- | --- | --- |
| host app + X server | 185.8 | 68.1 |
| Hyprland | 207.1 | 80.5 |
| Quickshell | 248.7 | 154.4 |
| cage | 17.6 | 2.6 |
| watcher / fit-x11 / broker / dbus / other | 10.7 / 6.9 / 12.5 / 2.8 / 6.6 | |

### Quickshell (248.7 MB PSS, 735 mappings)

| class | PSS MB | note |
| --- | --- | --- |
| heap and anon | 142.4 | of which **one 77.7 MiB block**: the wallpaper (below) |
| memfd (`wayland-shm`) | 44.7 | the layer surfaces' buffers; each is shared with Hyprland (each side shows half) |
| libs: Qt | 36.6 | Gui, Qml, Quick, Core, QuickTemplates2 |
| libs: other | 13.6 | |
| other files | 6.4 | quickshell binary 5.2 |
| QML caches | 2.8 | |
| font files | 1.0 | 4 mappings |

Largest mappings: 77.7 MiB anon (rw-p, size 78.0), then `/memfd:wayland-shm` 24.1 + 23.0 + 23.0
MiB (RSS), `libQt6Gui` 6.2, `libQt6Qml` 5.7, `libQt6Quick` 5.6, `quickshell` 5.2, `JSGCHeap:QtQml` 3.9.

**The 77.7 MiB block is the wallpaper.** `current/background` is `0-winding-road.webp`, 6016 x 3384
(read: `file` on the image copy) = 20.36 Mpx x 4 B = 77.7 MiB exactly. `Background.qml` loads it with
`Image { source; fillMode: PreserveAspectCrop; cache: true }` and no `sourceSize` (read:
`shell/plugins/background/Background.qml`), so the software scene graph holds the full decode. The
screen is 3200 x 1970 (6.3 Mpx, 24 MiB).

### Hyprland (207-208 MB PSS, 700 mappings)

| class | PSS MB | note |
| --- | --- | --- |
| heap and anon | 70.4 | **one 52.2 MiB anon block** (rw-p, 53 MB), a 7.0 and a 3.7 MiB block |
| memfd `wayland-shm` | 38.1 | the client layer buffers (Quickshell's), other half |
| memfd `aquamarine-shm` | 36.1 | **3 frame buffers**, 24.1 MiB each, other half is in the app |
| libs: Mesa / GL / LLVM | 30.4 | `libLLVM.so.22.1` 17.0 (file pages), `libgallium` 6.6, `libglslang` 1.9 |
| libs: other | 16.9 | 504 mappings |
| other files | 11.1 | the Hyprland binary 10.1 |
| GPU kgsl | 4.2 | 69 mappings |
| font files | 0.8 | |

The 52.2 MiB block is not aquamarine's (read: patch 0001 allocates no heap frame buffer) and not
a logo or wallpaper texture (`misc.disable_hyprland_logo = true`, `disable_splash_rendering = true`
in `default/hypr/looknfeel.lua`, read). Its owner is Hyprland itself; the swapchain A/B in step 3
shows whether it scales with the ring.

### App process (183.7 MB PSS, 696 mappings)

| class | PSS MB | note |
| --- | --- | --- |
| heap and anon | 43.6 | ART and native heap |
| `aquamarine-shm` | 36.1 | the same 3 frame buffers, this half |
| other files | 34.9 | `wlroots-*` 24.1 MiB (cage's x11 output buffer, 12.0 here + 12.0 in cage), base.apk 17 |
| GPU kgsl (CPU-mapped) | 26.7 | one 24.2 MiB mapping |
| ashmem `LorieBuffer` | 24.1 | one 24.1 MiB buffer mapped twice |
| libs and other | ~12 | |

### cage (17.6 MB PSS): the `wlroots-*` buffer 12.0, everything else under 2 MB. Nothing to cut.

### Layer surfaces and their buffers (`hc.sh j/layers`, logical px; monitor 3200 x 1970 at scale 2, so a buffer is 4x the logical area x 4 B)

| layer | logical size | buffer MiB | note |
| --- | --- | --- | --- |
| `omarchy-background` | 1600 x 985 | 24.06 (1 buffer) | static wallpaper, full screen |
| `omamobile-launcher` (drawer) | 1600 x 941 | **22.97 x 2 = 45.9** | `visible: true` for the life of the shell, Launcher.qml:751 |
| `omamobile-dock` | 1600 x 96 | 2.3 | |
| `omarchy-bar` | 1600 x 44 | 1.07 | |
| `omamobile-back` x 2 | 77 x 941 | 1.1 each | |
| frame buffers (aquamarine) | 3200 x 1970 | 24.06 x 3 = 72.2 | Hyprland + app |
| cage output (`wlroots-*`) | 3200 x 1970 | 24.06 | cage + app |
| `LorieBuffer` (ashmem) | 3200 x 1970 | 24.06 | app |
| kgsl CPU-mapped | 3200 x 1970 | 24.2 | app |

Every full-frame buffer in the session: 72.2 + 24.1 + 24.1 + 24.2 + 24.1 (background) + 45.9 (drawer)
= **214.6 MiB of the 698.7 MB**, plus the 77.7 MiB wallpaper decode.

### The four suspects of the brief

| suspect | verdict |
| --- | --- |
| wallpaper decoded at its source size | **confirmed**: 77.7 MiB, 6016 x 3384 webp, saving about 53 MiB if decoded at the screen size |
| full-screen mobile layers mapped while invisible, double-buffered | **partly**: the drawer holds two 22.97 MiB buffers (45.9 MiB, 11.5 MiB of PSS per side) and stays mapped by design (S2's tree); the back edges are 77 px strips, so not an issue |
| CJK font faces | **refuted**: font files are 0.6-1.0 MB PSS in every process |
| software scene graph (`QT_QUICK_BACKEND=software`) | **real but not separable**: it is why the shell has `wayland-shm` buffers instead of GPU ones; both branches of `omarchy-launch-shell` set it (read) |

## Phase 2: candidate against the R10 behaviour, same hour (measured)

Candidate APK `omdroid-mem-47e1aee.apk` (sha256 `4e89a89b...`, built from `47e1aee`), installed over
the R10 build on the tablet; arm C = as shipped, arm B = the R10 behaviour through the switches
(`OMDROID_MEM=0`, `AQ_WAYLAND_SWAPCHAIN=3`). Order C1, B1, B2, C2, 01:01-01:10 on one clock. Every
arm: cold start, 30 s settle, two `smaps_rollup` snapshots 60 s apart (median and range of the two).
Arm identity read back from the process in each arm: Hyprland environment, `aquamarine-shm`
mapping count (3 in B, 2 in C), `Background.qml` carrying `wallpaperPixels` (4 lines in C, 0 in B),
`session.env`.

| arm | session PSS MB (range) | SwapPss MB | app | Hyprland | Quickshell | idle CPU % of one core | `dumpsys meminfo` app TOTAL PSS / Graphics MB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | **630.6** (630-631) | 0.2 | 172.1 | 188.4 | 214.2 | 12.5 | 275.4 / 128.8 |
| B1 | **683.8** (683-684) | 0.2 | 184.2 | 200.3 | 243.4 | 12.5 | 287.5 / 128.9 |
| B2 | **689.3** (686-693) | 0.2 | 183.6 | 206.1 | 243.6 | 12.1 | 273.7 / 115.7 |
| C2 | **610.7** (609-612) | 0.2 | 170.6 | 178.5 | 205.7 | 12.2 | 261.6 / 116.0 |

**Saving, candidate minus R10: C 610.7-630.6 MB against B 683.8-689.3 MB, so -53.2 MB (C1 - B1) and
-78.6 MB (C2 - B2); the ranges do not overlap.** Idle CPU is unchanged (12.1-12.5 % in every arm).

Where it comes from (PSS per class, `mem-attrib.py` over the per-mapping dumps of each arm):

| part | B1 | B2 | C1 | C2 | candidate minus R10 |
| --- | --- | --- | --- | --- | --- |
| Hyprland `aquamarine-shm` (frame buffers) | 36.1 | 36.1 | 24.1 | 24.1 | **-12.0** (3 -> 2 buffers) |
| app `aquamarine-shm` | 36.1 | 36.1 | 24.1 | 24.1 | **-12.0** |
| Quickshell heap and anon (the wallpaper decode) | 143.2 | 143.3 | 91.3 | 92.3 | **-51.9 / -51.0**; the block itself 77.7 -> 26.3 MiB (-51.4) |
| Quickshell + Hyprland `memfd` `wayland-shm` (layer buffers) | 82.8 | 82.8 | 105.8 | 82.9 | **+23.0 in C1, 0 in C2** |
| Hyprland heap, libs, GPU; app heap, ashmem, kgsl | unchanged to 0.5 MB | | | | 0 |

The deterministic saving is therefore **75.4 MB** (24.0 ring + 51.4 wallpaper). The -53.2 pair is
that minus one extra 23.0 MiB `wl_shm` buffer that Quickshell's layer held in session C1 (estimated,
not isolated: the buffer count of a Qt layer surface depends on the order buffers are released, so it
can change from session to session; the size equals one drawer buffer). That variance is not ours: it is
in the shell's own tree (S2's omamobile launcher and the stock background), so the parent should
expect +-23 MB around the saving until the shell's buffer count is pinned. The remaining -3 MB in
C2 - B2 is spread over small classes.

The 52 MiB Hyprland anonymous block is **not** the ring: it reads 52.2 / 52.2 (B) and 51.6 / 52.5
(C), so step 3 does not touch it (attribution is open, step 4).

### Correctness (measured, forced-repaint method of `damage-and-frame-pacing.md`; candidate arm)

Each scenario: settle 3 s, screenshot, re-assert `debug.vfr = false` (a full repaint), settle 3 s,
screenshot, `scrdiff.py`.

| scenario | changed pixels | max diff |
| --- | --- | --- |
| idle | 0 | 0 |
| `foot` window opened | 0 | 0 |
| `foot` window closed | 0 | 0 |
| toast faded (6 s after a `notify-send`) | 0 | 0 |
| rotated (`screen.sh rot 0`) | 0 | 0 |
| rotation reset | 0 | 0 |

Positive controls (host-side, on the same shots): the toast really drew (I looked at
`toast-up.png`: a framed popup "r11-toast / toast fade check" at the top right, and 168,813 px differ
from the faded frame); `scrdiff` reads 5,809,341 changed pixels between the idle shot and the
`foot`-open shot, so the instrument sees a window; two sessions of the same build differ by 343 px,
all in the clock (bbox 141-161 x 29-58). The clock is the only changed region in the repaint diffs
too, and none showed it changing.

### Wallpaper fidelity (measured and looked at)

My own look at 800 px thumbnails (`p2-C2.png`, `p2-B2.png`; the first pass of these image checks
returned no image and the lines below are from the second, with the images in front of me): the same
wallpaper, bar and key row, a search bar at the bottom, no black band, no popup in either. At 1:1 on the
deer and ridge crop (`[300,1150,1100,1450]`) I cannot tell the two apart by eye. Measured, on the
wallpaper area of the same screenshots: the candidate differs from the original decode by a mean of
0.52 levels (99th percentile 5), 0.44 % of pixels differ by more than 8 levels. The fine-detail
energy is lower: Laplacian variance 74.4 against 117.1 (mean horizontal gradient 0.747 against
0.846). Against a reference built from the source image (centre-cropped, PIL Lanczos / box / triangle
filters) the original decode reads like an area-filtered downscale (117 against 107 / 116) and the
candidate is softer, close to a triangle filter (54), but its mean error against the Lanczos
reference is the same as the original's (0.90 against 0.92). Trade-off: a slightly softer wallpaper
for 51 MiB. `OMDROID_MEM_QML=0` puts the original file back.

### Load (measured, one sample per arm, interval ASSUMED: re-measured with timed windows in phase 3)

Typing (20 x `input text abcde`, 0.5 s apart) and a scrolling `foot`, CPU % of one core, B1 then C2:
typing app 16.5 / 13.5, Hyprland 27.4 / 22.9, session 48.8 / 41.3; scrolling app 54.6 / 52.1,
Hyprland 87.3 / 82.3, session 175.2 / 169.0. The candidate is not worse in any component, but the
windows were timed as 12 s and 10 s by assumption and each arm has one sample: relative only.

Cold start (one run each, `coldstart.sh`): C1 12.1 s hand-over / 11.6 s desktop, B1 10.8 / 10.2,
B2 11.0 / 10.5, C2 3.6 / 17.4. The C1 run is the first start after the install (overlay sync) and
C2 is not explained by anything I changed (a hand-over at 3.6 s and a desktop at 17.4 s, with the
same process set); phase 3 repeats the cold start in alternation.

## Phase 3: ring load and commit rhythm, software-GPU diet (measured, tablet, 01:33-01:50, one session of arms)

Same candidate APK as phase 2. Every CPU window is timed from the start of one snapshot to the start
of the next (9.6-11.0 s typing, 10.4-10.6 s scrolling on kgsl, 60.5-60.7 s idle); typing is 20 x
`input text abcde` 0.5 s apart into a full-screen `foot`; scrolling is `foot` printing `seq 1 60`.

### Step 3 on kgsl (candidate C against R10 behaviour B, C B B C)

| arm | typing session CPU % (app / Hyprland) | scrolling session CPU % (app / Hyprland) | cold start hand-over / desktop s |
| --- | --- | --- | --- |
| KC1 | **41.5** (13.7 / 22.5) | **161.7** (50.3 / 78.5) | 12.0 / 11.5 |
| KB1 | 51.0 (17.0 / 29.0) | 164.9 (50.9 / 81.7) | 11.9 / 11.4 |
| KB2 | 51.0 (17.5 / 28.2) | 167.2 (51.8 / 82.3) | 11.4 / 10.9 |
| KC2 | **44.7** (15.0 / 24.5) | **160.5** (50.1 / 77.7) | 11.7 / 11.2 |

Candidate minus R10: typing **-6.3 to -9.5 points of one core** (41.5-44.7 against 51.0), scrolling
-3.2 to -6.7 (160.5-161.7 against 164.9-167.2). The ring of two costs no CPU; it saves some. Idle
PSS is as in phase 2 (a 12.0 MB ring saving in Hyprland and in the app). Cold start: candidate 11.5 /
11.5 / 11.2 s desktop (three starts, counting the trace arm), R10 11.4 / 11.1 / 10.9: **+0.3 s**,
inside the 0.5 s spread of each arm. The 17.4 s start of phase 2 (C2) did not repeat in 11 starts.

**Commit rhythm** (`AQ_TRACE`, `/etc/phoshdroid/trace`, Hyprland log lines counted between two
line-count reads about 10 s apart; the window length is not timed, so read ratios as approximate):

| arm | idle: commits / scheduleFrame | scrolling: commits / scheduleFrame | whole-surface commits | ring exhausted |
| --- | --- | --- | --- | --- |
| TC candidate (ring 2) | 604 / 1210 | 375 / 1228 | 0 | 0 |
| TB R10 (ring 3) | 610 / 1220 | 337 / 1159 | 0 | 0 |

The idle rhythm is the same to 1 %. While scrolling the candidate commits 11 % more, not fewer: the
two-buffer ring never starved the frame loop in any window, in the software typing window either (239
commits, 0 whole-surface, 0 exhausted). The exhausted count is the trace line
`Swapchain: all buffers are still owned by the backend` (read: `Swapchain.cpp` `next()`); it has no
positive control from this phase (phase 4 greps the `capping a Wayland swapchain` debug line from the
same log to prove the log level shows the ring change).

### Step 5: software GPU (`gpu_mode=software`, llvmpipe), diet D against no diet N (D N N D)

| arm | idle PSS MB (SwapPss 0.2) | Hyprland idle PSS | typing 1 Hyprland CPU % | typing 2 Hyprland CPU % | cold start s (hand-over / desktop) |
| --- | --- | --- | --- | --- | --- |
| D1 | 889.4 | 435.4 | 498.1 | 448.2 | 16.0 / 15.5 |
| N1 | 914.9 | 452.5 | 520.3 | 496.5 | 15.5 / 14.9 |
| N2 | 891.0 | 441.4 | 508.6 | 473.9 | 16.8 / 16.2 |
| D2 | 897.6 | 441.4 | 460.9 | 493.3 | 15.5 / 15.0 |

**The diet does nothing in this build, so step 5 as written FAILS.** Read-back through
`hyprctl getoption` in every arm, diet and no diet: `animations:enabled`, `decoration:blur:enabled`
and `decoration:shadow:enabled` all read `bool: false`. The image config has blur and shadow off
(read: `default/hypr/looknfeel.lua`) and the mobile UI turns animations off (`omdroid-ui.sh`
looknfeel block), so there was nothing to switch off. Hyprland typing CPU: diet 448-498 (mean 475),
no diet 474-520 (mean 500), ranges overlapping, and idle Hyprland PSS is 441.4 in both second arms.
The helper itself works (log: `hyprctl eval rc=0 ok`, once after one refused connect in D1).
Typing needs about **5 cores** of the 8: `thdiff.py` over Hyprland's 24 threads shows 8 `llvmpipe-N`
workers at 60-69 % each (484-532 % in all) and the main thread out of the top six. The cost is
rasterising, not blur or animation: a full-screen `foot` (3200 px wide, I looked at `p3-N1-foot.png`)
is redrawn through llvmpipe. Software mode idle is 889-915 MB PSS, Hyprland 435-452 MB, against 190-200
MB on kgsl.

## Phase 4: where the software-GPU CPU goes (measured, tablet, 02:16-02:25, candidate APK, one clean software session Q plus two single-purpose arms)

Typing windows: 20 x `input text abcde` into a full-screen `foot`, Hyprland CPU over 8.1-8.5 s, timed
start to start. Q baseline: **473 / 511 / 476 %** of one core (three windows in the same session).

| lever (live, `hyprctl eval`, then reverted) | read-back after applying | typing Hyprland CPU % on / off | verdict |
| --- | --- | --- | --- |
| border size 0 | `general:border_size` 0 | 455.7 / 536.0 | **void**: the session already had border 0 (read-back at baseline: 0, set by the mobile UI); my revert wrote 2, so the windows after this one ran with border 2 |
| colour management off | `render:cm_enabled` false | 479.4 / 480.8 | no effect |
| cursor invisible | `cursor:invisible` true | 444.2 / 498.6 | -11 %, inside the baseline spread (455-536): not a result |
| `debug.vfr = true` | `debug:vfr` true | **355.9** / 508.8 | **-25 to -30 %**; but VFR has the known lost-last-frame risk (`damage-and-frame-pacing.md`), not shipped |
| `LP_NUM_THREADS=2` (a new session, `session.env`) | 12 threads in Hyprland | **196.1 / 196.3** | **-60 %**, but see the idle row |

Read-back of the options in the clean session (blur, shadow, animations all `false`, `debug:damage_tracking`
2, `render:direct_scanout` 0, `cursor:no_hardware_cursors` 1): nothing left to switch off in the config.

**What did not work as an instrument**, so nothing is concluded from it:
- Eight forced repaints (`debug.vfr = false` re-asserted) cost **1.7 %** of one core in total, while typing
  costs 480 %. Either a full frame is cheap and the typing cost is elsewhere, or the re-assert does not
  repaint in software mode. That is also the open question behind the phase 2 correctness diffs (a diff of
  0 means something only if the repaint happened): phase 5 counts the commits that carry damage after the
  re-asserts, on software and on kgsl.
- `debug.damage_blink = true` (read-back `true`): two screenshots while typing show no overlay at all (0 red-tinted
  pixels, and I looked at both). No positive control, so inconclusive.

**What the trace says** (software, `AQ_TRACE`, 400 log lines of a typing window): 88 commits, 53 with 0 rectangles
and 35 with 1, none a whole-surface commit, ring never exhausted. The commit stream is damage-limited, so
the typing cost is not a stream of whole-surface commits. The trace also holds
`Swapchain: capping a Wayland swapchain from 3 to 2 buffers` **1,859 times**: the positive control that
the ring change is live and that the log level shows it, and a wart (the line is logged on every
commit, formatted every time; negligible CPU, noisy at trace level; fix by logging only when the length
changes, not done).

**`LP_NUM_THREADS=2` idle**: in its first run Hyprland read **199.1 % of one core while idle** (Q idle: 3.9 %), and
idle Hyprland PSS was 426.5 against 437.1 MB. Two pegged cores at idle would make it worse overall, but
this is one window and the cause is unknown, so phase 5 repeats it (idle twice, typing twice, idle after
typing, with 8, 2, 4 and 2 threads) and counts commits per second to see whether the low CPU is dropped frames.

### Correctness: what the diffs above do and do not prove (added after phase 5; this supersedes the table's reading)

**The forced-repaint step did not repaint.** In phase 5 (trace on) eight `hl.config({ debug = { vfr = false } })`
re-asserts produced **0 damaged commits out of 256 (software) and out of 233 (kgsl)**: the value is unchanged,
so Hyprland damages nothing. The table above therefore compares two frames taken after the event; a stale
remnant would sit in both and read as 0. The `damage-and-frame-pacing.md` method (and R10's 13 checks)
need a different forcing step; this stream did not find one that works.

What the same shots do show, comparing each event with the frame taken **before** it (measured,
`scrdiff.py`; the clock turning over is x 141-161, y 29-58):

| event | frame before -> frame after | changed pixels | reading |
| --- | --- | --- | --- |
| `foot` opened and closed | `idle-after` -> `foot-closed-after` | **0** | no remnant of the window (a full-screen window, so the whole picture was redrawn) |
| toast shown and faded | `foot-closed-after` -> `toast-faded-after` | 2,131, all in the bar (y 24-88) | the toast area (y 88-253) is clean. I looked at both bars: the clock went 01:10 -> 01:11 and an unread badge "1" appeared beside it, which accounts for the x 141-220 part; a cluster at x 3000-3100 (right end of the bar) I did not identify |
| rotation and back | `toast-faded-after` -> `restored-after` | 2,230,231 (9,503 above 8 levels, 620 above 24) | all on edges (mean gradient 27 at the large differences against 1.4 overall), spread over the lower wallpaper, best integer shift 0,0: consistent with the wallpaper being re-decoded at a size one pixel off, not with a remnant; not proven; the phase 6 restart arm was invalid (below), phase 7 repeats the round trip on both builds |

Positive controls on the same shots: toast visible against the frame before it 166,706 px; foot open
against idle 5,809,341 px.

### Software mode: where the CPU goes (phases 5 and 6, measured)

Phase 5 (02:48-03:00, candidate, software, one session per arm, timed windows; `LP_NUM_THREADS` unset / 2 / 4 / 2):

| arm | idle before typing | typing | idle after foot closed | threads |
| --- | --- | --- | --- | --- |
| LP8 (default) | 1.9 % | 518 / 492 % | **742 %** | 8 llvmpipe workers at 91-98 % |
| LP2 | **197 %** | 196 / 197 % | 197 % | 2 workers at 97 % |
| LP4 | **384 %** | 387 / 382 % | 383 % | 4 workers at 95 % |
| LP2b (repeat of LP2) | 2.0 % | 197 / 198 % | **197 %** | 2 workers at 98 % |

Phase 6 (08:09-08:16, candidate, software, default threads, no trace, one session per arm, timed windows; the half
resolution arm sets the Android display override to 1068x1600 at 176 dpi, which gives an X root of 1600x984 at scale 1,
the same logical layout as the native 3200x1970 at scale 2 with a quarter of the pixels):

| arm | idle | foot open, not typing | typing 1 / 2 | after foot closed | Hyprland PSS idle / typing | session PSS idle / typing |
| --- | --- | --- | --- | --- | --- | --- |
| V1 native 3200x1970 | 1.9 % | 103.4 % | **428 / 483 %** | 1.9 % | 432.8 / 502.0 MB | 865.3 / 943.7 MB |
| V3 half 1600x984 | 2.0 % | 3.7 % | **155 / 139 %** | 2.0 % | 229.9 / 248.1 MB | 519.4 / 544.8 MB |
| V1 with `debug.vfr=true` set live | 0.1 % | - | **320 %** (one window) | 0.1 % | 448.1 / 502.4 MB | 871.7 / 946.2 MB |

What this supports (all measured, one session per arm, so the size of each effect is a direction, not a figure
with an error bar):

1. **Software cost follows the pixel count.** A quarter of the pixels costs 3.1 times less CPU while typing (455 %
   mean against 147 %), 254 MB less in Hyprland (502 -> 248 MB) and 400 MB less in the session (944 -> 545 MB). I looked
   at the half-resolution frame (`phase6/shots/p6-V3-end.png`): desktop intact, bar text legible, no band or dialog;
   it shows the two "Omdroid could not shutdown / could not stop" toasts, which are the guest leftovers listed in
   Risks, not a rendering fault. The lever is a smaller X root in software mode. That is a host change (the surface the
   X server is given), outside this stream's files: it is handed to the parent as the one software-mode win with
   a measurement, not shipped here.
2. **`debug.vfr` costs the same lever as before** (phase 4: -25..-30 %): typing 320 % against 428 / 483 %, idle 0.1 %.
   Not shipped, for the lost-last-frame risk named in phase 4.
3. **The "persistent busy state" I wrote up after phase 5 is retracted as a general property, and not explained.**
   In phase 5 all four sessions went into it (LP2 and LP4 from the first idle window, LP8 and LP2b after the typing):
   Hyprland stayed at 742 % (LP8) or at the thread-count ceiling (197 % LP2, 384 % LP4) after the foot window closed.
   In the three default-thread sessions of phases 6 and 7 (V1, V3, and the phase 7 repeat of the exact phase 5 LP8
   sequence, S) it never came: idle after the typing **1.9 / 1.8 %** (S, two 20 s windows), 1.9 % (V1), 2.0 % (V3). So it
   exists and is intermittent, I do not know what enters it, and I could not make it recur. My earlier sentence that R10's
   "496 % while typing" is this state is **withdrawn**: typing at default threads cost 339-520 % in every
   default-thread window of phases 3 to 7 (S: 372 / 339 %, the lowest), and idle after it is 1.9 % when the state is
   not on.
4. **`LP_NUM_THREADS` is not a fix.** At 2 or 4 threads the phase 5 arms sat at 197 % and 384 % through the idle
   windows, while the default sat at 1.9 % in the same windows; the trace of the 2-thread run shows 1.7 commits/s, every
   one carrying damage, against 60 empty commits/s at default idle (so it is not a quieter desktop). Whether the
   typing figure (196 %) is dropped frames was not counted.
5. **Per damaged frame** (estimated: CPU divided by damaged commits, trace on): typing at default threads is 52
   damaged commits in 6 s at about 500 %, about 0.6 core-seconds per damaged frame; kgsl takes about 0.03 for 49 damaged commits
   in the same window. The half-resolution arm was not traced, so the per-frame figure at a quarter of the pixels is not measured.

Trace of the post-typing window (phase 6 `Vt`, trace on, 5-11 s after the foot window closed): 8.4 commits/s, 51 of 51
with one damage rect, against 61.5 empty commits/s at calm idle. The trace arm did not measure CPU (the trace changes it),
so I cannot say whether this window is the intermittent high state or the tail of the window closing; the phase 7
repeat (item 3) read 1.9 / 1.8 % idle after typing in the same position, so I take it to be the tail of the window closing.

### Phase 6, shell-restart arm (K): invalid for wallpaper determinism, and it found a crash

The arm took a frame, ran the stock `omarchy-restart-shell` twice from the live session and compared the frames
(pixel counts: candidate C 5.88 M then 0.42 M changed; R10 behaviour B 6.30 M then 0). I looked at every frame:
`sr-C-0` and `sr-B-0` (15 s after the cold start) are intact desktops (wallpaper, bar at 08:17, the two
"Omdroid could not shutdown / could not stop" toasts); after restart 1 on the candidate (`sr-C-1`) the screen is black
with a "Quickshell has crashed" dialog (crashed process 11733, crash folder `7z8szi5pt`) and the toasts; after restart 1
on arm B (`sr-B-1`) the screen is black with only the cursor and no dialog; `sr-C-2` shows the same crash dialog and
`sr-B-2` is byte-identical in size to `sr-B-1` (black). So the pixel counts compare dead frames and say nothing about the
wallpaper. Both arms ended without a desktop; the cause was not read in phase 6.

## Phase 7: rotation round trips, the manual restart, the busy state again (measured, tablet, 08:52-09:07, candidate APK)

**Rotation round trips (4 arms in the order C B B C, two round trips each, `screen.sh rot 0` then `reset`, frame
before and after, `scrdiff.py`).** Every arm: the layers went to 1068x1517 logical and back to 1600x985, and the
frame after the round trip equals the frame before it except in the bar:

| arm | before -> after round trip 1 | round trip 1 -> round trip 2 |
| --- | --- | --- |
| C1 (candidate) | 388 px, bbox (141,29)-(3083,89) | 366 px, bbox (141,29)-(160,58) |
| B1 (R10 behaviour) | 265 px, bbox (141,29)-(160,58) | 477 px, bbox (141,29)-(3083,89) |
| B2 (R10 behaviour) | 365 px, bbox (141,28)-(3083,89) | 939 px, bbox (72,28)-(160,58) |
| C2 (candidate) | 450 px, bbox (141,28)-(3083,89) | 263 px, bbox (141,28)-(160,58) |

All 263-939 changed pixels sit inside the bar (y < 90): the clock (x 141-160, y 29-58; I viewed the bar before and
after in C1: 08:53 -> 08:54, and a struck-through wifi icon at the far right, which is where x about 3083 is). **The wallpaper
below the bar is identical to the pixel in all eight comparisons, on both builds.** The 2.2 M-pixel edge-level
difference I measured in phase 2 (`toast-faded-after` -> `restored-after`) did **not** reproduce here in either build, so
the candidate's smaller wallpaper decode is deterministic across round trips and the phase 2 residual is unexplained
(UNVERIFIED hypothesis only: that sequence had a toast, a window and a clock turnover between the frames). The
"control: before -> rotated must differ" line printed "size differs" (the frame is 2136x3200 against 3200x2136), a
trivial control; the rotated frames are `r7-*-rot1.png` but I did not compare them pixel by pixel. In B2 the watcher also
logged one of its own shell restarts (`act: omarchy-restart-shell rc=0`, "layers fit again 0.1 s after the restart") and
the desktop was intact afterwards.

**Manual `omarchy-restart-shell` on the candidate (arm X, no `session.env`):** the command returned `rc=0` and the screen
ended on the Quickshell crash dialog (viewed `r7-X-after.png`: crashed process 1867, crash folder `0d1z4l5pt`, created 09:03);
the layers after it were only background, `omamobile-home-strip` and `omamobile-launcher` (no bar), and the process list
had two live Quickshell processes plus one defunct. So the crash on the manual restart reproduced on the candidate,
three of three times (phase 6 restart 1, phase 6 restart 2 shows the stale dialog, phase 7). Whether it is caused by this
stream's changes is not known yet: phase 8 reads the crash report and runs the same restart on the R10 APK.

## What changed

- `rootfs/patches/aquamarine/0004-wayland-cap-the-nested-swapchain-at-two-buffers.patch`
  (`CSwapchain::reconfigure`, `src/allocator/Swapchain.cpp`): a Wayland swapchain is capped at
  `AQ_WAYLAND_SWAPCHAIN` buffers (default 2). `rootfs/build-aquamarine.sh` applies 0001-0004 and
  checks the sha256 of each; the rebuilt library is `rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13`.
  `start.sh` exports `AQ_WAYLAND_SWAPCHAIN=2` in the env-defaults block, before `session.env`.
- `rootfs/overlay/etc/phoshdroid/mem/`: `session-start.sh` (the hook), `qml-apply.sh` (patched
  Quickshell files over the image copies, original kept as `<file>.omdroid-orig`, applied only
  to the exact original whose sha256 is in `<file>.base-sha256`), `qml/plugins/background/Background.qml`
  (the three wallpaper `Image` items get `sourceSize` = the screen in device pixels). A software-GPU diet helper
  (`soft-diet.py`) was written and reverted (`41e272f`): it saved nothing measurable.
- `docs/omarchy/tools/mem-attrib-smaps.sh` and `mem-attrib.py`: the attribution method.

## Host proof

## Device proof

## Switches

| Change | Switch | Off value |
| --- | --- | --- |
| aquamarine ring of two | `AQ_WAYLAND_SWAPCHAIN` (`session.env`) | `3` |
| every change of `mem/` | `OMDROID_MEM` | `0` |
| Quickshell file patches | `OMDROID_MEM_QML` | `0` |

## Risks

## What was not done
