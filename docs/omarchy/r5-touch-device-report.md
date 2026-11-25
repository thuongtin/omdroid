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
| D3 real touch proven (devices, positions, bar 9/9, focus, gestures, long press, two fingers) | **PASS** | `touch: [wl_touch]`, Hyprland maps `/etc/phoshdroid/lib/libaquamarine.so.13` (device sha = repo); positions 8/8 within **1 screen px** (constant −1 px from the X11 hop, no scale, no mirror); desktop bar **9/9** react to a touch tap (ws1 checked from ws 3); focus by tap moves focus and `r5typed` lands only in the tapped window; mobile gestures **7/7** with quick swipes (back x=20 and x=3, pill home, dock → switcher, card flick closes, card tap, QS pull-down); card long press opens its actions; foot scrolls on a drag; **2 simultaneous touch points** reach a client (uinput MT screen) |
| D4 regressions (keyboard, size change, desktop mode) | **PASS** | uhid SUPER+2: workspace 1 → **2**, SUPER+1 back, Android top unchanged; rotation to portrait: probe PASS (root 2136x3035 → 1068x1517), Hyprland pid 7641 unchanged, quickshell 7707 → 14466 (shell-only restart); `screen.sh reset`: probe PASS 3200x1971, density 352, auto-rotate on; desktop mode cold start PASS, stock bar, bar taps work by touch |
| D5 decision: which `touchMode` ships | **`"3"` ships** | every D3 row passed on the D2 APK; nothing to revert |
| D6 clean up | **PASS** | mode file removed (missing = mobile, as found), cold start PASS (mobile layers, clients 0); `stay_on_while_plugged_in` restored and read back **0**; containers `omdroid-aq-build`, `omdroid-aquamarine-builder` removed (no rebuild was needed), images kept; `probe.sh -q` PASS |
| D7 report | **DONE** | this file; final APK `56db6d5201c8b08aa00331284d922d65601715aa0ae9d0b48a5a5bfa15f98ba4` built from `73b7a0b` |

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
within 1 screen px** (0.5 logical px, under 0.1 mm on this panel); a finger cannot resolve it.
Fix, for the Termux:X11 owner, not done here: scale against `width - 1` / `height - 1` in
`cmdentrypoint.c:261-262`, then the truncation lands on the tapped pixel.

**D3.5 mobile gestures, quick swipes with no hold** (`input touchscreen swipe … <ms>`, i.e. one
DOWN, a stream of MOVEs, UP). Scripts and logs: scratch `d3-gestures-1.sh`/`-2.sh` and `.log`.
Two windows open on workspace 1 (`foot`, and `foot --app-id=backtest` running a byte logger
that writes every byte it receives to `/tmp/r5-backtest.log`).

| Gesture | Injected | Result | Verdict |
|---|---|---|---|
| back from x = 20 | swipe 20,1000 → 420,1000, 150 ms | logger receives `1b` (Escape), focus stays on `backtest`, Android top unchanged | **PASS** |
| back from x = 3 | swipe 3,1000 → 420,1000, 150 ms | second `1b`; Android back did not fire (top still the X11 activity) | **PASS** |
| pill swipe goes home | swipe 1600,1915 → 1600,1765, 100 ms (75 logical px up) | workspace 1 → **2** (empty), `omamobile-home-strip` → `omamobile-dock` | **PASS** |
| dock swipe-up opens the switcher | swipe 1600,1880 → 1600,1560, 120 ms | new layer **`omamobile-switcher` 1600x985**, two cards | **PASS** (0/10 under simulated touch in the mobile round) |
| card flick closes a window | swipe 1600,1000 → 1600,300, 120 ms on the centred card | `clients` **2 → 1**, one card left | **PASS** |
| card tap switches | tap 1600,1000 | workspace 2 → **1**, active `foot`, switcher closed | **PASS** |
| quick-settings pull-down | swipe 1600,30 → 1600,600, 150 ms | new layer **`omamobile-quicksettings`**; Escape closes it | **PASS** |

