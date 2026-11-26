# R8 dock input report: the dock's keyboard and mouse drive Omarchy on the monitor

Brief: `docs/omarchy/brief-r8-dock-input.md`. Worker: Paseo agent `5af20376` (parent `f8d5582c`),
working in the main checkout `<repo>` (branch `main`).
Scratch: `<scratch>/omarchy/r8/input/`.

## STATUS TABLE

| Step | What | Verdict | Proof |
| --- | --- | --- | --- |
| I0 | test4 install + repair-links check (ld, gcc, yay cbonsai) | **PASS** | install sha `8e7a7266…a3a8ca2e0` PASS (`lastUpdateTime 14:17:57`); cold start handover +78.7 s (first start after the update: the repair runs), desktop PASS +80.3 s, `probe.sh -q` PASS; `omdroid-repair-links: restored 1830, already present 2, failed 0`; `/usr/bin/ld` 2500416 B present; gcc 16.1.1 hello world `gcc_rc=0`, prints `hello r8`; `yay -S --noconfirm cbonsai` rc 0 (makepkg compiled `cbonsai.c` with cc, installed), `cbonsai -p -L 5` rc 0 (21696 B of curses output), `yay -R --noconfirm cbonsai` rc 0, `pacman -Q cbonsai` then `was not found` (14:21:00-14:21:22, TERM=xterm-256color, run inside the session with `sx.sh`) |
| I1 | reproduce: simulated display + uhid kbd/mouse, Settings focused on display 0 | **PASS** (failure reproduced on test4) | overlay display `1920x1080/160` = display 18, `dock: docked display=18 1920x1080@160 kbd=1 mouse=1`, X activity `topResumedActivity` on Display #18; Settings search (`com.android.settings.intelligence/.search.SearchActivity`) started on display 0 holds focus (`mTopFocusedDisplayId=0`, `mCurrentFocus=…SearchActivity`); uhid `type r8typed\n` -> the Settings search field reads `text="r8typed"` (uiautomator), the foot reader on the docked desktop got nothing (`/tmp/r8-typed.txt` absent); uhid mouse 15 x (+20,+12) -> `hyprctl cursorpos` `{256,192}` before and after; Android pointer controller `Pointer Display ID: 0` |
| I2 | keys to X while docked (KeyInterceptor) | **PASS** (build1) | build1 = tree `f60c7b8` (termux-x11 `c7d06cd`), sha256 `95c86b38…ec2c337a`, installed 14:31:14; cold start while docked: `launch: handover done display=18 on-target=true`, then `KeyInterceptor: input: docked capture on display=18 kbd=2 pointer=3`; Settings search keeps focus on display 0 (`mTopFocusedDisplayId=0`, `mCurrentFocus=…SearchActivity` before and after); uhid `type r8typed\n` -> the foot reader on the docked desktop wrote `/tmp/r8-typed.txt` = `r8typed`, the Settings search field stays empty; uhid SUPER+Return -> a new `foot` (`omarchy@localhost:~`, pid 11738) on the docked monitor |
| I3 | pointer to X while docked (accessibility motion events) | **PASS** (build1) | API: `AccessibilityServiceInfo.setMotionEventSources(SOURCE_MOUSE \| SOURCE_TOUCHPAD)` + `AccessibilityService.onMotionEvent` (API 34, in the compileSdk 35 jar, no reflection; AOSP 16: events from those sources "are not sent to the rest of the system"). Settings search focused on display 0 throughout. Motion: uhid 10 x (+10,0) -> `hyprctl cursorpos` x 1375 -> 1787 (+412), 10 x (0,+10) -> y 540 -> 951, 50 x (-2,0) -> x -340, 50 x (0,-2) -> y -339 (gain about 2 px per count when slow, 3.4-4.1 fast: Android pointer acceleration, then X acceleration on the relative motion). Focus: Omarchy runs `follow_mouse = 1`, so moving onto foot `r8a`/`r8b` made each the active window (a click is not needed for focus here; `hyprctl keyword` cannot switch it off on the Lua config parser). Buttons at a client: in foot `r8a` (showing `seq 1 400`) a left click then a right click 4 lines lower (foot `select-begin` / `select-extend`) left the primary selection `359…377` (`wl-paste --primary`); wheel: 6 clicks up changed 4922 px of the foot text area (grim, bbox 14,18-938,1000), 6 clicks down restored it to 0 changed px; middle/left/right/wheel also logged by an X client on the outer X server (`xbtn.py`: press 1, 3, 2, 4 x4, 5 x2). Logs: scratch `i23-build1.log`, `i3c-build1.log`, `i3d-build1.log` |
| I4 | undock / re-dock / force-stop: Android keeps input | **PASS** (build1) | Undock (`settings delete global overlay_display_devices`, 14:46:00): `KeyInterceptor: input: capture off` at 14:46:00.478, the X activity back on Display #0; Settings search focused, uhid `type undocked2\n` -> Settings field `text="undocked2"`, desktop reader got nothing; uhid mouse -> the Android arrow moves on the tablet screenshot (48x48 regions 1136,720 -> 2080,1480) and Android's dispatcher has the mouse hovering the Settings window (`TouchStatesByDisplay … mDeviceStates=72 … hoveringPointers=[Pointer(id=0, MOUSE) at (656.845, 2090.58)]`), `hyprctl cursorpos` does not follow. Re-dock: `input: docked capture on display=20 kbd=2 pointer=3` 1 s after the display came back, X activity on Display #20. Force-stop while docked (14:43:43): app pid gone, Android drops the service (`Bound services:{}`, `enabled_accessibility_services` = `null`); uhid `type killed1\n` -> Settings field `text="killed1"`; mouse hovering Settings at (654.86, 2218.21), `HOVER_MOVE` 1.2 s old in the dispatcher queue, the arrow drawn on the tablet (screenshot crop). Next launch re-enables the service and capture (`input: docked capture on display=19` 3 s after `am start`). Logs: `i4-build1.log` (force-stop), `i4b-build1.log` (undock, re-dock) |
| I5 | test5 APK for Phil + manual test | **PASS** | `<mesh dir>/omdroid-0.0.15-test5.apk` = build1 (tree `f60c7b8`, termux-x11 `c7d06cd`; every later commit is docs only), 1715789306 B, sha256 `95c86b38454af31d37d3ba23a7486d1743c0b1d4424ab1c6c26111e6ec2c337a`; `curl -s http://<mesh host>:8899/omdroid/omdroid-0.0.15-test5.apk \| sha256sum` gives the same sum. "Manual test for Phil" below |
| I6 | gate (unit tests, lint) + README Docking + contract section 8 | **PASS** | `./gradlew :app:test :app:lintDebug --console=plain`: BUILD SUCCESSFUL, `testDebugUnitTest` and `testReleaseUnitTest` ran, `unit-count.py` `unit tests 138 failed 0` (100 before + `DockedInputTest` 24 + `DockedPointerTest` 14), lint `0 errors, 32 warnings` (report 14:48). README "Docking" gains "Keyboard and mouse belong to the desktop while docked"; `launch-contract.md` §8 gains "Input while docked" and the `KeyInterceptor` log lines |
| I7 | cleanup (overlay display, uhid, stay-awake 15, probe PASS) | PENDING | |

