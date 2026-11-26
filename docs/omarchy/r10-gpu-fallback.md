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
| 4 | Phantom process killer: `ProcessLimits.kt` + hook in `ProotService` | PASS (host decision table); device PENDING | `ProcessLimitsTest` 9 tests (decision table over SDK 28-36 x setting x grant); mechanism read from AOSP, section below. Writing and the notification: device PENDING |
| 5 | `onTrimMemory` / `onLowMemory` logging in `ProotService` | PASS (name table, host); device PENDING | `MemorySignals.trimLevelName` tested for the seven levels; steps 4 and 5 share one commit because both edit `ProotService` |
| Gate | `:app:test`, `:app:lintDebug` | PASS (host) | `:app:test` 176 tests, 0 failures, `:app:lintDebug` 0 errors, 17 warnings, none new against the parent's `main` report (its 32 include 15 network version-check warnings this offline run cannot make). Log `gradle-test-3.log` |

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
| `LIBGL_ALWAYS_SOFTWARE` | Mesa's switch to its software path; in the host EGL test below it is redundant once `MESA_LOADER_DRIVER_OVERRIDE=swrast` is set, and on its own it is not enough | **added**, `1` (belt and braces) |
| `GALLIUM_DRIVER` | picks the pipe driver inside the megadriver; also redundant in the host test, kept so the choice is explicit | **added**, `llvmpipe` |
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

- `launch/ProcessLimits.kt` (new): the pure rule `decide(sdkInt, reading, canWriteSecureSettings)` ->
  `NOTHING_TO_DO` / `DISABLE` / `TELL_USER`, and `apply(context, enabled)` that reads `Settings.Global`, writes
  `settings_enable_monitor_phantom_procs=false` and reads it back (every read and write inside a `try`, a
  refused or non-sticking write becomes `TELL_USER`). It logs one line per start (tag `Phoshdroid`,
  `limits: phantom-procs sdk=34 setting=unset write-secure-settings=true -> wrote settings_enable_monitor_phantom_procs=false`).
  Same pattern as `KeyCapture`: `WRITE_SECURE_SETTINGS` is checked with `checkSelfPermission`, no new manifest line.
- `proot/ProotService.kt`: calls `ProcessLimits.apply` in `onStartCommand` before `startForeground`. For
  `TELL_USER` the foreground notification's text becomes "Android may stop desktop apps. Expand for the fix."
  with the full instruction (the adb command) in its expanded `BigTextStyle`. It is the least intrusive place
  that a person sees: the notification is already there for the whole session, no second channel, no
  dismissal state to keep. It also overrides `onTrimMemory` and `onLowMemory` (log only, tag `Phoshdroid`,
  `memory: onTrimMemory TRIM_MEMORY_RUNNING_LOW (10)`, `memory: onLowMemory`).
- `settings/PhoshdroidPreferences.kt`, `res/xml/preferences.xml`: `phantom_limit_fix` (default on), the way
  back for a user who does not want the app to write a system setting.

## The phantom process killer: mechanism and what the app can do (read: AOSP, fetched for this round)

- **The count.** `PhantomProcessList.trimPhantomProcessesIfNecessary()`
  (`services/core/java/com/android/server/am/PhantomProcessList.java`, line 421 in `android12-release`, 424 in
  `android12L-release` and later): if `ActivityManagerConstants.MAX_PHANTOM_PROCESSES` (`max_phantom_processes`
  in DeviceConfig namespace `activity_manager`, default `DEFAULT_MAX_PHANTOM_PROCESSES = 32`, all apps together)
  is below the number of phantom processes, it sorts them by the parent's `curAdj` (then youngest first) and
  kills the surplus with the reason "Trimming phantom processes".
- **The CPU trigger.** `ActivityManagerService.checkExcessivePowerUsage()` (line 14237 in `android12-release`)
  also walks `mPhantomProcessList.forEachPhantomProcessOfApp` and kills a phantom process "excessive cpu" when
  its CPU use over the check interval passes the app's limit (`POWER_CHECK_MAX_CPU_1..4`); it only looks at
  apps whose process state is `PROCESS_STATE_HOME` or worse (`ActivityManager.PROCESS_STATE_*` are declared in
  ascending order, `FOREGROUND_SERVICE` before `HOME`), so while the foreground service runs only the **count**
  can kill the desktop; the CPU trigger cannot.