**D3.6 long press.** A still 1.2 s hold on a switcher card fires its QML long press: the actions
sheet opens (`Foot` / `Show with…` "No other app is open" / `Cancel`, `shots/d3-card-hold.png`).
A still 1.5 s hold on the home pill over an app does nothing: no layer, workspace and focus
unchanged. That is the pill as built since `a44b0a1` (`longPressThreshold: root.voice ? 0.45 : 3600`,
no voice plugin), so its long press is correctly inert.

**D3.6 drag inside a window.** In `foot` after `seq 1 300` (typed with `input text`), a one-finger
quick drag down (`swipe 1600,500 → 1600,1500`, 800 ms) scrolls the scrollback: the visible
lines go from 251-300 + prompt to **221-271** with foot's scroll indicator at the right edge
(`shots/d3-drag-before.png`, `d3-drag-after.png`). The same drag over `touchlog` is one
`wl_touch.down` at 799.5,249.5, **97** `motion` events, one `up` at 799.5,749.5: a continuous
stream, no hold needed. Moving a window by dragging it is not tested: Hyprland has no touch
binding for that (it needs a plugin such as hyprgrass), and the mobile layout tiles windows.

**D3.7 two fingers.** A synthetic multi-touch screen through Android's `uinput` command
(`adb shell uinput /data/local/tmp/r5-mt.json`: a type-B MT device, `INPUT_PROP_DIRECT`, axes
2136x3200 = the panel in its natural portrait orientation; generator inline in scratch
`d3-multi.sh`), with `touchlog` reading. The device maps raw (x, y) to screen (y, 2135 − x).

| Injected | `touchlog` sequence | Verdict |
|---|---|---|
| one finger tap at raw 500,800 | id 0 down at 399.5,817.0 (= screen 799,1634) | calibration |
| two fingers, raw X +600 in 20 steps | ids **0 and 1** down at 699.5,717 and 899.5,717; 42 motions; both end at y = 417 (a two-finger swipe up, 300 logical px) | **PASS** |
| two fingers, raw Y +600 in 20 steps | ids 0 and 1 at 599.5,717 and 599.5,517; 42 motions; both end at x = 899.5 (a two-finger swipe right) | **PASS** |

`max simultaneous touch points: 2`: two real `wl_touch` points reach a client at once, which
pointer emulation could never deliver. `gestures:workspace_swipe_touch` is `false` (not set),
Hyprland default, so the touch workspace swipe is off in this config and was not enabled.

