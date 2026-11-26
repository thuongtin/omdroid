# Brief R8-DOCK-INPUT: the dock's keyboard and mouse drive Omarchy on the monitor

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. The tablet's adb serial is in your launcher prompt (wireless adb,
`ip:port`); export it as `TABLET_SERIAL` and never write it into a repo file. Phil's phone is also
on adb: never run any command against it.

Repo: `<repo>` (branch `main`, read `AGENTS.md`). Read first:
`docs/omarchy/launch-contract.md` §8 (docking), `docs/omarchy/r7-dock-device-report.md` (how the
dock was proven with a simulated display, the tools used), `docs/omarchy/r4-input-report.md` (the
key interceptor, the uhid synthetic keyboard method), and in the `termux-x11` submodule
`app/src/main/java/com/termux/x11/utils/KeyInterceptor.java`, `MainActivity.java`
(`shouldInterceptKeys`, `handleKey`, `onWindowFocusChanged`, `KeyboardCapture`),
`input/TouchInputHandler.java` (mouse paths, pointer capture), `LorieView.java`
(`sendMouseEvent(x, y, button, down, relative)`, `sendMouseWheelEvent`), and
`res/xml/accessibility_service_config.xml`.
Report, created in your FIRST calls and updated after every step:
`docs/omarchy/r8-dock-input-report.md` (STATUS TABLE I0-I7). Scratch:
`<scratch>/omarchy/r8/input/`.

## The problem, measured (parent, on the tablet with Phil's real dock)

Phil docked the tablet (HyperOS, Android 16.0, SDK 36) to a USB-C dock with a 3440x1440 HDMI
monitor, a `foostan Corne` keyboard and an `Apple Inc. Magic Trackpad`. The display side works:
Omarchy fills the monitor. But typing and the trackpad never reach Omarchy; Android gets them.
Capture: `<scratch>/omarchy/r7/input/capture/` (`b-*` = while he typed):
- `com.termux.x11.MainActivity` is resumed on **display 14** (`HDMI Screen`, 3440x1440), but
  `mTopFocusedDisplayId=0` / `FocusedDisplayId: 0` and the focused window is another app on the
  tablet screen (`b-window-focus.txt`, `b-dumpsys-input.txt`). Keys go to the focused display.
- `PointerChoreographer`: the only mouse pointer controller has `Pointer Display ID: 0`, and the
  `DisplayTopologyGraph` is empty: the cursor cannot leave the tablet screen, so the trackpad can
  never click on the monitor to move focus there.
- `getevent.txt` shows the kernel received both devices (event19, event21).
- `KeyInterceptor` only filters keys while `MainActivity.hasWindowFocus()` (its `recheck()` and
  `shouldInterceptKeys()`), so it never takes them either.

## The design (decided by the parent)

While docked (the X activity is on a non-default display), **physical keyboards and pointing
devices belong to Omarchy, independent of Android focus**; the tablet's touchscreen stays Android.
Undocked, everything behaves exactly as today.

1. **Keys.** The accessibility `KeyInterceptor` keeps key filtering enabled while docked and, for
   key events from a physical keyboard (`InputDevice` not virtual, has `SOURCE_KEYBOARD`, alphabetic
   or with keys; decide and say how you treat the tablet's own keyboard cover, which is a physical
   keyboard too), forwards them to the X server via the same path `handleKey` uses, even when
   `MainActivity` has no window focus, and consumes them. Keep releases consistent (a key pressed
   before docking, released after).
2. **Mouse and trackpad.** Use the accessibility motion-event API (`AccessibilityServiceInfo
   .setMotionEventSources(...)` + `AccessibilityService.onMotionEvent(MotionEvent)`, API 34; verify
   the exact names, levels and whether intercepted events are consumed, in the SDK the project
   compiles against and in AOSP for 16; reflection if `compileSdk` 35 lacks something). While
   docked, take `SOURCE_MOUSE` (and the touchpad source if separate) events and feed X: relative
   motion (`AXIS_RELATIVE_X/Y`) as relative pointer motion, buttons (primary, secondary,
   tertiary: press/release), wheel (`AXIS_VSCROLL/HSCROLL`), and the touchpad two-finger scroll
   (Android 14+ reports it as `CLASSIFICATION_TWO_FINGER_SWIPE` with
   `AXIS_GESTURE_SCROLL_X/Y_DISTANCE`; check). Hyprland draws the cursor on the monitor. Say what
   happens to Android's own cursor on the tablet screen while this is active.
3. **Lifecycle.** Enable both filters on dock, restore the stock behaviour on undock and when the
   X activity is gone; never leave Android without keyboard or mouse after an undock or a crash
   (if the service cannot tell, it must fail open: pass the event through). Log one line per state
   change: `input: docked capture on display=<id> kbd=<n> pointer=<n>` / `input: capture off`.
