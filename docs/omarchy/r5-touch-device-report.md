# R5-TOUCH-DEVICE report: real touch on the tablet (aquamarine `wl_touch` + direct touch)

Brief: `docs/omarchy/brief-r5-touch-device.md`. Worker: Hermes child agent `c8da29de` (parent
`f8d5582c`), run in-session, no delegation. Repo `<repo>`,
branch `main`, base commit `9e1bb3f`. Device: the Xiaomi Pad (serial kept out of the repo).
Scratch: `<scratch>/omarchy/r5/touch-device/`.

## STATUS TABLE

| Step | Status | Decisive fact |
|---|---|---|
| D0 device, stay-awake, `probe.sh -q` on the installed build | **PASS** | keyguard not showing, awake; `stay_on_while_plugged_in` was `0`, set `2` (read back `2`); installed base.apk `0a229e1a…1f80` (0.0.14-alpha + round-5 mobile UI); `probe.sh` `VERDICT: PASS` (root 3200x1971, monitor 1600x985 @2); baseline `j/devices` `touch: []`; Hyprland maps the image library sha `8a2a2cbe…135e` |
| D1 new library loaded on the device (no APK change), `wl_touch` listed | **PASS** | image library renamed over (backup `files/r5-touch-backup/…orig`, sha `8a2a2cbe`); cold start handover +9.7 s, desktop PASS +9.2 s; `j/devices` **`touch: ["wl_touch"]`** (was `[]`); Hyprland maps inode 98028 = the new 1 775 168-byte file (sha `8514d2a6…`); `probe.sh -q` PASS; bar tap (mode 2 click) at 1600,44 opens `omamobile-quicksettings`, Escape closes it |
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

### D1 the new library on the device, no APK change

The quickest change a cold start does not undo: `GuestOverlay` only writes `etc/phoshdroid` files,
so the image library itself was swapped (a rename, so the running Hyprland kept its old inode):

```
adb push libaquamarine.so.0.14.0 (8514d2a6…, 1 775 168 B) /data/local/tmp/aq-r5-new.so
run-as: cp -p <guest>/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0 files/r5-touch-backup/libaquamarine.so.0.14.0.orig
        sha256 8a2a2cbe…135e (the image library)
        cp aq-r5-new.so <lib>/libaquamarine.so.0.14.0.r5new; chmod 700; mv … libaquamarine.so.0.14.0
        sha256 <lib>/libaquamarine.so.0.14.0 -> 8514d2a65f2e10bb75d74a97cd3bc97db52f06bc19ecd0a47395aa9fdae66191
./coldstart.sh 1 --tag d1   handover +9.7 s (auto), desktop PASS +9.2 s, foreign activity 0,
                            log: launch: ready marker 8939ms, handover done 8953ms
./hc.sh j/devices           mice [wl_pointer]  keyboards [wl_keyboard]  touch [wl_touch]  (0x7790ef2d00)
/proc/<Hyprland 29231>/maps libaquamarine.so.0.14.0 inode 98028
stat                        inode 98028, 1775168 bytes  (the backup is inode 220556, 1661600 bytes)
./probe.sh -q               VERDICT: PASS
input touchscreen tap 1600 44 (touchMode 2 = a click)
                            new layer omamobile-quicksettings 0,0 1600x985, cursor 800,22
                            (shots/d1-qs-open.png); keyevent 111 (Escape) closes it (0 quicksettings layers)
```

The patched library loads, Hyprland starts on it, and the touch device exists. Under simulated
touch the X server sends pointer events only, so nothing reaches `wl_touch` yet.
