# R11 S1: memory, and a software-GPU mode a phone can live with

Branch `r11/memory` (from `90d7494`). Stream S1 of R11. Evidence labels: **measured**, **read**,
**estimated**. Every device number was taken on the tablet; every A/B is in the same hour.

## STATUS TABLE

| # | Step | Status | Proof |
| --- | --- | --- | --- |
| 1 | Attribution (R10 build, Quickshell + Hyprland + app) | PASS | tables below; device phase 1, log `<scratch>/mem/phase1.log`, rows `<scratch>/mem/phase1/attrib/rows.txt` |
| 2 | Quickshell fixes (through `mem/`) | PASS (memory), fidelity noted | `47e1aee`: wallpaper `sourceSize`: Quickshell wallpaper block 77.7 -> 26.3 MiB, Quickshell heap 143.2 -> 91.3 / 92.3 MB in both candidate arms (phase 2, below); picture unchanged to my eye, fine-detail energy 36 % lower (measured, below); `OMDROID_MEM_QML=0` restores the file |
| 3 | aquamarine swapchain 3 -> 2 (`AQ_WAYLAND_SWAPCHAIN`) | PARTIAL: idle PSS and repaint diffs PASS, commit rhythm PENDING | `f97dda7`: -12.0 MB in Hyprland and -12.0 MB in the app in both candidate arms (3 -> 2 `aquamarine-shm` mappings); forced-repaint diffs 0 on idle, window open, window close, toast fade, rotation, restore; `AQ_TRACE` commit rhythm and CPU re-measure in phase 3 |
| 4 | Hyprland extras (logo, cursor, render options) | PENDING | image config already sets logo, splash, blur, shadows off (read) |
| 5 | Software-GPU diet (`OMDROID_GPU=software`) | CODE COMMITTED, device PENDING | `70fef09`: `mem/soft-diet.py` (hyprctl eval, re-applied after `configreloaded`); the image config already has blur and shadows off (read), so the measurable part is animations: phase 3 decides whether more is needed |
| 6 | Optional: `TERMUX_X11_FORCE_FLIP=1` (report only) | PENDING | |

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

Positive controls (host-side, on the same shots): the toast really drew (my own look at
`toast-up.png`: a framed popup "r11-toast / toast fade check" at the top right, and 168,813 px differ
from the faded frame); `scrdiff` reads 5,809,341 changed pixels between the idle shot and the
`foot`-open shot, so the instrument sees a window; two sessions of the same build differ by 343 px,
all in the clock (bbox 141-161 x 29-58). The clock is the only changed region in the repaint diffs
too, and none showed it changing.

### Wallpaper fidelity (measured and looked at)

My own look at 800 px thumbnails (`p2-C2.png`, `p2-B2.png`): the same wallpaper, bar and key row, no
black band; at 1:1 on the deer and ridge crop I cannot tell the two apart. Measured, on the
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

## What changed

- `rootfs/patches/aquamarine/0004-wayland-cap-the-nested-swapchain-at-two-buffers.patch`
  (`CSwapchain::reconfigure`, `src/allocator/Swapchain.cpp`): a Wayland swapchain is capped at
  `AQ_WAYLAND_SWAPCHAIN` buffers (default 2). `rootfs/build-aquamarine.sh` applies 0001-0004 and
  checks the sha256 of each; the rebuilt library is `rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13`.
  `start.sh` exports `AQ_WAYLAND_SWAPCHAIN=2` in the env-defaults block, before `session.env`.
- `rootfs/overlay/etc/phoshdroid/mem/`: `session-start.sh` (the hook), `qml-apply.sh` (patched
  Quickshell files over the image copies, original kept as `<file>.omdroid-orig`, applied only
  to the exact original whose sha256 is in `<file>.base-sha256`), `qml/plugins/background/Background.qml`
  (the three wallpaper `Image` items get `sourceSize` = the screen in device pixels), `soft-diet.py`.
- `docs/omarchy/tools/mem-attrib-smaps.sh` and `mem-attrib.py`: the attribution method.

## Host proof

## Device proof

## Switches

| Change | Switch | Off value |
| --- | --- | --- |
| aquamarine ring of two | `AQ_WAYLAND_SWAPCHAIN` (`session.env`) | `3` |
| every change of `mem/` | `OMDROID_MEM` | `0` |
| Quickshell file patches | `OMDROID_MEM_QML` | `0` |
| software-GPU diet | `OMDROID_SOFT_DIET` | `0` |

## Risks

## What was not done
