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

Correctness against a forced full repaint (`scrdiff.py`, exact pixel compare, one run each):

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

## Open after runs 1 and 2

1. **Hand-over is slower with the new watcher.** The five socket-watcher cold starts took
   10.7-12.0 s, the legacy-watcher arm 7.1 s and 0.0.18 8.7 s. `desktop` (the probe sees the
   bar and wallpaper, independent of the marker) moves with it, so the shell itself comes up
   later, not just the marker. Run 3 separates the watcher from plain CPU load.
2. **Idle PSS is higher than the 0.0.18 baseline:** the app's `dumpsys meminfo` total went from
   250.7 MB to 280.1 MB. The app maps the three `aquamarine-shm` frame buffers (cage scans
   Hyprland's frames out directly), a 24.8 MB CPU-mapped GPU buffer and one 24.6 MB ashmem
   `LorieBuffer`; the baseline showed no ashmem buffer. The full-damage arm has the same
   layout, so the damage patch is not the cause. Run 3 measures 0.0.18 again in the same hour
   before anything is concluded.
3. Software GPU mode on the device.
