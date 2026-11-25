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
| D2 delivery change + `touchMode = "3"`, gates, build, install | **PASS** | commits `27192a8` (build) + `73b7a0b` (feat); gate `compileDebugKotlin test lintDebug` BUILD SUCCESSFUL, `unit tests 63 failed 0`; `assembleDebug` 20 s, APK 1 715 699 122 B sha `56db6d52…8ba4`, carries `assets/guest-overlay/etc/phoshdroid/lib/libaquamarine.so.13` sha `8514d2a6…`; `install.sh` → `INSTALL: PASS` (installed sha = local); D1 swap undone first (`/opt` library back to `8a2a2cbe…`) |
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

### Pre-check between D1 and D2: direct touch on the D1 state, no rebuild

Before spending a build, the D1 session (new library in `/opt`, APK still `"2"`) was switched to
direct touch live with Termux:X11 own preference receiver, which is exported in this APK:
`am broadcast -a com.termux.x11.CHANGE_PREFERENCE -n com.phoshdroid.app/com.termux.x11.LoriePreferences\$Receiver --es touchMode 3`
→ `result=2, data="Done"`, `shared_prefs` `touchMode` = `3`, logcat shows
`MainActivity.onPreferencesChangedCallback`. A touch tap at 1600,44 then opened
`omamobile-quicksettings` (before the patch, round 4 measured 0/9 reactions in this mode).
The next launch rewrites the preference, so this lasted until the cold start of D3.

A position probe was written for the round: `docs/omarchy/tools/touchlog.c` (built in the
`omdroid-aquamarine-builder` container, 75 824 bytes). It maps one layer-shell surface anchored to
all four edges with exclusive zone -1 on the overlay layer, so its surface-local coordinates are
Hyprland logical coordinates, and prints every `wl_touch` and `wl_pointer` event. Its first run
(seat caps `touch=1`, configure 1600x985) is repeated on the D2 APK in D3.

### D2 delivery change, gates, build, install

Files (commit `27192a8`, `build(rootfs): ship aquamarine with wl_touch in the guest overlay`):

- `rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13`: the P3 library, a regular file,
  1 775 168 B, sha256 `8514d2a6…6191`, SONAME `libaquamarine.so.13`.
- `rootfs/overlay/etc/phoshdroid/lib/LICENSE`: aquamarine BSD-3-Clause (sha256 `52d07f34…`).
- `rootfs/overlay/etc/phoshdroid/lib/README.md`: sha256, source revision `a79fb21b`, both patches
  with their sha256, the `rootfs/build-aquamarine.sh` command and how the copy reaches the guest.
- `rootfs/overlay/etc/phoshdroid/start.sh`: `LD_LIBRARY_PATH=/etc/phoshdroid/lib:` first
  (`bash -n` clean, no apostrophe added).
- `app/build.gradle.kts`: `include("lib/**")` in `syncGuestOverlay`.
- `rootfs/package-omarchy-rootfs.sh`: `cp -a "$OVERLAY_DIR/etc/phoshdroid/lib" …` in the
  "Applying overlay" block (`bash -n` clean). Both lists now name `lib/`.

Commit `73b7a0b` (`feat(launcher): direct touch now that the guest has a touch device`):
`LauncherActivity.kt` `.putString("touchMode", "3")` with the comment rewritten (why "3", the
library it depends on, the round-4 history and `"2"` as the fallback).

```
./gradlew :app:compileDebugKotlin :app:test :app:lintDebug --console=plain   BUILD SUCCESSFUL in 56s
python3 docs/omarchy/tools/unit-count.py                                     unit tests 63 failed 0
rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug --console=plain
                                                                             BUILD SUCCESSFUL in 20s
app-debug.apk  1 715 699 122 bytes  sha256 56db6d5201c8b08aa00331284d922d65601715aa0ae9d0b48a5a5bfa15f98ba4
  (tree = 73b7a0b, clean; copy kept as scratch omdroid-r5-touch-73b7a0b.apk)
unzip -l: assets/guest-overlay/etc/phoshdroid/lib/{LICENSE,README.md,libaquamarine.so.13 1775168}
unzip -p …/libaquamarine.so.13 | sha256sum   8514d2a6…6191
D1 undone: <guest>/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0 -> sha 8a2a2cbe…135e
./install.sh  pm install from /data/local/tmp, 45 s push
              INSTALLED sha256=56db6d52…8ba4 lastUpdateTime=2026-11-25 01:04:59   INSTALL: PASS
```

