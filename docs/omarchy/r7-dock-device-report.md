# R7 dock device round: docking on the tablet (M1-M3)

**Result:** on the fixed build (`omdroid-dock-final.apk`, tree `60fe8ef`) a live dock moves the
running session to the simulated 1920x1080 display at its full size in ~5 s, an undock brings it
back to the tablet in mobile UI, windows and PIDs survive five cycles, SUPER and typing reach the
docked desktop. Four failures of the test2 build were fixed (F1-F4, plus F5 found in the code);
one is open: a session keeps the UI scale it started with (F6).

Builds: **test2** (`a239a8c5…`, installed 08:53) ran T0-T4 and the first T2/T3; **fix1** =
**final** (`3b4166ab…`, tree `60fe8ef`, installed 09:15) ran T2b-T6 (`phase2.log`) and T2c/T3c/T8
(`final.log`). Scratch logs and screenshots: `<scratch>/omarchy/r7/device/`.

Brief: `docs/omarchy/brief-r7-dock-device.md` (with its AMENDMENT). Device: the Xiaomi tablet
(serial passed in the launcher prompt, exported as `TABLET_SERIAL`, never written here).
Scratch: `<scratch>/omarchy/r7/device/`.

## STATUS TABLE

| Step | What | Verdict | Number / log line |
| --- | --- | --- | --- |
| T0 | Baseline: install test2, cold start, probe, undocked mobile, dock lines, touch, key capture, `sudo id` | **PASS** (dock baseline) / **FAIL** (`sudo id`, not this round's fix) | install sha `a239a8c5…12fc407a0` PASS; cold start handover +7.6 s, desktop PASS +8.0 s; `dock: undocked`; `wl_touch`; KeyInterceptor bound; `sudo id` -> `omdroid-rootd: peer is not this app` |
| T1 | How a second display works on this tablet | **PASS** | `overlay_display_devices 1920x1080/160` -> display 2, `type OVERLAY`, `FLAG_PRESENTATION, FLAG_TRUSTED` (not PRIVATE), density 160; `activities_on_secondary_displays` present; `am start --display 2` Settings -> `Display #2` fullscreen; no other setting needed |
| T2 | Dock (M1 + M2) | test2: **FAIL** (F1 gap, F2 start-time mode, F3 log) / fix1: **PASS** | fix1 T2c: X activity MOVED to display 13 (same ActivityRecord), xroot = cage = monitor **1920x1080** (scale 2, logical 960x540), `x-view margins top=0 bottom=0 (display 13)`, `monitor fit 1920x1080 rc=0`, desktop UI, foot 10935 kept, switch +5.4 s, ready **+5.9 s** |
| T3 | Undock (M2) | test2: **PASS** (+F3 log) / fix1: **PASS** | fix1 T3c: back on display 0 by itself, `x-view margins top=0 bottom=165 (built-in display)`, `dock: ui mobile written (undocked)`, xroot 3200x1971, mobile UI, foot kept, ready **+29.4 s** (one `omarchy-restart-shell rc=1`, recovered by the layer remedy) |
| T4 | Pin | test2: **FAIL** (F4) / fix1: **PASS** | fix1: `pin=desktop` undocked -> desktop UI (0 omamobile); dock + undock pinned: `dock: ui desktop kept (pinned)` x2, `ui` stays `mobile`; `auto` -> mobile again |
| T5 | Repeat x5 | fix1: **PASS** | 5/5 cycles: dock 4.1 / 4.2 / 5.0 / 5.1 / 2.8 s, undock 17.4 / 15.4 / 15.7 / 11.9 / 13.6 s; X activity on displays #7-#11 and back on #0 each time; foot 24331, cage, Hyprland same pids; 0 crash lines; 1/10 switches rate-limited -> queued (superseded 1 s later) |
| T6 | Input while docked | fix1: **PASS** | uhid SUPER+Return: clients 1 -> 2 (foot 7882 on the docked monitor), typed `dockok` round trip, SUPER+W: 2 -> 1; keys via the accessibility KeyInterceptor (`MiuiInputKey: application accessibility handled this event,info=...KeyInterceptor`), capture API absent (SDK 36.0) |
| T7 | Fixes | **PASS** (F1-F5) / **F6 open** | `3ed2f47`, `9ad4c2b` (+ termux-x11 `57790ca`), `60fe8ef`; gate BUILD SUCCESSFUL, `unit tests 100 failed 0`, lint 0 errors; re-proven on fix1 (T2c-T6). F6: a session keeps its start-time scale (root cause + proposed fix below) |
| T8 | Hand-off and cleanup | **PASS** | overlay `null`, stay-awake `0`, desktop-mode `0`, freeform `0` read back; session undocked, mobile, display 0, probe PASS; final APK `omdroid-dock-final.apk` sha256 `3b4166ab…20cf0c2` |

## Settings changed on the tablet (restore list)

| Setting | Recorded value | Set to | Restore command | Restored / read back |
| --- | --- | --- | --- | --- |
| `global overlay_display_devices` | `null` | `1920x1080/160` (T1-T6) | `adb -s $TABLET_SERIAL shell settings delete global overlay_display_devices` (it read `null`) | deleted, reads `null`, 0 overlay displays |
| `global stay_on_while_plugged_in` | `0` | `2` | `adb -s $TABLET_SERIAL shell settings put global stay_on_while_plugged_in 0` | reads `0` |

## Log

### Pre-T0 (2026-11-26 ~08:55 UTC)

- **Tablet PIN-locked at round start**: asleep, woken with `KEYCODE_WAKEUP`; `isKeyguardShowing=true`,
  `trust: deviceLocked=1`, `lock_settings: CredentialType: PIN`; `wm dismiss-keyguard` does not clear
  it. No PIN typed. Parent told at once (owner action: unlock the tablet). Work that needs no unlock
  continued; a background watcher waits for `isKeyguardShowing=false`.
- Recorded before any change: installed `0.0.15-alpha` (versionCode 15, lastUpdateTime
  2026-11-25 05:58:47), a session up 1d 2h 53m (app pid 31693, proot 31779), `probe.sh -q` PASS.
  Global settings: `overlay_display_devices=null`, `force_desktop_mode_on_external_displays=0`,
  `enable_freeform_support=0`, `force_resizable_activities=1` (already on before this round),
  `enable_non_resizable_multi_window=1`, `stay_on_while_plugged_in=0`; system
  `screen_off_timeout=120000`.

### T0. Baseline (build test2, 08:53-08:56 UTC)

- Unlocked at ~08:53 UTC (`isKeyguardShowing=false`, `deviceLocked=0`); stay-awake `0` -> `2`.
- Install: `omdroid-0.0.15-test2.apk`, 1,715,859,742 B, pm install from `/data/local/tmp`
  (`install-fast.sh` in scratch = the fast path of `tools/install.sh` without its tap-driven
  fallback, which must never run against a keyguard): `pm install: Success`, installed base.apk
  sha256 `a239a8c5134f1d79ed0cbcd669d0b1049bc9cc5f8bf34aa9506c66a12fc407a0` = the brief's,
  `lastUpdateTime=2026-11-26 08:53:49`, `WRITE_SECURE_SETTINGS` granted.
- `coldstart.sh 1`: `RUN 1: handover=+7.6s (auto) desktop=+8.0s relaunch=0`, no foreign activity;
  xroot 3200x1971, cage 3200x1970, monitor 3200x1970 scale 2 (logical 1600x985), layers
  `omarchy-background`, `omamobile-dock`, `omamobile-launcher`, `omarchy-bar`, `omamobile-back` x2,
  ready marker, **`VERDICT: PASS`**. `probe.sh -q`: PASS. Screenshot `shots/t0-cold-1.png`.
- Undocked, mobile: `ui=mobile`, no `ui-pin` file (= `auto`), scan file 42 blocks with 5
  `omamobile` plugins; watcher `start pid=1765 ... ui=mobile`, `ready 3200x1970 scale 2 written`.
- Dock lines with no monitor (logcat, app pid 953):
  ```
  08:54:12.120 I/Phoshdroid: dock: undocked
  08:54:12.121 I/Phoshdroid: dock: ui mobile kept (unchanged)
  08:54:12.361 I/Phoshdroid: dock: undocked
  08:54:12.369 I/Phoshdroid: launch: key-capture enabled com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor 235ms
  08:54:12.400 I/Phoshdroid: launch: ui mobile unchanged 265ms
  08:54:19.436 I/Phoshdroid: launch: handover done display=default on-target=false 7302ms
  08:54:19.499 I/KeyboardCapture: keyboard capture API absent (needs Android 16.1+); the accessibility KeyInterceptor is the key path
  ```
  The first pair is `DockMonitor.register()` at process start, the second `dock: undocked` the
  launcher's own read in `bootstrap()`.
- Touch: `hc.sh j/devices` -> `devices mice=1 keyboards=1 touch=['wl_touch']`.
- Key capture: `enabled_accessibility_services=com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor`,
  `dumpsys accessibility` Bound services `label=Omdroid keyboard capture`,
  `BIND_ACCESSIBILITY_SERVICE: allow`. Tablet: Android 16, `ro.build.version.sdk_full=36.0` (not
  36.1), so the keyboard-capture API is absent as expected.
- **`sudo id`: FAIL.** `sx.sh 'sudo id'` -> `omdroid-rootd: peer is not this app`, rc 1.
  `/tmp/omdroid-root/rootd.log`: `2026-11-26T08:54:28 refused peer uid 10323, accepts [0] exit=1`.
  `/tmp/root-broker.log` does not exist. The guest copies are the fixed files (guest
  `omdroid-rootd.py` sha256 `a8efc399…` = repo HEAD = the APK asset; `omdroid_root.py` `2d991411…`
  likewise), so the fix ran and still refused: `PEER_UIDS = {os.getuid()} | {kernel_uid()}` came
  out as `{0}`, i.e. on the device `kernel_uid()` (SO_PEERCRED on a socketpair) returned 0 under the
  device proot, or raised `OSError`, while the client connection reports the real app uid 10323.
  Not this round's fix (sibling-owned files); the dock steps carried on.

### T1. A second display on this tablet (08:55-08:58 UTC, app force-stopped so nothing docked)

- `settings put global overlay_display_devices 1920x1080/160` -> `DisplayDeviceInfo{"Overlay #1":
  uniqueId="overlay:1", 1920 x 1080 ...}` and logical
  `DisplayInfo{"Overlay #1", displayId 2, displayGroupId 0, FLAG_PRESENTATION, FLAG_TRUSTED, real
  1920 x 1080 ... state ON, type OVERLAY, density 160}`. **Not `FLAG_PRIVATE`**, so `DockState`
  makes it the launch target. Full dump: scratch `t1-dumpsys-display.txt`.
- `pm list features`: `android.software.activities_on_secondary_displays` **present**, plus
  `android.software.freeform_window_management` and `picture_in_picture`.
- SurfaceFlinger: `Display 11529215049803859011 (Virtual display): displayName="Overlay #1"` next to
  `Display 4630947192003572371 (HWC display 0)`. `screencap -p -d <that id>` returns a 1920x1080
  PNG of the simulated display; the built-in id returns the 3200x2136 tablet screen. (The overlay's
  SurfaceFlinger id is re-read on every add.)
- `am start --display 2 -n com.android.settings/.Settings` -> `Display #2 ... Task{#4452 ...
  A=1000:com.android.settings ... visible=true mode=fullscreen}`. Screens
  (`shots/t1-settings-d2.png`, `shots/t1-settings-tablet.png`): display 2 shows Settings full screen
  (Wi-Fi page, 1920x1080); the tablet shows its home screen with the small "Overlay #1:
  1920x1080, 160 dpi" window in the top-left corner mirroring display 2. Sent back with
  `am force-stop com.android.settings`, display removed again.
- **Combination that lets an app run on the second display: none needed.** HyperOS left as found:
  `force_desktop_mode_on_external_displays=0`, `enable_freeform_support=0` (not changed);
  `force_resizable_activities=1` was already on before the round (not changed either).

### T2. Dock (build test2, 08:58-09:01 UTC)

Before (`snap.sh t2-before`, fresh cold start: handover +10.3 s, desktop PASS +9.7 s, then one
`foot` via `hc.sh '/dispatch hl.dsp.exec_cmd("foot")'`): app/X server pid 6096, proot 6222 (root
broker) and 6243 (session), cage 6514, Hyprland 6516, quickshell 6579, **foot 7306**; X activity
`ActivityRecord{174012199 ... t4454}` on `Display #0`; xroot 3200x1971, cage 3200x1970, monitor
3200x1970 scale 2, `clients 1`, `ui=mobile`, scan 42 blocks / 5 omamobile, probe PASS.

`dock.py on` (t0 = device clock at the `settings put`, 08:59:08.911):
```
+0.47s logcat Phoshdroid: dock: docked display=3 1920x1080@160 kbd=0 mouse=1 (change)
+0.47s logcat Phoshdroid: dock: ui mobile written (docked)
+0.47s logcat Phoshdroid: dock: extra-key bar hidden
+0.50s logcat Phoshdroid: dock: session asked onto display 3
~1s    watch  ui mode mobile -> desktop, switching in place
~4s    watch  ui switch: omdroid-ui rc=0; plugin-index rc=0; omarchy-restart-shell rc=0; layers fit again 0.1 s after the restart; hyprctl reload skipped: monitor and X root differ, the size logic owns it
RESULT t2-dock: ui switch logged at +3.9 s (host), desktop ready (switch + probe PASS at 1920x1080) at +NEVER s
```
(The simulated display came up as id 3: Android gives every re-added overlay a new id.)

After (`snap.sh t2-after`, 09:00:35):
- **Where the X activity is: moved, not re-launched.** `Display #3 ... topResumedActivity=
  ActivityRecord{174012199 u0 com.phoshdroid.app/com.termux.x11.MainActivity t4454}` - the same
  ActivityRecord and task as before, the same app pid 6096; `Display #0` is back on the HyperOS
  launcher. No `launch:` line: the launcher was not involved.
- Session untouched: pids 6096 / 6222 / 6243 / cage 6514 / Hyprland 6516 unchanged, **foot 7306
  still there** (`clients 1`, `class=foot ws=1`); only quickshell is new (6579 -> 8025, the switch's
  shell restart). No `FATAL`/`AndroidRuntime`.
- Guest: `ui=desktop`, scan file 37 blocks / **0 omamobile**, layers `omarchy-background`
  + `omarchy-bar` (bar 26 px logical, the stock desktop bar), no omamobile layer.
- **FAIL 1 - X root 1920x915, not 1920x1080.** cage window 1920x914. 1080 - 915 = 165 = the
  tablet's extra-key-bar gap (`XLORIE geometry: 3200x1971 (window 3200x2136, bottom gap 165)`).
  The view's margins are applied once in `MainActivity.onCreate` from the launch extras; the move
  keeps the activity (no recreate, `configChanges` covers it) and the dock monitor's re-launch with
  `phoshdroid_bottom_padding_px=0` reaches `onNewIntent`, which does not apply them. The bar itself
  is hidden (`dock: extra-key bar hidden`), so the 165 px are a black band.
- **FAIL 2 - Hyprland monitor 3200x1970 scale 2**, not the cage size: `probe: VERDICT: FAIL Hyprland
  monitor 3200x1970 != cage window 1920x914`. Hyprland's own log (`hyprctl rollinglog`):
  `Output WAYLAND-1: configure toplevel with 1920x914` -> `Swapchain: Reconfigured ... 1920, 914`
  -> `Swapchain: Reconfigured ... 3200, 1970`. Hyprland did follow cage, then a config reload put
  the start-time mode back: `monitors.lua` builds the mode from `OMARCHY_OUTPUT_WIDTH/HEIGHT`, which
  are fixed at session start, and Hyprland auto-reloads its config when a config file changes
  (`misc:disable_autoreload` = false) - `omdroid-ui.sh` edits `looknfeel.lua` during the switch
  (mtime 08:59). The watcher's own `hyprctl reload` was skipped, but its premise (a reload
  re-applies the CURRENT mode when monitor = root) is wrong in any case: it re-applies the
  START-TIME mode. After `ready` the watcher has no remedy for monitor != X root.
