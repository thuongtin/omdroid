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
| I3 | pointer to X while docked (accessibility motion events) | PENDING | |
| I4 | undock / re-dock / force-stop: Android keeps input | PENDING | |
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
