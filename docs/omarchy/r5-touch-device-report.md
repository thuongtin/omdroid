# R5-TOUCH-DEVICE report: real touch on the tablet (aquamarine `wl_touch` + direct touch)

Brief: `docs/omarchy/brief-r5-touch-device.md`. Worker: Hermes child agent `c8da29de` (parent
`f8d5582c`), run in-session, no delegation. Repo `<repo>`,
branch `main`, base commit `9e1bb3f`. Device: the Xiaomi Pad (serial kept out of the repo).
Scratch: `<scratch>/omarchy/r5/touch-device/`.

## STATUS TABLE

| Step | Status | Decisive fact |
|---|---|---|
| D0 device, stay-awake, `probe.sh -q` on the installed build | **PASS** | keyguard not showing, awake; `stay_on_while_plugged_in` was `0`, set `2` (read back `2`); installed base.apk `0a229e1a…1f80` (0.0.14-alpha + round-5 mobile UI); `probe.sh` `VERDICT: PASS` (root 3200x1971, monitor 1600x985 @2); baseline `j/devices` `touch: []`; Hyprland maps the image library sha `8a2a2cbe…135e` |
| D1 new library loaded on the device (no APK change), `wl_touch` listed | PENDING | |
| D2 delivery change + `touchMode = "3"`, gates, build, install | PENDING | |
| D3 real touch proven (devices, positions, bar 9/9, focus, gestures, long press, two fingers) | PENDING | |
| D4 regressions (keyboard, size change, desktop mode) | PENDING | |
| D5 decision: which `touchMode` ships | PENDING | |
| D6 clean up | PENDING | |
| D7 report | PENDING | |

## Log

### D0 device

```
isKeyguardShowing=false  mWakefulness=Awake  top com.phoshdroid.app/com.termux.x11.MainActivity
settings get global stay_on_while_plugged_in   -> 0   (recorded; restored at the end)
svc power stayon usb; settings get ...          -> 2
installed base.apk sha256 0a229e1aaf35f7f093a79f70791bc450e222d3523490950067925fd7c5661f80
  (versionName 0.0.14-alpha, lastUpdateTime 2026-11-25 00:45:09, the round-5 mobile UI build)
./probe.sh   xroot 3200x1971, cage-window 3200x1970 @0,0, monitor 3200x1970@120 scale 2 -> 1600x985,
             layers omarchy-background, omamobile-dock, omamobile-launcher, omarchy-bar 1600x44,
             2x omamobile-back; clients 0; VERDICT: PASS
./hc.sh j/devices   mice [wl_pointer]  keyboards [wl_keyboard]  touch []  tablets []  switches []
/proc/<Hyprland 25013>/maps -> .../opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0
  device file sha256 8a2a2cbe95a56b16ec986acf8ba4e8d6b5c737f607ff3482c62c759983ee135e, 1 661 600 bytes
  (= touch-patch/out/libaquamarine.orig.so.0.14.0, the image library)
```

`Hyprland` (17 316 744 bytes, pulled from the guest) has no `RPATH`/`RUNPATH` and one
`NEEDED libaquamarine.so.13`, so the `LD_LIBRARY_PATH` order alone decides which copy loads.
`ProotCommandBuilder.kt:122` also sets an `LD_LIBRARY_PATH`, but `start.sh:37` replaces it: the
live Hyprland's environment reads `/opt/omarchy-android/mesa/root/usr/lib:/opt/omarchy-android/aquamarine/lib`.