**D3.3 the bar, desktop mode** (stock Omarchy bar; run inside D4's desktop cold start).
`BARTEST_SETTLE=2.2 python3 docs/omarchy/tools/bartest.py touch 26`, real touch:

| target (x) | ws | new layer | verdict |
|---|---|---|---|
| Omarchy button (45) | 1→1 | **`omarchy-menu`** | reacts |
| workspace 1 (87) | 3→**1** | - | reacts (checked from workspace 3 in a second desktop cold start, since 1 was already active in the sweep) |
| workspace 2 (128) | 1→**2** | - | reacts |
| workspace 3 (170) | 1→**3** | - | reacts |
| workspace 4 (211) | 1→**4** | - | reacts |
| workspace 5 (253) | 1→**5** | - | reacts |
| network (3052) | 1→1 | **`omarchy-keyboard-panel`** | reacts |
| volume (3105) | 1→1 | **`omarchy-keyboard-panel`** | reacts |
| display (3160) | 1→1 | **`omarchy-keyboard-panel`** | reacts |

Round 4 measured 0/9 in this mode before the patch. The cursor follows each touch (45 → 22,12;
3052 → 1525,12), the same −1 px as D3.2. In mobile mode the bar is one touch target (tap toggles
quick settings, a pull opens it, `Bar.qml:450-466`): tap → `omamobile-quicksettings` (pre-check
and D3.5).

The ws1 check: stay-awake set to 2 again for it, `printf desktop > ~/.config/omdroid/ui`,
`coldstart.sh 1 --tag ws1-desktop` (PASS), `hl.dsp.focus({ workspace = "3" })` → ws 3, touch tap
87,26 → **ws 1**; mode file removed, `coldstart.sh 1 --tag ws1-mobile` → mobile layers, clients 0,
`VERDICT: PASS`; stay-awake restored, read back `0`.

**D3.4 focus by tap, typing.** Desktop mode, two byte-logger windows (`foot --app-id=r5a|r5b`
running `/tmp/r5-bytelog.py`). `focustest.py touch`: `active_before=r5b` → tap 805,1011 →
`active_after=r5a focus_moved=yes`. Then `adb shell input text r5typed`: `r5a.log` =
`72357479 70 6564` (= `r5typed`), `r5b.log` empty. Typing lands in the tapped window. Screenshot
`shots/d4-desktop-focus.png`: two tiled windows, the left one (r5a) with the active border.

**D3.7, two fingers in a terminal.** Two uinput fingers dragged down 800 px over foot after
`seq 1 300`: the view goes from 251-300 + prompt to **227-277** (`shots/d3-2f-before.png`,
`d3-2f-after.png`). foot scrolls with the touch stream; whether it uses the second point or only
the first is not distinguishable here (a one-finger drag scrolls it too, D3.6).

### D4 regressions

```
keyboard  uhid keyboard (hid, descriptor from docs/omarchy/r4-input-research.md appendix)
          Left GUI + usage 0x1F ("2"): j/activeworkspace 1 -> 2; LorieNative "Sending key: 133 (125 0 1)",
          "Sending key: 11 (3 0 1)"; Left GUI + 0x1E ("1"): 2 -> 1; top stays com.termux.x11.MainActivity
          (a first try with 0x1E alone sent Super_L + "1" while on workspace 1, so nothing moved: the
          research appendix calls 0x1E "2", but HID 0x1E is "1" and 0x1F is "2")
size      ./screen.sh rot 0  -> cur 2136x3200; probe: xroot 2136x3035, cage 2136x3034, monitor 1068x1517, VERDICT PASS
          pids cage 7632 / Hyprland 7641 unchanged, quickshell 7707 -> 14466 (shell restart only)
          ./screen.sh reset  -> Override density 352, accelerometer_rotation=1, cur 3200x2136;
          probe: xroot 3200x1971, monitor 1600x985, VERDICT PASS; Hyprland 7641 unchanged, quickshell -> 15165
          omarchy-watch.log: "layers do not fit … attempt 1/3", "omarchy-restart-shell rc=0", "layers fit again 3.7 s after the restart"
desktop   printf desktop > ~/.config/omdroid/ui; ./coldstart.sh 1 --tag d4-desktop: handover +3.6 s, desktop PASS +3.1 s,
          layers omarchy-background + omarchy-bar 1600x26; bar taps by touch: D3.3 (9/9); focus + typing: D3.4
mobile    rm ~/.config/omdroid/ui (missing = mobile, the state found); ./coldstart.sh 1 --tag d6-final:
          handover +9.8 s, desktop PASS +9.2 s, mobile layers (dock, launcher, bar 1600x44, two back strips), clients 0
```

### D5 decision: `touchMode = "3"` ships

Direct touch is what `73b7a0b` sets, and it stays. On the D2 APK every D3 item passed: the touch
device exists and is the APK's library, a touch lands within 1 screen pixel of where it was
tapped across the whole screen, the desktop bar reacts 9/9, focus and typing follow a tap, and
all seven mobile gestures work as plain quick swipes (the dock swipe-up was 0/10 under simulated
touch). A long press reaches QML (card actions), a drag scrolls a terminal, and two fingers
reach a client as two touch points. Nothing in D4 regressed. The library stays, as decided.

### D6 clean up

Session in `mobile` (mode file absent, as found), no test windows (`omarchy-hyprland-window-close-all`
rc=0, clients 0 after the final cold start), `stay_on_while_plugged_in` restored to the recorded
`0` (`svc power stayon false`, read back `0`), `probe.sh -q` → `VERDICT: PASS`. The patch needed
no rebuild, so `docker rm -f omdroid-aq-build omdroid-aquamarine-builder` ran (0 omdroid
containers left; images `omdroid-aquamarine:0.0.14`, `omdroid-guest:0.0.14` kept). The D1 backup
`files/r5-touch-backup/libaquamarine.so.0.14.0.orig` and the probes `/tmp/touchlog`,
`/tmp/r5-bytelog.py` stay in the app data (harmless, a few hundred KB); `/opt` holds the image
library again (`8a2a2cbe…`).

## Screenshots viewed

All under `<scratch>/omarchy/r5/touch-device/shots/`.

| File | Verdict |
|---|---|
| `d1-qs-open.png` | mode 2 on the new library: quick settings sheet and shade open, cursor at the tap |
| `d3-touchlog-overlay.png` | the probe surface covers the whole Omarchy area above the key bar |
| `d3-back-x20.png`, `d3-back-x3.png` | two tiled windows, unchanged after back (Escape went to the logger) |
| `d3-pill-home.png` | home screen: wallpaper, dock "Search apps…" |
| `d3-dock-switcher.png` | switcher open: a Foot card centred, a second card at the right, Clear all, Home |
| `d3-card-flick.png` | one card left |
| `d3-card-hold.png` | actions sheet: Foot / Show with… (No other app is open) / Cancel |
| `d3-card-tap.png` | foot full screen on workspace 1 |
| `d3-pill-hold.png` | foot, nothing opened by the hold |
| `d3-qs-pull.png` | quick settings sheet and shade open |
| `d3-drag-before.png`, `d3-drag-after.png` | 251-300 then 221-271 with the scroll indicator |
| `d3-2f-before.png`, `d3-2f-after.png` | 251-300 then 227-277 |
| `d4-portrait.png` | portrait: bar, foot full width, pill; nothing cut off |
| `d4-desktop-focus.png` | stock bar, two tiled windows, the tapped one (left) has the active border |

## What Phil should try with his fingers

1. A fast flick up on the dock (switcher) and on the pill over an app (home), with no pause.
2. Back from the very edge, left and right, in an app with a dialog open.
3. Two-finger scroll and pinch in a Qt or GTK app (and kinetic scroll in the drawer).
4. Dragging a quick-settings slider and paging the sheet sideways.
5. Text selection in foot (long press, then drag) and a long press on a drawer icon.
6. Typing on the soft keyboard after tapping a text field: does the IME come up?

## Not verified

- Real fingers: every touch here is `adb shell input` or a `uinput` device, both through Android
  InputReader and Termux:X11 like a finger, but with perfect straight-line timing.
- Pinch, rotate and three-finger gestures; whether apps use the second touch point (foot
  scrolled, but a one-finger drag does that too).
- Hyprland's touch workspace swipe: `gestures:workspace_swipe_touch` is `false` in this config
  and was not enabled.
- Moving a window by touch (Hyprland has no touch binding for it).
- The fresh-image path: the packager's new `lib/` copy is `bash -n` clean but no image was
  repacked this round; an updated install got the library from the APK (D3.1).
- The 1 px offset fix in Termux:X11 (below) is a proposal, not tested.

## Findings for other owners

- `termux-x11/app/src/main/cpp/lorie/cmdentrypoint.c:261-262` scales a touch to the valuator
  range against `width`/`height`; the X server spreads it over 0..W−1 and wlroots keeps the
  integer part (`backend/x11/input_device.c:245`), so every touch lands 1 X pixel up-left of
  the finger. Scaling against `width - 1`/`height - 1` would remove it.
- `docs/omarchy/r4-input-research.md` (appendix) names HID usage `0x1E` as "2"; it is "1"
  (`0x1F` is "2").
- `ProotCommandBuilder.kt:122` still builds its own `LD_LIBRARY_PATH` without
  `/etc/phoshdroid/lib`; `start.sh` overrides it, so it only matters for a launch that bypasses
  `start.sh`.

## Commits and the final build

| Commit | What |
|---|---|
| `27192a8` | `build(rootfs): ship aquamarine with wl_touch in the guest overlay` |
| `73b7a0b` | `feat(launcher): direct touch now that the guest has a touch device` |
| `03aed04`, `02e7c09`, `4eaa666`, `73d9aff`, `f2ca77a`, `45ca009` + this one | report and `docs/omarchy/tools/touchlog.c` |

Final APK: `app-debug.apk`, 1 715 699 122 bytes, sha256
`56db6d5201c8b08aa00331284d922d65601715aa0ae9d0b48a5a5bfa15f98ba4`, built from `73b7a0b`
(clean tree), installed on the tablet (`INSTALL: PASS`). Later commits are docs only.
