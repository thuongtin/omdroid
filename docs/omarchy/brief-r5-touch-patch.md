# Brief R5-TOUCH-PATCH: give nested Hyprland a touch device (aquamarine `wl_touch`)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. You have NO device in this run (another agent owns the tablet).

Repo: `<repo>` (branch `main`, read `AGENTS.md`).
Read first: `docs/omarchy/r5-omamobile-research.md` section 4 (the patch, sized, with file:line)
and `docs/omarchy/r4-touch-research.md` (the whole touch path).
Report, created in your FIRST calls and updated after every step:
`docs/omarchy/r5-touch-patch-report.md` (STATUS TABLE rows P1-P6, `PENDING` until proven).
Scratch: `<scratch>/omarchy/r5/touch-patch/` (sources, build trees, outputs).

## Why

On the tablet a finger never reaches the desktop: Termux:X11 sends XI2 touch, wlroots 0.20's X11
backend turns it into a `wlr_touch`, cage 0.3.1 offers `wl_touch` to its client (Hyprland), and
there it dies, because aquamarine's Wayland backend (the guest runs Hyprland nested, so this is
its input backend) binds `wl_pointer` and `wl_keyboard` and never `wl_touch`
(`hyprctl -j devices` on the device: `touch: []`). The app now works around it by turning taps
into mouse clicks. Phil wants a mobile UI (gestures, swipes), which needs real touch. Hyprland
itself already handles a backend touch device (`Compositor.cpp` listens for `newTouch`).

## The exact build that is in the guest today

- `manifest/components.lock` and `manifest/patches.lock` of the upstream bundle, extracted at
  `<scratch>/omarchy/upstream/BlackFireAlex-omarchy-android-0f4cee8/`: aquamarine
  base revision `a79fb21b2e2a82dd061a6d071802bcf38bd5c383` plus
  `patches/aquamarine/0001-wayland-carry-proven-Android-KGSL-buffer-pipeline.patch`
  (sha256 in `patches.lock`).
- The installed library: `/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0` (plus the
  `.so.13` and `.so` links) inside the guest image `app/src/main/assets/rootfs.bin` (a gzipped
  tar, read-only for you: extract single members with `tar -xzOf`).
- The upstream build recipe: `builder/README.md`, `builder/guest/build-graphics.sh`,
  `builder/guest/packages.txt`, `builder/guest/audit-graphics.sh` in the same bundle directory.
  Read them before building: reuse their configure flags and install prefix exactly.
- Guest library versions that the new build must stay ABI-compatible with: glibc 2.43,
  hyprutils 0.14.1, wayland 1.26.0, libdrm 2.4.134, libinput 1.31.3, mesa 26.2.1 (from the
  guest's `/var/lib/pacman/local/`).

## Steps

### P1. Reproduce the current library
Clone aquamarine, check out `a79fb21b…`, apply the 0001 patch (verify its sha256). Build it for
aarch64 with the upstream recipe's flags. Build environment, in this order of preference:
1. this guest image itself as an arm64 container: `docker import --platform linux/arm64
   app/src/main/assets/rootfs.bin omdroid-guest:0.0.14`, run it with `--platform linux/arm64`
   (qemu-aarch64 binfmt is registered on this machine), install only the build tools from
   `builder/guest/packages.txt` that are missing (`pacman -S --needed`, never `-Syu`; if pacman
   insists on a sync, record exactly what it upgraded);
2. the upstream builder's pinned base `danhunsaker/archlinuxarm:20260517`.
Compiling under qemu is slow: run long builds detached (`docker run -d ...`, then read
`docker logs`), never as a foreground call longer than 400 s, never as a Hermes background job.
Proof: compare your build with the installed library: SONAME, the exported dynamic symbol list
(`nm -D --defined-only | sort | diff`), `readelf -d` NEEDED entries, and the highest `GLIBC_`
symbol version required (must not exceed what glibc 2.43 provides). Byte-identical is not
expected; the same symbols and NEEDED set is.

### P2. Write the patch
Add a `CWaylandTouch : public ITouch` to the Wayland backend, modelled on `CWaylandPointer`
(research §4 gives the file:line of every piece): create it when the parent's `wl_seat`
advertises `WL_SEAT_CAPABILITY_TOUCH` (and drop it when the capability goes away, as the
pointer does), map `wl_touch` `down/up/motion/frame/cancel` to `ITouch::SDownEvent`,
`SUpEvent`, `SMotionEvent`, `SCancelEvent` (and frame, if `ITouch` has it), with positions
normalised the way the libinput path (`Session.cpp`) produces them (find out whether `ITouch`
expects 0..1 or pixels, and the output size it is relative to), and the timestamp unit the
other events use. Emit `events.newTouch`. Keep the change self-contained and in upstream style.
Write it as `rootfs/patches/aquamarine/0002-wayland-add-wl_touch-input.patch` (git format-patch,
applies on top of 0001, a commit message that says why), and keep the 0001 patch beside it
(copy it from the bundle) so the series is complete in this repo.

### P3. Build the patched library
Same environment as P1; then the same comparisons: SONAME and NEEDED unchanged, every symbol of
the old library still exported (new ones allowed), GLIBC version requirement unchanged.
Install a copy of the result at
`<scratch>/omarchy/r5/touch-patch/out/libaquamarine.so.0.14.0` with its sha256.

### P4. A test without the device (best effort, cap 20 calls)
Inside the container, prove the touch path runs: e.g. a minimal Wayland client or compositor pair
that offers a seat with touch (a headless wlroots compositor such as cage with a fake touch, or a
small C test program that links the new library, creates the Wayland backend against a parent
that exposes `wl_touch`, sends down/motion/up and checks the `ITouch` events). If nothing
workable fits in the cap, say so and leave the proof to the device phase.

### P5. Build script in the repo
`rootfs/build-aquamarine.sh`: the whole P1-P3 recipe as one script (pinned revision, patch
sha256s, container image, flags), writing the library to a path the packager can use, and
printing the comparisons. `bash -n` it and run it once end to end.

### P6. Report
STATUS TABLE plus: "The patch" (what it does, line counts), "ABI checks" (the numbers), "Test",
"How it gets onto the device" (two options the parent will choose from: the packager installs
the library into the image; or the APK carries it in the guest overlay so `GuestOverlay` syncs it
into an existing install, with the file size), "What the device phase must prove" (exact
commands: `hyprctl -j devices` lists a touch device; a touch tap on a bar workspace switches
workspace with `touchMode = "3"`; two-finger behaviour), "Not verified".

## Hard rules

- No adb, no device tool, no gradle, no `./install.sh`. Never edit `app/**`, `termux-x11/**`,
  `rootfs/package-omarchy-rootfs.sh`, `rootfs/overlay/**` or `rootfs/overlay/etc/phoshdroid/**`
  (another agent owns the overlay this round). You create `rootfs/patches/aquamarine/**`,
  `rootfs/build-aquamarine.sh` and your report, nothing else in the repo.
- Never modify `app/src/main/assets/rootfs.bin` or the running guest on the tablet.
- No git command that changes anything in the repo (your aquamarine clone in scratch is yours).
- Docker: name every container and image you create with an `omdroid-` prefix and remove the
  containers you started when you finish (`docker rm -f <name>`, by name, never a pattern or
  `prune`). Do not touch other containers or images on this machine.
- Never `pkill -f`. No `sleep N; tail` polling: read `docker logs --tail` when you need it, and do
  other work in between.

Final reply, at most 8 lines: P1-P6 with their decisive facts, the patch's size, the library
sha256, and the two delivery options in one line each.