- **FAIL 3 - log line:** `dock: ui mobile written (docked)` while the file now says `desktop`
  (contract §8 promises `dock: ui desktop written (docked)`).
- Scale: the session keeps its start-time scale 2 on a 160 dpi display (a cold start while docked
  would resolve scale 1 through `UiScale`); with FAIL 2 fixed the docked desktop would be 960x540
  logical.
- Screens: `shots/t2-dock-d2.png` (display 3, SurfaceFlinger id 11529215047708466855): the stock
  desktop bar (workspaces 1-5, `Thursday 09:00`) and the foot terminal, cropped - only the top-left
  1920x914 of a 3200x1970 output is visible (the terminal runs off the right edge), black band
  across the bottom 165 rows. `shots/t2-dock-tablet.png`: the tablet is on the HyperOS home screen,
  with the small "Overlay #1" window top-left showing the same cropped desktop.
- Time from `settings put` to the switch: **3.9 s** (ui switch logged); to a desktop at the
  display's size: never (FAIL 1 + 2).

### T3. Undock (build test2, 09:03 UTC, from the T2 state)

`dock.py off` (t0 09:03:38.146):
```
+0.48s logcat Phoshdroid: dock: undocked (change)
+0.48s logcat Phoshdroid: dock: ui desktop written (undocked)
+0.48s logcat Phoshdroid: dock: extra-key bar shown
+0.48s logcat Phoshdroid: dock: monitor gone, the session follows to the default display
~0s    watch  ui mode desktop -> mobile, switching in place
~12s   watch  ui switch: omdroid-ui rc=0; plugin-index rc=0; omarchy-restart-shell rc=0; layers fit again 0.1 s after the restart; hyprctl reload rc=0
RESULT t3-undock: ui switch logged at +12.9 s (host), desktop ready (switch + probe PASS at 3200x1970) at +13.1 s
```
- X activity: back on `Display #0` as the top resumed activity, the same
  `ActivityRecord{174012199 ... t4454}` - Android migrated it; nothing re-launched it.