4. Fallback to think about but not build unless (1)-(2) fail on the device: when the X window does
   get focus on the monitor, `requestPointerCapture()` gives relative mouse events to it.

## Steps

**I0. Baseline + the pending repair check.** The tablet runs test3. Install the parent's test4
first: `<mesh dir>/omdroid-0.0.15-test4.apk` (sha256 `8e7a7266…a3a8ca2e0`,
carries `omdroid-repair-links.sh`). Cold start, `probe.sh -q`, then in the guest:
`grep omdroid-repair-links /tmp/omarchy-session.log` (expect `restored 1830`), `ls -la /usr/bin/ld`,
compile and run a hello-world with `gcc`, and `yay -S --noconfirm cbonsai`, `cbonsai -p -L 5`
exit code, `yay -R --noconfirm cbonsai` (`TERM=xterm-256color`). Record each; a failure here is a
FAIL row, not a blocker for the input work.
**I1. Reproduce without Phil.** Simulated display (`settings put global overlay_display_devices
1920x1080/160`, as in the r7 device report) + a uhid keyboard and a uhid mouse (the r4 method;
make the mouse a real HID mouse with relative X/Y, 3 buttons and a wheel). Put another app in front
on display 0 (e.g. Settings) so the X window is not focused. Show the failure: keys typed reach
the Settings search box or nothing, `hyprctl cursorpos` does not move. If uhid devices are not
treated like the real dock devices (e.g. `isExternal`), say so and adapt.
**I2. Keys** (design 1), unit tests for any pure decision (which device counts, docked or not).
Gate, commit, build, install, re-test I1: a `foot` window on the docked desktop receives typed
text while Settings is focused on the tablet; `SUPER+Return` opens a terminal there.
**I3. Pointer** (design 2), same loop: `hyprctl cursorpos` follows uhid relative motion, a left
click focuses a window, right click and wheel reach a client (use `wev` or `xev` if present, or a
`foot` scrollback), and Android's cursor behaviour on the tablet screen is recorded.
**I4. Undock** (remove the simulated display): keys and mouse go back to Android (the Settings
search box gets the typed text, the Android cursor moves), log `input: capture off`. Re-dock: on
again. Kill the app (`am force-stop`) while docked: Android keeps keyboard and mouse.
**I5. Hand to Phil.** Copy the final APK to `<mesh dir>/omdroid-0.0.15-test5.apk`,
verify `curl -s http://<mesh host>:8899/omdroid/omdroid-0.0.15-test5.apk | sha256sum` equals the
file, and write "Manual test for Phil" (6-8 steps with the real dock, the Corne and the Magic
Trackpad: typing, SUPER shortcuts, pointer, clicks, two-finger scroll, touching the tablet screen
while docked, undock, and the log lines to read: `adb logcat -s KeyInterceptor:* Phoshdroid:* | grep input:`).
**I6. Gate + docs.** `./gradlew :app:test :app:lintDebug --console=plain` + `unit-count.py` (from
`unit tests 100 failed 0`, lint 0 errors), README "Docking" + launch contract §8 updated for input.
**I7. Cleanup.** Overlay display removed, uhid devices closed, stay-awake left at `15` (Phil asked
for the tablet to stay awake while plugged in: do not restore it), session undocked in mobile UI,
`probe.sh -q` PASS.

## Build notes

`~/.gradle/caches` is a broken root-owned mount on this machine: build with
`GRADLE_USER_HOME=<scratch>/omarchy/r7/gradle-home` (warm cache) and the heap the
project file sets; `gradle.properties` is modified by Phil's other session: never edit, stage or
revert it. Delete `app/build/outputs/apk/debug/app-debug.apk` before `assembleDebug`, run it in the
foreground, copy the APK to your scratch dir in the same command. Submodule edits: commit in
`termux-x11` on `phoshdroid-integration`, then the pointer in the main repo.

## Hard rules

- Files you may change: `termux-x11/**` (branch `phoshdroid-integration`), `app/src/main/**`,
  `app/src/test/**`, `docs/omarchy/launch-contract.md` §8, README "Docking", your report,
  `docs/omarchy/tools/**` (new files). Comments in shell scripts: no apostrophes.
- Commit each finished step at once with exactly its paths; never `git add -A`, never `git stash`.
  No push, tag or release.
- Never `pkill -f`; kill only PIDs you started. No long `sleep; tail` polls.
- If a command waits on an approval, do not retry or rephrase it; note it and go on.
- If the call budget runs low: write the report state, run I7, commit, then reply.

Final reply, at most 10 lines: I0-I7 with the decisive number or log line each, the API that
carried the mouse, what happens to Android's cursor, the commits, the test5 link and sha256, and
what Phil must try with the real dock.