- **Android 12 (API 31) before QPR3: no switch.** `android12-release`, `android12-qpr1-release`,
  `android12-qpr2-release`: `PhantomProcessList.java` has no reference to the flag, both kills are unconditional.
  The only knob is `device_config put activity_manager max_phantom_processes <n>` (needs `WRITE_DEVICE_CONFIG`,
  so adb). **From `android12-qpr3-release`, `android12L-release` (API 32) and every later release** both kills
  return early unless `FeatureFlagUtils.isEnabled(context, SETTINGS_ENABLE_MONITOR_PHANTOM_PROCS)`
  (`PhantomProcessList.java:424-427` and `ActivityManagerService.java:14282-14287` in `android12L-release`; the
  same in `android14-release` and `android16-release`). The flag name is `settings_enable_monitor_phantom_procs`.
- **How the flag resolves** (`core/java/android/util/FeatureFlagUtils.java`, `isEnabled`, identical in
  `android12L-release`, `android14-release`, `android16-release`): `Settings.Global.getString` first; if it is
  non-empty, `Boolean.parseBoolean` decides (so `0` also means off); else the system property
  `persist.sys.fflag.override.<flag>`; else the default `true`. An app cannot read the property reliably, so an
  unset global is treated as "monitor on".
- **Why the global setting, not the Developer options toggle.** Android 14+ "Disable child process restrictions"
  writes the property (`FeatureFlagUtils.setEnabled`) and resets it when Developer options are switched off
  (per the AOSP Settings change cited by agnostic-apollo's documentation, secondary source); a `Settings.Global`
  value wins over the property and stays. The tablet has the property set by hand
  (`docs/omarchy/ARCHITECTURE.md:49-50`), so there the global reads `unset` and the app will write it once.
- **What the app can do.** With `WRITE_SECURE_SETTINGS`, `Settings.Global.putString` works for this key
  (a public API behind that permission). Without it: nothing but telling the user. On API 31 the write may
  be a no-op on a build before QPR3 (no reader of the flag); the app cannot tell the builds apart, so the
  note on API 31 also carries the `device_config` commands.
- Not tested on a device: that the write sticks, that Android then stops killing, and what the notification
  looks like.

## Host proof

**1. Unit tests and lint (host).** `:app:test` 176 tests, 0 failures; `:app:lintDebug` 0 errors, 17 warnings, none
new against the parent's `main` report. New tests: `GpuModeTest` (10), `ProotCommandBuilderTest` (+5, a
literal 0.0.17 KGSL environment), `GuestGpuScriptsTest` (14, the real scripts in bash), `ProcessLimitsTest` (9).
Positive control: two lines of the GPU block broken on purpose, 3 of the 14 script tests failed, file restored
(sha256 identical).

**2. The software block gets a GL context from the patched Mesa (host, emulated aarch64).** The image was
extracted, and the skill's `egl-probe.py` run inside it with `bwrap` + `qemu-aarch64-static`
(`EGL_PLATFORM=surfaceless`, no display, `/opt` Mesa first on `LD_LIBRARY_PATH`):

| Environment | Result |
|---|---|
| the software block (`MESA_LOADER_DRIVER_OVERRIDE=swrast LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe`) | `eglInitialize` ok, `eglCreateContext` ok, `eglMakeCurrent` ok; `GL_renderer: llvmpipe (LLVM 22.1.8, 128 bits)`, `OpenGL ES 3.2 Mesa 26.3.0-devel (git-98f3d6229d)` |
| `MESA_LOADER_DRIVER_OVERRIDE=swrast` alone | same: llvmpipe |
| `LIBGL_ALWAYS_SOFTWARE=1` alone (no override) | **fails**: `ZINK: vkCreateInstance failed (VK_ERROR_INCOMPATIBLE_DRIVER)`, `eglInitialize -> 0` |
| the KGSL block (`kgsl` override, freedreno ICD, `FD_KGSL_ENABLE_DMABUF=1`) with **no** `/dev/kgsl-3d0` | **also llvmpipe**: Mesa fell back to software by itself |
| the software block without `EGL_PLATFORM` | `eglInitialize -> 0` (no display to use; Hyprland chooses its own platform) |

