# R7 dock device round: docking on the tablet (M1-M3)

Brief: `docs/omarchy/brief-r7-dock-device.md` (with its AMENDMENT). Device: the Xiaomi tablet
(serial passed in the launcher prompt, exported as `TABLET_SERIAL`, never written here).
Scratch: `<scratch>/omarchy/r7/device/`.

## STATUS TABLE

| Step | What | Verdict | Number / log line |
| --- | --- | --- | --- |
| T0 | Baseline: install test2, cold start, probe, undocked mobile, dock lines, touch, key capture, `sudo id` | **PASS** (dock baseline) / **FAIL** (`sudo id`, not this round's fix) | install sha `a239a8c5…12fc407a0` PASS; cold start handover +7.6 s, desktop PASS +8.0 s; `dock: undocked`; `wl_touch`; KeyInterceptor bound; `sudo id` -> `omdroid-rootd: peer is not this app` |
| T1 | How a second display works on this tablet | PENDING | |
| T2 | Dock (M1 + M2) | PENDING | |
| T3 | Undock (M2) | PENDING | |
| T4 | Pin | PENDING | |
| T5 | Repeat x5 | PENDING | |
| T6 | Input while docked | PENDING | |
| T7 | Fixes | PENDING | |
| T8 | Hand-off and cleanup | PENDING | |

## Settings changed on the tablet (restore list)

| Setting | Recorded value | Set to | Restore command | Restored / read back |
| --- | --- | --- | --- | --- |
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
