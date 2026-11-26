# R7 dock device round: docking on the tablet (M1-M3)

Brief: `docs/omarchy/brief-r7-dock-device.md` (with its AMENDMENT). Device: the Xiaomi tablet
(serial passed in the launcher prompt, exported as `TABLET_SERIAL`, never written here).
Scratch: `<scratch>/omarchy/r7/device/`.

## STATUS TABLE

| Step | What | Verdict | Number / log line |
| --- | --- | --- | --- |
| T0 | Baseline: install test2, cold start, probe, undocked mobile, dock lines, touch, key capture, `sudo id` | **PASS** (dock baseline) / **FAIL** (`sudo id`, not this round's fix) | install sha `a239a8c5…12fc407a0` PASS; cold start handover +7.6 s, desktop PASS +8.0 s; `dock: undocked`; `wl_touch`; KeyInterceptor bound; `sudo id` -> `omdroid-rootd: peer is not this app` |
| T1 | How a second display works on this tablet | **PASS** | `overlay_display_devices 1920x1080/160` -> display 2, `type OVERLAY`, `FLAG_PRESENTATION, FLAG_TRUSTED` (not PRIVATE), density 160; `activities_on_secondary_displays` present; `am start --display 2` Settings -> `Display #2` fullscreen; no other setting needed |
| T2 | Dock (M1 + M2) | **FAIL** (geometry) / PASS (move, UI switch, no restart) | X activity MOVED to display 3 (same ActivityRecord, same task); `ui switch` +3.9 s; foot pid 7306 kept; but X root **1920x915** (165 px key-bar gap kept), Hyprland monitor **3200x1970** (start-time mode re-applied), `dock: ui mobile written (docked)` names the wrong mode |
| T3 | Undock (M2) | **PASS** (one log FAIL, same as T2's FAIL 3) | X activity back on display 0 by itself (same ActivityRecord); xroot 3200x1971, monitor 3200x1970; mobile UI back; foot 7306 kept; desktop ready +13.1 s; log `dock: ui desktop written (undocked)` names the old mode |
| T4 | Pin | PENDING | |
| T5 | Repeat x5 | PENDING | |
| T6 | Input while docked | PENDING | |
| T7 | Fixes | PENDING | |
| T8 | Hand-off and cleanup | PENDING | |

## Settings changed on the tablet (restore list)

| Setting | Recorded value | Set to | Restore command | Restored / read back |
| --- | --- | --- | --- | --- |
| `global overlay_display_devices` | `null` | `1920x1080/160` (T1-T6) | `adb -s $TABLET_SERIAL shell settings delete global overlay_display_devices` (it read `null`) | |
| `global stay_on_while_plugged_in` | `0` | `2` | `adb -s $TABLET_SERIAL shell settings put global stay_on_while_plugged_in 0` | |

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
