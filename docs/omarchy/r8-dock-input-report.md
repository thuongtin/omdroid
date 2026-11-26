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
| I5 | test5 APK for Phil + manual test | PENDING | |
| I6 | gate (unit tests, lint) + README Docking + contract section 8 | PENDING | |
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