What that does and does not show. It proves the llvmpipe path of this exact Mesa build loads and renders a
context, the load-bearing variable is `MESA_LOADER_DRIVER_OVERRIDE=swrast`, and the hard-coded KGSL override on
a machine with no node does **not** fail at the EGL layer here: it quietly lands on llvmpipe. So the premise in
the brief that a non-Adreno phone cannot create an EGL context is **not confirmed** for the probe's surfaceless
platform; whether the old block boots on a Mali phone is a device question (Hyprland and aquamarine have more
KGSL-specific steps than this probe). The explicit mode is still worth having: it states the choice instead of
relying on Mesa's silent fallback, it drops the Adreno-only dma-buf advertisement and Vulkan ICD, and it gives
the fallback in `session-child.sh` something real to switch. It does not prove anything about speed (qemu) or
about proot on a phone. The probe's last lines (`glClearColor`) die on a ctypes argtype bug in the skill copy of
the script, after the renderer line; the skill script was fixed.


## Device A/B plan (the parent runs it)

Set `TABLET_SERIAL` (the tools refuse to run without it). All three installs are the same APK; only the
Graphics setting differs. `gx.sh '<cmd>'` runs a command inside the live guest.

1. **KGSL unchanged on the tablet** (Graphics = Auto). PASS when: `adb -s $TABLET_SERIAL logcat -d -s Phoshdroid:*
   | grep -E 'gpu:|limits:'` shows `gpu: preference=auto kgsl-usable=true -> kgsl source=auto`;
   `docs/omarchy/tools/probe.sh` prints `VERDICT: PASS`; the guest log (`gx.sh 'grep "gpu:" /tmp/omarchy-session.log'`)
   shows `gpu: mode=kgsl source=auto from=host` and no `Hyprland exited` line; the session ends and restarts as it did
   (the new thing to watch: Hyprland is now a child of `session-child.sh` for this default case; Stop from the
   notification and a logout from Hyprland must both still end the session, and `ps` should show no orphan
   Hyprland afterwards). Renderer: `gx.sh 'timeout 25 python3 /path/to/egl-probe.py'` (copy it in with
   `gpush.sh`) names the Adreno, not llvmpipe. A/B switch: `OMDROID_GPU_FALLBACK=0` (session.env) or Graphics =
   Adreno GPU (KGSL) restores the old `exec` path.
2. **Software forced on the same tablet** (Settings -> Graphics -> Software, or `adb shell run-as
   com.phoshdroid.app` editing `shared_prefs/phoshdroid_prefs.xml` to `<string name="gpu_mode">software</string>`,
   then stop and start the desktop). PASS when: the log says `-> software source=setting`, the guest log
   `gpu: mode=software source=setting from=host`, the session reaches `omarchy-ready`, and `egl-probe.py` run with
   the session environment prints `GL_renderer: llvmpipe (LLVM 22.1.8, ...)`. Record, so the README can say what
   slow means: frame rate of a full-screen terminal or `weston-simple-egl`-style client, `top -b -n 1` of the
   guest at idle (real `/proc/stat` is blocked, use the host `top`), cold start to ready, and a note on
   whether the shell bar, wallpaper and a browser load. Also try `LP_NUM_THREADS=4` once in `session.env`.
