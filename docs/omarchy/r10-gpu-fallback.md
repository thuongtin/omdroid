# R10 S2 (gpu): boot without an Adreno GPU, keep Android from killing the guest

Branch `r10/gpu-fallback`, cut from `bbf908d`. Stream owner: S2. No device was attached: every
device claim below is **PENDING** and comes with the command the parent runs.

## STATUS TABLE

| Step | What | Status | Proof |
|---|---|---|---|
| 1 | Facts: llvmpipe present? `OMARCHY_GPU_MODE` consumers? what each KGSL variable does, software block | PASS | host `readelf`/`strings`/`grep` on the extracted image, below |
| 2 | `GpuMode.kt` rule, Graphics setting, `ProotCommandBuilder` env blocks, tests | PASS | `:app:test` 153 tests, 0 failures (host); new: `GpuModeTest` 10, `ProotCommandBuilderTest` 9 (5 new). Log `gradle-test-1.log` |
| 3a | `start.sh` GPU block honours `OMDROID_GPU` (probe when unset) | PASS | `bash -n` ok; `GuestGpuScriptsTest` 7 block tests run the real block in bash and compare with the host env (host). Positive control: breaking two lines of the block failed 3 tests; restored (sha256 equal) |
| 3b | `launch-contract.md` GPU section | PASS | section 9 added (plus the `gpu:` log lines in section 6); same commit as 3a/3c |
| 3c | `session-child.sh` one software retry on an early Hyprland exit (stretch) | PASS (host, fake Hyprland) | `GuestGpuScriptsTest` 7 fallback tests: retry, no retry on success / user choice / switch off / past the window, exit codes kept, exec path unchanged. `:app:test` 167 tests, 0 failures. Real Hyprland: PENDING (device) |
| 4 | Phantom process killer: `ProcessLimits.kt` + hook in `ProotService` | PENDING | |
| 5 | `onTrimMemory` / `onLowMemory` logging in `ProotService` | PENDING | |
| Gate | `:app:test`, `:app:lintDebug` | PENDING | |

## Step 1: facts (host, measured on the 0.0.17 image unless marked read)

**llvmpipe is in the patched Mesa; softpipe is not.** (measured: `readelf -dW` and `strings -a` on
`/opt/omarchy-android/mesa/root/usr/lib/libgallium-26.3.0-devel.so`, 28,206,784 B)

- `NEEDED libLLVM.so.22.1` is a hard dependency, and the image has it (`usr/lib/libLLVM.so.22.1`,
  pacman entry `llvm-libs-22.1.8-2`). The same library is already loaded on the tablet in KGSL
  mode, so every `NEEDED` entry resolves on a device.
- `strings`: `llvmpipe` 210 hits, `lp_build` 352, `softpipe` **0**. The software mode therefore gets
  llvmpipe, never softpipe; `GALLIUM_DRIVER=softpipe` would select nothing.
- The DRI dir has `swrast_dri.so` and `kms_swrast_dri.so` (links to the `libdril_dri.so` megadriver).
  `LIBGL_ALWAYS_SOFTWARE`, `GALLIUM_DRIVER` and `MESA_LOADER_DRIVER_OVERRIDE` are all strings in the library.
- The image has **no lavapipe**: no `libvulkan_lvp.so` or `lvp_icd*.json` among the 83,316 members. Only the
  freedreno ICD exists, so the software block ships no Vulkan ICD.
- Not proven: that llvmpipe's JIT can map executable memory inside proot on a phone. PENDING (device).

**`OMARCHY_GPU_MODE` has exactly one consumer in the image** (read: `grep -rI` over
`usr/share/omarchy`, `usr/local/bin`, `home/omarchy/.config`, `etc`, extracted in one `tar -xzf` pass):