### D3 real touch, on the D2 APK

**D3.1 device and library.** `./coldstart.sh 1 --tag d3`: handover +10.3 s, desktop PASS +9.8 s,
foreign activity none, `probe.sh` PASS. `shared_prefs` `touchMode` = `3` (written by the launcher).

```
logcat  launch: guest-overlay files=61 changed=4 129ms
        launch: guest-overlay updated etc/phoshdroid/lib/LICENSE
        launch: guest-overlay updated etc/phoshdroid/lib/README.md
        launch: guest-overlay updated etc/phoshdroid/lib/libaquamarine.so.13
        launch: guest-overlay updated etc/phoshdroid/start.sh
./hc.sh j/devices        mice [wl_pointer]  keyboards [wl_keyboard]  touch [wl_touch]
/proc/<Hyprland 7641>/maps   inode 1045150 .../installed-rootfs/omarchy/etc/phoshdroid/lib/libaquamarine.so.13
/proc/<Hyprland 7641>/environ LD_LIBRARY_PATH=/etc/phoshdroid/lib:/opt/omarchy-android/mesa/root/usr/lib:/opt/omarchy-android/aquamarine/lib
<guest>/etc/phoshdroid/lib   libaquamarine.so.13 inode 1045150, 1775168 B, sha256 8514d2a6…6191 (= repo)
                             LICENSE 52d07f34… (= repo), README.md 43e6aeda… (= repo), mode 0600 (owner = the app uid)
```

`GuestOverlay` wrote the 1.7 MB binary intact (same sha256 as the repo) and the loader picked it
from `/etc/phoshdroid/lib`; the image copy in `/opt` (`8a2a2cbe…`, restored after D1) is not mapped.

**D3.2 positions.** `touchlog` (full-output overlay layer, see the pre-check) running in the
session; one `input touchscreen tap` per point; the surface-local coordinates of `wl_touch.down`
are Hyprland logical coordinates. Expected = screen / 2 (the X root maps 1:1 onto the screen,
cage is 3200x1970 at 0,0, Hyprland scale 2). Log: scratch `d3-positions.log`.

| tap (screen px) | expected (logical) | `wl_touch.down` | error (logical) | error (screen px) |
|---|---|---|---|---|
| 4,4 (top left) | 2.0,2.0 | 1.50,1.50 | −0.5,−0.5 | −1,−1 |
| 3195,4 (top right) | 1597.5,2.0 | 1597.00,1.50 | −0.5,−0.5 | −1,−1 |
| 4,1965 (bottom left) | 2.0,982.5 | 1.50,982.00 | −0.5,−0.5 | −1,−1 |
| 3195,1965 (bottom right) | 1597.5,982.5 | 1597.00,982.00 | −0.5,−0.5 | −1,−1 |
| 1600,985 (centre) | 800.0,492.5 | 799.50,492.00 | −0.5,−0.5 | −1,−1 |
| 3195,40 (bar, far right) | 1597.5,20.0 | 1597.00,19.50 | −0.5,−0.5 | −1,−1 |
| 800,500 | 400.0,250.0 | 399.50,249.50 | −0.5,−0.5 | −1,−1 |
| 2400,1500 | 1200.0,750.0 | 1199.50,749.50 | −0.5,−0.5 | −1,−1 |

8/8 taps arrive as `wl_touch` (seat caps `touch=1`, no `wl_pointer.button` at all). The error is
the same −1 screen px at both ends of both axes, so there is **no scale and no mirror**: the
patch normalises against the right size. The constant 1 px is upstream of the patch, in the X11
hop: Xlorie queues a touch as the valuator `x * 0xFFFF / width`
(`termux-x11/app/src/main/cpp/lorie/cmdentrypoint.c:261-262`), which the X server spreads over
0..width−1, so an integer pixel x becomes x·(W−1)/W, just under x; wlroots' X11 backend then keeps
only the integer part (`send_touch_down_event(output, ev->event_x >> 16, …)`,
`backend/x11/input_device.c:245`, the same for motion at `:283`). Round 4 saw the same −1 on the
cursor in this mode before the patch existed (tap 3052,26 → cursor 1525,12). Verdict **PASS
within 1 screen px** (0.5 logical px, about 0.05 mm on this panel); a finger cannot resolve it.
Fix, for the Termux:X11 owner, not done here: scale against `width - 1` / `height - 1` in
`cmdentrypoint.c:261-262`, then the truncation lands on the tapped pixel.
