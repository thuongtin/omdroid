# Brief R5-TOUCH-DEVICE: real touch on the tablet (aquamarine wl_touch + direct touch)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. You can see images: view the screenshots you take.

Repo: `<repo>` (branch `main`, read `AGENTS.md` first).
Read whole: `docs/omarchy/r5-touch-patch-report.md` (the patch, the ABI checks, "What the device
phase must prove"), `docs/omarchy/r4-touch-report.md` (how taps were tested: `bartest.py`,
`focustest.py`, `xtap.py`), and `docs/omarchy/r5-mobile-ui-device-report.md` (the mobile UI and
what its gestures needed under simulated touch).
Report, created in your FIRST calls and updated after every step:
`docs/omarchy/r5-touch-device-report.md` (STATUS TABLE rows D0-D7, `PENDING` until proven).
Scratch: `<scratch>/omarchy/r5/touch-device/`.

## Why

A finger on the tablet never reached Omarchy as touch: aquamarine's Wayland backend (Hyprland's
input backend when nested in cage) bound no `wl_touch`. The app works around it with Termux:X11
"simulated touch" (`touchMode = "2"`): a tap is a click, but a quick flick does nothing and every
swipe needs a half-second hold first. That makes the new Omamobile mobile UI (dock swipe-up, back
edge swipe, card flicks, pull-down) awkward. Commit `56ed028` adds the touch device to aquamarine
(`rootfs/patches/aquamarine/0002-wayland-add-wl_touch-input.patch`); the built library has never
been loaded on the device. This round proves it there and, if it works, ships it with direct touch.

## The library

`<scratch>/omarchy/r5/touch-patch/out/p3-install/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0`,
1 775 168 bytes, sha256 `8514d2a65f2e10bb75d74a97cd3bc97db52f06bc19ecd0a47395aa9fdae66191`
(SONAME `libaquamarine.so.13`). `rootfs/build-aquamarine.sh` rebuilds it (docker images
`omdroid-guest:0.0.14` / `omdroid-aquamarine:0.0.14` exist; containers `omdroid-aq-build`,
`omdroid-aquamarine-builder` are still up). If the device shows a bug in the patch, fix the patch,
rebuild with that script (long compiles under qemu: detached `docker exec -d` + log file, never a
foreground call over 400 s), and say so.

## Decisions taken by the parent

- **Delivery: the APK carries the library** so an updated install gets it without re-extracting
  the guest. Put it at `rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13` (named by its
  SONAME, a regular file, not a link), with aquamarine's `LICENSE` (BSD-3-Clause) and a
  `README.md` beside it giving the sha256, the source revision, both patches and the
  `rootfs/build-aquamarine.sh` command. `start.sh` puts `/etc/phoshdroid/lib` FIRST in
  `LD_LIBRARY_PATH` (before `/opt/omarchy-android/aquamarine/lib`). Add `lib/**` to
  `syncGuestOverlay` in `app/build.gradle.kts` and copy `lib/` in the packager's "Applying
  overlay" block (`rootfs/package-omarchy-rootfs.sh`); both must list the same files (`AGENTS.md`).
  Check that `GuestOverlay` writes a 1.7 MB binary correctly (sha256 on the device equals the repo).
- **Direct touch only if proven.** `touchMode = "3"` in `LauncherActivity.kt` (the prefs block,
  ~line 552, with its comment rewritten to say why) is the goal. If D3 fails, keep `"2"`, keep the
  library (it is harmless), and report exactly what failed.
- The guest's original `/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0` stays
  untouched in the image. If you test by replacing it on the device first, back it up and put it
  back.

## Steps