- `usr/share/omarchy/bin/omarchy-launch-shell:69`, `if [[ ${OMARCHY_GPU_MODE:-virgl} == kgsl ]]`. Both
  branches start Quickshell with the same environment (`QT_QUICK_BACKEND=software QSG_RENDER_LOOP=basic`
  and the rest); the `kgsl` branch only adds a comment. So any value other than `kgsl` behaves like
  `virgl` and no virgl-only code path exists (`virgl` appears only as the default value in that test and in a comment of
  `omarchy-provision-owner`; `virpipe` and `VTEST` appear nowhere). The software mode exports
  `OMARCHY_GPU_MODE=software`: it names the mode honestly and takes the same branch.
- The shell is CPU-rendered in both modes, so a software session changes only Hyprland's own renderer
  and GL clients.
- `usr/local/bin/Xwayland` unsets `GALLIUM_DRIVER`, `LIBGL_DRIVERS_PATH`, `MESA_LOADER_DRIVER_OVERRIDE` and
  `VK_ICD_FILENAMES` and runs `-shm`, so the software block does not reach Xwayland.

**What each GPU variable does, and what the software block does with it**

| Variable | Role (source) | Software block |
|---|---|---|
| `OMARCHY_GPU_MODE` | only read at `omarchy-launch-shell:69` | `software` |
| `MESA_LOADER_DRIVER_OVERRIDE` | picks the DRI driver name; without it Mesa tries its X11 DRI3/Zink path (`nested-wayland-stack.md`, GPU ladder) | `swrast` |
| `LIBGL_ALWAYS_SOFTWARE` | makes Mesa's EGL surfaceless platform skip the render-node scan, which cannot succeed without a DRM node | **added**, `1` |
| `GALLIUM_DRIVER` | picks the pipe driver inside the megadriver | **added**, `llvmpipe` |
| `LIBGL_DRIVERS_PATH` | where the loader finds `*_dri.so`; the patched copy is the one that links `libgallium-26.3.0-devel.so` | kept |
| `LD_LIBRARY_PATH` (`/opt` Mesa first) | the patched libEGL/libgallium win over the stock Arch ones | kept |
| `VK_ICD_FILENAMES` | freedreno ICD; fails to initialise on a non-Adreno GPU; no lavapipe to replace it | **dropped** |
| `FD_KGSL_ENABLE_DMABUF` | freedreno/KGSL only: exports GPU buffers as dma-bufs | **dropped** |
| `HYPRLAND_ANDROID_DMABUF` | patched Hyprland keeps `linux-dmabuf` v3 without a DRM node (`strings Hyprland`: "Android KGSL: keeping linux-dmabuf v3 without a DRM node"); software GL clients have no dma-buf producer and use `wl_shm` | **dropped** |
| `HYPRLAND_SHM_DAMAGE` | damage-limited copies into the SHM swapchain; the presentation path does not depend on the GPU vendor (aquamarine 0001 picks `CSHMAllocator` unless `AQ_ANDROID_DMABUF_VULKAN` or `_HEAP` is set, and neither is set anywhere) | kept |
| `HYPRLAND_EGL_SURFACELESS` | EGL without an EGLSurface (nothing to present to without a DRM node) | kept |
| `HYPRLAND_EGL_NO_MODIFIERS`, `AQ_NO_MODIFIERS` | no DRM modifiers exist on this path in either mode | kept |
| `AQ_NO_KMS_REQUIREMENT` | aquamarine refuses to start without a DRM node otherwise | kept |
| `AQ_WAYLAND_REFRESH_MHZ` | read by the patched backend (`0001...patch:1463`), cadence only | kept |
| `HYPRLAND_NO_SD_*`, `HYPRLAND_NO_RT`, `QT_*`, `GDK_BACKEND`, `SDL_VIDEODRIVER`, `XWAYLAND_NO_GLAMOR`, `NO_AT_BRIDGE`, `GTK_A11Y` | not GPU-specific | kept |

