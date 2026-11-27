# R11 S1: memory, and a software-GPU mode a phone can live with

Branch `r11/memory` (from `90d7494`). Stream S1 of R11. Evidence labels: **measured**, **read**,
**estimated**. Every device number was taken on the tablet; every A/B is in the same hour.

## STATUS TABLE

| # | Step | Status | Proof |
| --- | --- | --- | --- |
| 1 | Attribution (R10 build, Quickshell + Hyprland + app) | PASS | tables below; device phase 1, log `<scratch>/mem/phase1.log`, rows `<scratch>/mem/phase1/attrib/rows.txt` |
| 2 | Quickshell fixes (through `mem/`) | CODE COMMITTED, device PENDING | `47e1aee`: wallpaper `sourceSize` patch via `mem/qml-apply.sh` (dry run on a copy of the image shell dir: patched, idempotent, `OMDROID_MEM_QML=0` restores byte-identical); expected saving about 53 MiB; phase 2 measures it |
| 3 | aquamarine swapchain 3 -> 2 (`AQ_WAYLAND_SWAPCHAIN`) | CODE COMMITTED, device PENDING | `f97dda7`: patch 0004, library built (ABI OK: SONAME and NEEDED identical, 0 consumer symbols missing, GLIBC 2.38), sha256 `5e8bbd35...`; device A/B and correctness diffs run in phase 2 |
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