3. **A device with no Adreno node** (any non-Qualcomm phone, Android 12+): Graphics = Auto should log
   `kgsl-usable=false -> software`; then Graphics = Adreno GPU (KGSL) on the same phone answers the open
   question above (does the old block boot there by Mesa's own fallback?).
4. **The fallback**: on the tablet, force a KGSL failure the session can see, e.g. `gpush.sh` a copy of
   `session-child.sh` whose first line after the shebang is `export MESA_LOADER_DRIVER_OVERRIDE=nonexistent`
   (restore by restarting the APK sync), Graphics = Auto. PASS when `/tmp/omarchy-session.log` has
   `gpu: Hyprland exited <rc> after <n>s in kgsl mode; ...` then `gpu: mode=software source=auto from=fallback`,
   the desktop comes up, `$XDG_RUNTIME_DIR/omdroid-gpu-fallback` exists, and a second cold start does not (the
   launcher wipes it). If the stand-in does not make Hyprland die within 15 s, the fallback is unexercised: say so.
5. **The phantom decision**, from `logcat -s Phoshdroid:* | grep limits:`:
   - tablet (global unset, property set by hand, `install.sh` grant held):
     `limits: phantom-procs sdk=<n> setting=unset write-secure-settings=true -> wrote settings_enable_monitor_phantom_procs=false`
     then `adb shell settings get global settings_enable_monitor_phantom_procs` prints `false`. A second start:
     `setting=false ... -> nothing to do`.
   - an Android 12+ phone with no grant and the monitor on:
     `... write-secure-settings=false -> tell user: adb shell settings put global settings_enable_monitor_phantom_procs false`
     and the notification reads "Android may stop desktop apps. Expand for the fix." with the command when
     expanded. After running the command: `-> nothing to do`.
   - Settings -> Advanced -> "Lift Android's child-process limit" off: `limits: ... switched off in Settings`.
   - Evidence that the limit matters: `adb shell dumpsys activity processes | grep -i phantom` count during a `yay` build.
6. **Memory callbacks**: `logcat -s Phoshdroid:* | grep memory:` during a heavy session (a browser plus the
   shell); a line is the answer "yes, Android asked", silence is "no".

## Risks

- **The default KGSL path changed shape**: with `auto` on an Adreno phone Hyprland is now a child of
  `session-child.sh`, not its `exec`. The wait loop forwards `TERM`/`INT`/`HUP` and relays the exit code, and
  the fake-Hyprland tests cover exit codes and the signal flag, but a real stop was not run (no device). The
  off switches are `OMDROID_GPU_FALLBACK=0` and an explicit Graphics choice.
- **A device where KGSL "works" but is wrong** (a renderer that starts and draws garbage) is not detected; only a
  Hyprland that exits within 15 s is. A slow KGSL failure (a hang) is not caught either.
- **Every cold start on a device where KGSL fails pays the failed attempt** (up to 15 s) because the marker lives
  for one launch only. That is deliberate (a transient failure must not pin software for ever); the user can set
  Graphics = Software.
- **`pkill -x quickshell` / `pkill -f omarchy-launch-shell`** in the fallback assume `procps` is in the image
  (stderr is silenced if not; then a leftover shell could keep the one-shot launch lock, which is removed too).
- **Software mode and GL clients**: Chromium in the image is forced to `--use-angle=vulkan` (freedreno ICD), which
  is gone in software mode; expect a slow start and CPU compositing. `omarchy-launch-shell` shell is CPU-rendered
  in both modes already. Not changed (image-owned file).
- **llvmpipe thread count** follows the real CPU count (8 on these phones) at 3200x1971; it can compete with
  everything else. `LP_NUM_THREADS` is the knob; no default was set without a measurement.
- **Writing a global setting** is a bigger side effect than the accessibility merge; it only happens with the
  grant, it is logged, and it has an off switch. On API 31 builds before QPR3 the write is a no-op.
- `FeatureFlagUtils` on a vendor ROM may differ from AOSP; the read-back after the write catches a write that
  does not stick, not a ROM that ignores the flag.

## What I did not do

- No device run, no APK assembly, nothing pushed (brief). Every device row above is PENDING.
- Did not change `AssetExtractor.kt`, `LauncherActivity.kt`, `app/build.gradle.kts`, `README.md`, any `start.sh`
  line outside the GPU block, `omarchy-watch.py` or `omdroid-ui.sh`; no new overlay file.
- Did not touch the image's `chromium-flags.conf` or the Hyprland config for software mode.
- Did not add a persistent "KGSL failed on this device" memory across launches.
- Did not read `SessionExit`'s retry window from a setting; the interaction is documented in the contract section 9.
- virgl, ANGLE and any Mali/Xclipse/PowerVR hardware path stay "not shipped" (no driver in the image, no DRM node).