## Device state changes (restore commands)

| Setting | Recorded value | Set to | Restore command | Restored / read back |
| --- | --- | --- | --- | --- |
| `global overlay_display_devices` | `null` | `1920x1080/160` (I1-I4) | `adb -s $TABLET_SERIAL shell settings delete global overlay_display_devices` | PENDING |
| `global stay_on_while_plugged_in` | `15` | not changed (Phil asked for stay-awake while plugged in) | leave at `15` | PENDING |
| uhid keyboard + mouse (`uhid-dock.py serve`, Android devices `r8 dock keyboard` / `r8 dock mouse`) | absent | registered 14:28:51 | `uhid-dock.py send quit` (or kill the serve job: `hid` unregisters at EOF) | PENDING |

The test devices, as Android classifies them (`dumpsys input`): `r8 dock keyboard` = `IsExternal: true`,
`Sources: KEYBOARD`, `KeyboardType: 2` (alphabetic), exactly the Corne's line; `r8 dock mouse` =
`IsExternal: true`, `Sources: MOUSE`. The Magic Trackpad is `MOUSE | TOUCHPAD` (a touchpad mapper with
gestures), so the uhid mouse covers its pointer path but not its two-finger scroll or tap-to-click:
those are left to Phil's manual test.

## Log

### What was built (termux-x11 `e2a8fb1` keys, `c7d06cd` pointer)

- **When capture is on** (`DockedInput.captureWanted`): the X activity is alive, started (visible),
  on a display other than the built-in one, connected to the X server, the keyguard is not up,
  and Samsung DeX is off. Anything unknown counts as false, so a failed check leaves Android its
  input. DeX is excluded on purpose: there the pointer and focus already reach the monitor, and a
  capture would draw two cursors on one screen. The keyguard rule keeps the PIN typeable.