- xroot 3200x1971, cage 3200x1970, monitor 3200x1970 scale 2, **probe PASS** - the undocked size
  equals the start-time mode, so the config reload that broke T2 is harmless here.
- Mobile UI back: `ui=mobile`, scan 42 / 5 omamobile, layers `omamobile-home-strip`,
  `omamobile-launcher`, `omarchy-bar` 44 px, `omamobile-back` x2. `shots/t3-undock-tablet.png`:
  the mobile bar (`09:03`), the foot terminal maximised, the home pill and the two-row extra-key bar
  (ESC / - HOME ... PGDN) at the bottom, no misplaced band.
- Session untouched: 6096 / 6222 / 6243 / cage 6514 / Hyprland 6516, **foot 7306** still the one
  client; quickshell new again (8025 -> 14325).
- The log line names the previous mode again (`ui desktop written (undocked)` for a `mobile`
  write): T2's FAIL 3.
- The undock switch took 12 s against 3 s for the dock (both measured from the watcher's own
  lines); the mobile direction runs the longer `omdroid-ui.sh` path. T5 repeats it.

### T4. Pin (build test2, 09:04-09:06 UTC)

`t4.sh` (scratch): pin written inside the session with `sx.sh 'echo desktop > ~/.config/omdroid/ui-pin'`.
- Pinned `desktop`, undocked, 6 s later: `ui=mobile pin=desktop`, scan 5 omamobile, mobile layers,
  no watcher line. **FAIL: undocked does not become (or stay) `desktop`.** `omdroid-ui.sh` and the
  watcher read only `ui`, and the host never writes `ui` while pinned (UiMode.write returns null),
  so a desktop pin set while the file says `mobile` changes nothing at all - the contract's own
  example (`echo desktop > ui-pin  # keep the stock desktop UI, even on the phone`) does not work.