Not changed, and why it matters for the device round: `~/.config/chromium-flags.conf` in the image forces
`--use-angle=vulkan`, which needs the freedreno ICD. In software mode Chromium's GPU process fails and it
falls back to CPU compositing after a slow start. That file belongs to the image, not to this stream.

## What changed

- `launch/GpuMode.kt` (new): `GpuMode` (`KGSL`, `SOFTWARE`) and `GpuModeRule`: `resolve(preference, kgslUsable)`,
  `normalise`, `source` (`auto` or `setting`), and the one probe `isKgslUsable()` (`/dev/kgsl-3d0` exists, readable
  and writable). The rule is pure; only `isKgslUsable` touches the file system.
- `settings/PhoshdroidPreferences.kt`: `gpuMode` (key `gpu_mode`, default `auto`, unknown values read as `auto`).
- `res/xml/preferences.xml` + `res/values/strings.xml`: a "Graphics" category with one list, Auto / Adreno GPU
  (KGSL) / Software (slow, any phone). It takes effect at the next desktop start.
- `proot/ProotCommandBuilder.kt`: `buildEnvironment(..., gpu, gpuSource)`. The KGSL entries are the old ones
  unchanged; the software mode drops `VK_ICD_FILENAMES`, `FD_KGSL_ENABLE_DMABUF`, `HYPRLAND_ANDROID_DMABUF` and
  adds `LIBGL_ALWAYS_SOFTWARE=1`, `GALLIUM_DRIVER=llvmpipe`, `MESA_LOADER_DRIVER_OVERRIDE=swrast`,
  `OMARCHY_GPU_MODE=software`. Both modes add `OMDROID_GPU=<kgsl|software>` and `OMDROID_GPU_SOURCE=<auto|setting>`.
  A caller that passes neither gets KGSL and source `setting`, so no guest fallback.
- `proot/ProotDistroManager.kt`, `proot/ProotService.kt`: the service resolves the mode once per start, logs one line
  (`gpu: preference=auto kgsl-usable=false -> software source=auto`, tag `Phoshdroid`) and passes it to the
  session and the root broker.

- `rootfs/overlay/etc/phoshdroid/start.sh` (GPU block only, from `# GPU path` to `# Fake root:`): uses
  `OMDROID_GPU` when it is `kgsl` or `software`; otherwise probes `/dev/kgsl-3d0` (`-r` and `-w`) and treats
  the launch as `auto`. If the mode is `kgsl`, the source is `auto` and `$XDG_RUNTIME_DIR/omdroid-gpu-fallback`
  exists, it starts in software mode (a host retry after a guest fallback). Exports the shared variables,
  then the mode's block, and `unset`s the other mode's variables. One session-log line:
  `gpu: mode=<m> source=<s> from=<host|probe|marker>`. No apostrophes in the new comments; `bash -n` ok.
- `rootfs/overlay/etc/phoshdroid/session-child.sh`: for `OMDROID_GPU=kgsl` with `OMDROID_GPU_SOURCE=auto`
  (and `OMDROID_GPU_FALLBACK` not `0`) Hyprland runs as a child with signal forwarding; a non-zero exit
  within `OMDROID_GPU_FALLBACK_WINDOW` (15) seconds that nobody asked for removes the failed start's `hypr/`
  dir and shell lock, leaves the marker, switches to the software block and `exec`s Hyprland once more. Every other
  case still `exec`s Hyprland as before.
- `docs/omarchy/launch-contract.md`: section 9 (who decides, the two variables, the per-mode table, the guest
  rule, the fallback, how it meets `SessionExit`, logs, what is not shipped).
- `app/src/test/.../launch/GuestGpuScriptsTest.kt`: runs both scripts in bash with a clean environment, a
  temporary runtime dir, a fake Hyprland and a fake `pkill` (the real one would hit the machine running the tests).

## Host proof

(filled in as steps land)

## Device A/B plan (the parent runs it)

(filled in at the end)

## Risks

(filled in at the end)

## What I did not do

(filled in at the end)