- **Keys** (`KeyInterceptor.onKeyEvent`): while docked, every key from a physical alphabetic
  keyboard, and the keys a mouse synthesizes for its side buttons, goes to X through
  `MainActivity.handleKey`, whatever Android has focused. A release follows its press (a key held
  across the dock moment is released where it was pressed). Power, sleep, volume, media,
  brightness, camera and call keys stay Android's. **The tablet's keyboard cover counts like any
  physical keyboard**: Android reports it as an internal alphabetic keyboard, and docked it types on
  the monitor; Android apps on the tablet keep the touchscreen and the on-screen keyboard.
- **Pointer** (`KeyInterceptor.onMotionEvent` + `DockedPointer`): while docked the service asks
  for `SOURCE_MOUSE | SOURCE_TOUCHPAD` with `AccessibilityServiceInfo.setMotionEventSources`
  (API 34; the platform then gives those events to the service and to nothing else). Relative
  motion comes from `AXIS_RELATIVE_X/Y` of DOWN / MOVE / HOVER_MOVE only (an Android mouse frame
  repeats its delta on BUTTON_PRESS, UP and the HOVER_MOVE after UP), buttons from the button
  state (primary, tertiary, secondary -> X 1, 2, 3), the wheel at one X click per notch
  (`AXIS_VSCROLL/HSCROLL`), and a touchpad two-finger scroll (`CLASSIFICATION_TWO_FINGER_SWIPE`,
  `AXIS_GESTURE_SCROLL_X/Y_DISTANCE`, 120 px = one click) as wheel. Pinch and three/four-finger
  swipes are dropped. Touchscreen and stylus are other sources and are never taken.
- **Lifecycle**: `KeyInterceptor.recheck()` runs on the activity start, stop, destroy, display
  moves, new intents, focus changes, display add/remove/change, screen on/off and unlock, before
  each key press, and at most every 500 ms from pointer events. A change applies the pointer
  sources at once in both directions and releases any X button still held. One line per change:
  `input: docked capture on display=<id> kbd=<n> pointer=<n>` / `input: capture off` (tag
  `KeyInterceptor`; the counts include the keyboard cover's keyboard and touchpad, which Android
  lists even with no cover attached).
- **Android's own cursor while captured**: it keeps moving on the tablet screen in step with the
  mouse (Android's PointerChoreographer draws it before the accessibility filter runs), but no
  Android window gets hover or clicks (`TouchStatesByDisplay` lists no hovering mouse). Measured:
  screenshots of display 0 show the arrow move between 880,472 and 1808,1224 while capture is on.
- **Crash or force-stop**: the service lives in the app process, so the platform drops it with the
  process (`Bound services:{}`) and input returns to Android at once. Android also removes it from
  `enabled_accessibility_services` on a force-stop; the next Omdroid launch writes it back.
- **Pointer speed**: the relative deltas already carry Android's acceleration and the X server
  accelerates relative motion again (about 2 px per count slow, 3.4-4.1 fast with the uhid mouse).
  If the trackpad feels too fast, that is the knob to turn next.

## Manual test for Phil (dock, Corne, Magic Trackpad)

APK: http://<mesh host>:8899/omdroid/omdroid-0.0.15-test5.apk (sha256 `95c86b38454af31d37d3ba23a7486d1743c0b1d4424ab1c6c26111e6ec2c337a`).
Keep `adb logcat -s KeyInterceptor:* Phoshdroid:* | grep input:` running over wireless adb.

1. Install test5, open Omdroid on the tablet, then plug in the dock. The desktop moves to the
   monitor and the log prints `input: docked capture on display=<id> kbd=<n> pointer=<n>`.
2. Tap any Android app on the tablet so it has focus, then type in a terminal on the monitor with
   the Corne: the text lands on the monitor, nothing reaches the tablet app.
3. SUPER shortcuts on the Corne: SUPER+Return opens a terminal on the monitor, SUPER+W closes it,
   SUPER+1/2 switch workspaces. The tablet app drawer must not open.
4. Trackpad: the Hyprland cursor moves on the monitor (say if the speed is wrong). Android's arrow
   also moves on the tablet screen but clicks nothing there: that is expected.
5. Clicks: press or tap to click a window and a bar item; two-finger click (right click) in a
   terminal after a left click extends a selection.
6. Two-finger scroll in a terminal with long output (`seq 1 500`): the scrollback moves; say if the
   direction or the speed feels wrong.
7. Touch the tablet screen while docked: Android apps still answer touch and the on-screen keyboard.
8. Unplug the dock: the log prints `input: capture off`, the desktop comes back to the tablet in the
   mobile layout, and the tablet behaves as before (touch, keyboard cover if attached).