- Dock while pinned: `dock: docked display=4 1920x1080@160 kbd=0 mouse=1 (change)`,
  **`dock: ui desktop kept (pinned)`** (host wrote nothing: PASS), `dock: session asked onto display
  4`. The guest stayed `mobile` (`ui=mobile`, 5 omamobile) - the log line's `desktop` is the pin,
  not what the guest shows.
- Undock while pinned: `dock: undocked (change)`, `dock: ui desktop kept (pinned)`, `dock: monitor
  gone ...`; `ui` still `mobile`.
- **Side finding that settles T2's FAIL 2:** with no UI switch (pinned), Hyprland followed cage on
  the monitor - watcher `monitor 1920x914 scale 2, logical 960x457, X root 1920x915`, one shell
  restart for the layers (`act: layers fit again 6.8 s after the restart`), probe PASS at
  1920x914. So the start-time mode in T2 came from the switch's config reload, not from the move;
  and the 165 px gap (X root 1920x915) is there with or without a switch (T2's FAIL 1).
- `echo auto > ui-pin`: `ui=mobile pin=auto`, nothing to switch undocked (correct), mobile PASS.

### T7. Root causes and fixes

| # | Failure (step) | Root cause | Fix | Commit |
| --- | --- | --- | --- | --- |
| F1 | X root 1920x915 on a 1920x1080 display (T2) | `MainActivity.onCreate` applied the launcher's 165 px bottom gap once; a display move keeps the activity, and the dock monitor's re-launch extras (0/0) land in `onNewIntent`, which did nothing | termux-x11 `MainActivity.applyPhoshdroidPadding()`: the launcher's gaps apply only on the built-in display, 0 elsewhere; re-applied on configuration change (a move), focus change and new intent; logs `x-view margins top=.. bottom=.. (display N)`. A docked launch passes `phoshdroid_builtin_bottom_padding_px` (launcher `builtinBottomGap`) for the way back | termux-x11 `57790ca`, pointer + launcher `9ad4c2b` |
| F2 | Hyprland monitor 3200x1970 on a 1920x914 cage after the switch (T2) | `monitors.lua` builds the mode from the session-start `OMARCHY_OUTPUT_*`; Hyprland auto-reloads when `omdroid-ui.sh` edits `looknfeel.lua`, and every full reload puts that start-time mode back. Proven live: `hyprctl eval 'hl.monitor({ output = "", mode = "1920x914@120.000", position = "auto", scale = 2, transform = 0 })'` moved the monitor 3200x1970 -> 1920x914 at once | `omarchy-watch.py`: `fit_monitor()` (that `hl.monitor` rule at the even-rounded X root, current scale and refresh) right after the switch's scripts and, after `ready`, whenever monitor != X root for 1.5 s (3 tries per size); the switch's own reload is `hyprctl reload config-only` | `60fe8ef` |
| F3 | `dock: ui mobile written (docked)` / `ui desktop written (undocked)` (T2, T3) | `UiModeFile.apply` built `effective` from the file content read BEFORE the write | pin, then the mode just written, then the old file; 2 new tests | `3ed2f47` |
| F4 | `ui-pin` = `desktop` left the UI `mobile` (T4) | the guest read only `ui`; the host (correctly, per contract) never writes `ui` while pinned, so nothing ever applied the pin | `omdroid-ui.sh` and the watcher's `ui_mode()` use `ui-pin` while it names a mode, else `ui`; 8/8 host-side cases of `ui_mode()` checked against temp files | `60fe8ef` |
| F5 | (found reading the code for T5) a UI switch refused by the restart rate limit was dropped, leaving the old shell on screen; a rate-limited layer pass counted as one of the 3 attempts | `switch_ui` returned without a restart and `last_ui` moved on | a refused restart is queued (`PENDING_RESTART`) and run as soon as the limit allows; a rate-limited layer pass is not an attempt | `60fe8ef` |

One commit carries F2, F4 and F5 because all three live in `omarchy-watch.py` (F4 also in
`omdroid-ui.sh`) and were written and gated together.

Gate on `60fe8ef` (GRADLE_USER_HOME in scratch, the project's 4 GB heap):
`./gradlew :app:compileDebugKotlin :app:test :app:lintDebug --console=plain` -> **BUILD SUCCESSFUL in
57s**; `unit-count.py` -> **`unit tests 100 failed 0`** (98 + 2); lint **0 errors**, 32 warnings.
`bash -n omdroid-ui.sh` and an AST parse of the watcher clean. `assembleDebug` -> BUILD SUCCESSFUL
in 1m 7s (no OOM at 4 GB): `omdroid-dock-fix1.apk`, 1,715,760,502 B, sha256
`3b4166ab6106ac08cd4c35d42fa9270c6aadf546ef1d6edf37bd1d46220cf0c2`, tree `60fe8ef` + Phil's
uncommitted `gradle.properties` heap line; its `assets/guest-overlay` watcher and `omdroid-ui.sh`
equal HEAD (`b8acadac…`, `ab6ae227…`).

### Device re-proof on fix1 (09:15-09:24 UTC)

Install: `pm install: Success`, base.apk sha256 `3b4166ab…20cf0c2`; the guest copies of
`omarchy-watch.py` and `omdroid-ui.sh` equal HEAD after the cold start (`b8acadac…`, `ab6ae227…`).

**Cold start while docked (unplanned: my F2 probe had left the simulated display on).**
`dock: docked display=5 1920x1080@160`, `launch: ui desktop unchanged`, `launch: handover done
display=5 on-target=true`, handover +5.9 s, desktop PASS +6.2 s: X root 1920x1080, monitor
1920x1080 **scale 1** (UiScale from the display's 160 dpi), desktop UI. The `T2b` row of `phase2.log`
therefore measured nothing (already docked); T2c below is the brief's flow.

**T3b, undock of that docked-start session.** `x-view margins top=0 bottom=165 (built-in display)`
(the docked launch's `phoshdroid_builtin_bottom_padding_px` at work), `dock: ui mobile written
(undocked)` (F3 fixed), `monitor fit 3200x1970 rc=0` after the switch's reload had put the
session's start-time 1920x1080 back (F2 fixed in reverse), mobile UI, probe PASS at +16.6 s - but
at **scale 1**: logical 3200x1970, a 44 px bar on a 440 dpi screen (F6).

**T4b, pin.** `pin=desktop` undocked: the watcher switched to desktop by itself (`ui switch` 09:17:50,
scan 37 blocks / 0 omamobile) while `ui` still said `mobile` (F4 fixed). Dock and undock pinned:
`dock: ui desktop kept (pinned)` both times, `ui` untouched, monitor fitted (`monitor 3200x1970 !=
X root 1920x1080 (even-rounded): monitor fit 1920x1080 rc=0`), layers re-fitted, probe PASS at
1920x1080 and 3200x1970. `pin=auto`: back to mobile (`ui switch` 09:19:08), PASS.

**T5, five cycles** (`dock.py` = `settings put` to switch logged + probe PASS at the display's
size; in the docked-start session, scale 1):

| Cycle | Dock: switch / ready | X activity | Undock: switch / ready | X activity |
| --- | --- | --- | --- | --- |
| 1 | 3.8 / 4.1 s | display #7 | 0.1 / 17.4 s | #0 |
| 2 | 3.9 / 4.2 s | #8 | 0.1 / 15.4 s | #0 |
| 3 | 4.7 / 5.0 s | #9 | 15.5 / 15.7 s | #0 |
| 4 | 4.8 / 5.1 s | #10 | 9.5 / 11.9 s | #0 |
| 5 | 2.5 / 2.8 s | #11 | 11.1 / 13.6 s | #0 |

After the five: foot **24331** (same pid as before T3b), cage 23840 / Hyprland 23841 unchanged,
`ui=mobile`, 5 omamobile, probe PASS. Crash lines in logcat (`FATAL EXCEPTION|Fatal signal|F
DEBUG|ANR in com.phoshdroid`): **0**. Each undock logged one `monitor fit 3200x1970` (the reload
put the start-time mode back) and no `giving up`. Rate limit: cycle 5's dock hit it
(`09:20:33 ui switch: ... shell restart rate limited (6 per 60 s, 2 s apart), queued`); the mobile
shell stayed up for ~1 s until the next undock's own restart superseded the queue, so the final UI
was right. The queued restart itself running was not observed on the device (F5's path).

**T6, input while docked** (display #12; focus `mCurrentFocus=Window{... com.phoshdroid.app/
com.termux.x11.MainActivity}`; uhid keyboard from `mkhid.py`):
- SUPER+Return: LorieNative `Sending key: 133 (125 0 1)`, `36 (28 0 1)` -> `clients 1: foot pid=24331`
  -> `clients 2: ..., foot pid=7882 mon=0` (the docked monitor is Hyprland's only monitor).
- Typing `echo dockok > /tmp/typed-dock.txt` + Enter: 70 key events, the file reads `dockok`.
- SUPER+W: `133` + `25 (17 0 1)` -> `clients 1: foot pid=24331`.
- Path: `MiuiInputKey: application accessibility handled this event,info=com.phoshdroid.app/
  com.termux.x11.utils.KeyInterceptor` - the accessibility interceptor, because this tablet is
  SDK 36.0 (`KeyboardCapture: keyboard capture API absent (needs Android 16.1+)`).
- Touch on the simulated display is not meaningful (its overlay is drawn on the tablet screen and
  takes no input of its own): not tested.

### T2c / T3c in the brief's flow (fix1, 09:23 UTC)

Undocked cold start: handover +11.1 s, desktop PASS +10.5 s, scale 2, mobile; one `foot` (10935).
- Dock: `dock: docked display=13 1920x1080@160 kbd=0 mouse=1 (change)`, **`dock: ui desktop
  written (docked)`**, `dock: session asked onto display 13`, **`x-view margins top=0 bottom=0
  (display 13)`**; watcher `ui switch: omdroid-ui rc=0; plugin-index rc=0; monitor fit 1920x1080
  rc=0; omarchy-restart-shell rc=0; ...; hyprctl reload config-only rc=0`, then once more `monitor
  3200x1970 != X root 1920x1080 (even-rounded): monitor fit 1920x1080 rc=0, attempt 1/3` (the
  autoreload landed after the first fit). **Switch +5.4 s, ready +5.9 s.** X activity: `Display #13
  ... ActivityRecord{56085350 ... t4459}` - the same record as on display 0: moved. xroot
  **1920x1080** = cage 1920x1080 = monitor 1920x1080 scale 2 (logical 960x540), bar 26, 0 omamobile,
  foot 10935, cage 10286 / Hyprland 10289 unchanged, probe PASS.
  `shots/t2c-dock-d2.png`: the stock desktop fills the whole 1920x1080 display - bar with workspaces
  1-5, `Thursday 09:23` centred and the tray at the right edge, the terminal framed inside the
  screen, no black band, nothing cropped (at scale 2 everything is large).
- Undock: `x-view margins top=0 bottom=165 (built-in display)`, `dock: undocked (change)`, **`dock:
  ui mobile written (undocked)`**; a transient `monitor fit 3200x914` (the X root was 3200x915 for
  a moment while the window re-laid out on display 0), then the switch, whose
  `omarchy-restart-shell` returned **rc=1** (`layers still do not fit 8 s after the restart`); the
  layer remedy restarted the shell 2 s later and `layers fit again 6.0 s after the restart`.
  **Ready +29.4 s.** X activity back on display #0 (same record), xroot 3200x1971, monitor
  3200x1970 scale 2, mobile layers, foot 10935, probe PASS. `shots/t3c-undock-tablet.png`: the
  mobile bar (`09:24`), the terminal maximised, the home pill and the two-row extra-key bar at the
  bottom, filling the screen.
- Crash lines: 0.

### F6 (open): a running session keeps the UI scale it started with

Measured: started undocked (scale 2) and docked, the 1920x1080 display gets a 960x540 desktop;
started docked (scale 1) and undocked, the tablet runs the mobile UI at scale 1 (logical
3200x1970). Root cause: the scale is decided once - the launcher's `UiScale` result reaches the
guest as `OMARCHY_SCALE` at session start, `monitors.lua` uses it - and nothing carries a new
scale on a live display change. Proposed fix (not made this round: call budget): the dock monitor
resolves `UiScale` for the new display and writes it beside the mode file; the watcher reads it and
passes it as `scale` to the same runtime `hl.monitor` rule (which already takes a scale), and its
layer remedy restarts the shell. That is a contract §8 change (a new host-owned file).

### T8. Hand-off and cleanup (09:24 UTC)

- `settings delete global overlay_display_devices` -> reads `null` (as recorded), 0 overlay
  displays; `stay_on_while_plugged_in` -> `0`; `force_desktop_mode_on_external_displays=0`,
  `enable_freeform_support=0` (never changed), `force_resizable_activities=1` (as found).
  `screen.sh` was not used.
- Session left running undocked: X activity on display #0, `ui=mobile pin=auto`, 5 omamobile,
  xroot 3200x1971, monitor 3200x1970 scale 2, **`VERDICT: PASS`**.
- Final APK: `<scratch>/omarchy/r7/device/omdroid-dock-final.apk` (= fix1),
  1,715,760,502 B, sha256 `3b4166ab6106ac08cd4c35d42fa9270c6aadf546ef1d6edf37bd1d46220cf0c2`,
  built from `60fe8ef` (only Phil's uncommitted `gradle.properties` heap line beside it).
- Docs: launch contract §8 (the pin in the guest, the monitor fit and `reload config-only`, the
  view margins, the new log lines) and README "Docking" (proven on the tablet, the scale limit).

## Manual test for Phil (Galaxy Z Fold8 + real monitor)

1. Install `omdroid-dock-final.apk` (sha256 `3b4166ab…20cf0c2`) over 0.0.15 - an update, the guest
   stays. Open Omdroid unplugged: the mobile desktop (bar, home pill, extra-key bar).
2. Open a terminal and run `seq 300; echo before-dock`. Leave it open.
3. Plug the monitor (USB-C to HDMI/DP) with DeX set to **Extend** (Settings > Connected devices >
   Samsung DeX > Connected display). Within ~6 s the desktop should be on the monitor, full screen,
   no black band at the bottom: thin top bar with workspaces 1-5 and the clock, no home pill, no
   extra-key bar; the same terminal. The phone shows Android. If the desktop stays on the phone,
   open Omdroid from the monitor's taskbar instead and note it.
4. Expect a large UI on a 1080p monitor (the session keeps the phone's scale 2, F6). Note the
   monitor's size and the `dock: docked display=N WxH@dpi` line.
5. Keyboard: SUPER+Return opens a terminal on the monitor; type `echo kbd-ok`; SUPER+W closes it.
   SUPER alone must not open the DeX start menu or the app drawer.
6. Mouse: move over the desktop; left click on workspace 2 in the bar (switches); right click on
   the terminal; wheel in the terminal scrolls back through the `seq` output.
7. Unplug with the terminal open. Within ~30 s Omdroid shows the mobile UI on the phone (bar, home
   pill, extra-key bar, no black band); the terminal still shows `before-dock`.
8. Plug again: back on the monitor, same terminal.
9. With DeX set to **Screen mirroring** (if One UI offers it): the phone is mirrored and Omdroid
   stays in mobile UI (`dock: undocked` - a mirror is not a second display).
10. Pin: in a terminal `echo desktop > ~/.config/omdroid/ui-pin` - the phone switches to the stock
    desktop UI within a few seconds; unplug/plug keeps it; `echo auto > ~/.config/omdroid/ui-pin`
    follows the dock again.
11. Started docked: force-stop Omdroid, plug the monitor, open Omdroid (from the monitor or the
    phone): the desktop comes up on the monitor at its own scale; unplug - expect the mobile UI at
    scale 1 (tiny, F6) and no black band; reopen Omdroid after a force-stop to get scale 2 back.
12. Logs to send: `adb logcat -s Phoshdroid:* KeyboardCapture:* | grep -E 'dock:|x-view|handover|keyboard capture'`
    (expect `dock: docked display=N ...`, `dock: ui desktop written (docked)`, `dock: session asked
    onto display N`, `x-view margins top=0 bottom=0 (display N)`; on unplug `dock: undocked`,
    `dock: ui mobile written (undocked)`, `x-view margins ... (built-in display)`; on Android 16.1+
    `keyboard capture on`), and from a terminal `cat /tmp/omarchy-watch.log` (`ui mode mobile ->
    desktop`, `ui switch: ...`, `monitor fit ...`).

## Risks still open

- **F6, scale:** a live dock keeps the start-time scale (phone 2 -> a 1080p monitor gets 960x540
  logical); a session started docked keeps scale 1 on the phone after unplug.
- The monitor fit reacts to the X root as soon as it differs, so a transient size during a move
  can be fitted first (`monitor fit 3200x914` in T3c) and one shell restart can fail (`rc=1`); the
  watcher recovered both times (layer remedy, Hyprland following cage), at the cost of an undock
  taking up to ~30 s.
- The undock switch is slow (12-29 s against 3-6 s for a dock): the mobile direction's
  `omdroid-ui.sh` plus plugin index dominate.
- A queued, rate-limited shell restart (F5) was seen queuing but not running on the device.
- Samsung's desktop-mode display may be `FLAG_PRIVATE` (then no move: `dock: ... private`, open
  Omdroid on the monitor), and `keep_process_alive=true` may not be honoured by Android 16 DeX.
- If the X activity is not alive when a monitor appears (session in the background), the dock
  monitor's re-launch carries no built-in gap, so after unplug the extra-key bar can overlap the
  desktop's bottom until the next launch.
- `sudo` refuses every client on the device (T0, `refused peer uid 10323, accepts [0]`) - the
  sibling round's fix did not take under the device proot.

## Not verified

Only the phone and a real monitor can show: Samsung DeX (Extend and mirror), whether One UI moves
the running window (it MOVED here, on HyperOS's simulated display) or needs it opened on the
monitor, `keep_process_alive` across an unplug, a real mouse (left/right click, wheel - injection
cannot carry buttons), the monitor's density and DeX's density override, HDMI hot-plug timing,
Android 16.1's keyboard-capture API (this tablet is 36.0), a 4K or ultrawide monitor, and audio
over the monitor.