**D0. Device.** `export TABLET_SERIAL=<adb serial>` (never write the serial into a repo file). Tools in
`docs/omarchy/tools/` (read a tool's head before first use). If the keyguard shows, never enter a
PIN: `BLOCKED (keyguard)`, bounded waits (4 x 380 s). Record `stay_on_while_plugged_in`, set `2`,
restore and read back at the end. `probe.sh -q` PASS on what is installed now.

**D1. The device exists (no APK change).** Push the new library into the guest (the quickest way
that a cold start does not undo), cold start, and read `./hc.sh j/devices`: `touch` must list
`wl_touch`. Also confirm with `/proc/<Hyprland pid>/maps` that the new file is the one loaded.
Under simulated touch the X server sends no touch events, so taps still arrive as clicks here;
this step only proves the library loads, Hyprland starts and the device appears. Run
`probe.sh -q` and a bar tap (still a click) for regressions.

**D2. The build.** Make the delivery change and `touchMode = "3"`. Gate:
`./gradlew :app:compileDebugKotlin :app:test :app:lintDebug --console=plain` (foreground) and
`python3 docs/omarchy/tools/unit-count.py` (expect `unit tests 63 failed 0` or more); then
`rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug --console=plain`
(foreground, 600 s timeout, never in the background). Commit the code first (exact paths,
`feat(launcher): ...` / `build(rootfs): ...`), then build, then install with `./install.sh`
(`INSTALL: PASS`, sha256). Undo the D1 replacement on the device before D3 if you made one.

**D3. Real touch, proven.** With the D2 APK, cold start, then each with numbers:
1. `j/devices` lists `wl_touch`; the library loaded is `/etc/phoshdroid/lib/libaquamarine.so.13`.
2. Positions: tap the four corners, the centre and the bar's far right; prove where each landed
   (e.g. a layer or window that reports the touch position, `WAYLAND_DEBUG=1` on a client, or
   Hyprland's cursor position after the tap). A systematic offset, scale or mirror is a FAIL with
   the measured error. The X root (3200x1971) is the size authority; Hyprland is 1600x985 logical.
3. The bar: 9/9 targets react to a touch tap (`bartest.py` or its equivalent).
4. Windows: focus by tap (`focustest.py`), typing still lands in the tapped window.
5. Mobile UI gestures with a plain quick swipe (no hold), `adb shell input touchscreen swipe ...`
   and `motionevent DOWN/MOVE/UP`: dock swipe-up opens the switcher, pill swipe goes home, a
   card flick closes a window, the back gesture from x <= 20 and from x = 3, the quick-settings
   pull-down. Screenshot each result and view it.
6. Long press and drag: a long press on the pill (its QML long-press) and a window drag.
7. Two fingers (best effort): `adb shell input` injects one pointer; try a synthetic multi-touch
   screen (`cmd uinput` or `hid` with a touchscreen descriptor, see
   `docs/omarchy/r4-input-research.md` for how the keyboard round used them) for a two-finger
   scroll in a terminal and Hyprland's touch workspace swipe
   (`hyprctl getoption gestures:workspace_swipe_touch`). If it cannot be injected, say so; Phil
   will test with his fingers.

**D4. Regressions.** Keyboard capture still works (SUPER+2 switches workspace via the synthetic
keyboard from the keyboard round, or `launch: key-capture enabled` in logcat plus one key test).
A size change still recovers by restarting only the shell (`screen.sh` rotation, then
`screen.sh reset`: density 352, auto-rotate back on). The `desktop` UI mode still works with
touch (`echo desktop > ~/.config/omdroid/ui`, cold start, bar tap; then back to `mobile`).

**D5. Decision.** Write which `touchMode` ships and why, with the D3 numbers. If `"3"` failed,
revert that line (commit), rebuild, reinstall and prove the D1 state.

**D6. Clean up.** Session in `mobile` mode, no test windows, stay-awake restored and read back,
`probe.sh -q` PASS after a cold start. Remove the two docker containers only if the patch needed
no rebuild (`docker rm -f omdroid-aq-build omdroid-aquamarine-builder`; leave the images); if
that command waits on an approval, note it and move on.

**D7. Report.** STATUS TABLE plus a section per row with commands and output, "Screenshots
viewed" (path + one-line verdict each), "What Phil should try with his fingers" (a short list),
"Not verified", and the final APK sha256 with the commit it was built from.

## Hard rules

- Files you may change: `rootfs/overlay/etc/phoshdroid/lib/**`, `rootfs/overlay/etc/phoshdroid/start.sh`
  (only the `LD_LIBRARY_PATH` lines; no apostrophes in its comments, `bash -n` after),
  `app/build.gradle.kts` (`syncGuestOverlay` only), `rootfs/package-omarchy-rootfs.sh` (the overlay
  block only), `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt` (the `touchMode` line
  and its comment only), `rootfs/patches/aquamarine/0002-*` and `rootfs/build-aquamarine.sh` (only
  if the device shows a patch bug), `docs/omarchy/tools/**` (new tools), your report.
  Never touch `rootfs/overlay/etc/phoshdroid/omamobile/**` or `omdroid-ui.sh`.
- **Commit each finished step at once** with exactly its paths (`git add <paths> && git commit`);
  never `git add -A` or `git add .`. No `git push`, no release, no GitHub writes.
- Never `pkill -f`; kill only PIDs you started, by exact PID. No `sleep N; tail` poll loops.
- If a command waits on an approval, do not retry or rephrase it; note it and go on.
- If you near your call budget, write the report state and commit before anything else.

Final reply, at most 10 lines: D0-D7 with the decisive number each, which touchMode ships and
why, the commits, the final APK sha256, what Phil should try with his fingers.
