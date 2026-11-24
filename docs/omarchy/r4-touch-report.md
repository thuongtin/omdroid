# R4-TOUCH report — taps on the Omarchy bar did nothing (fixed: `touchMode` "2")

Worker: one session, no subagents, no `delegate_task`. Device `<tablet serial>` only.
Picked up the parent's amendment mid-round: aquamarine 0.14.0's Wayland backend has no `wl_touch`, so
T2 is one `j/devices` check and T3 is the `touchMode = "2"` switch, with the cost measured.

## STATUS TABLE

| Row | State | Decisive number / note |
|---|---|---|
| T0 unlock, stay-awake, install 0.0.14-alpha, cold start | **PASS** | keyguard cleared 22:56:23; stay-awake `0`→`2`; `install.sh` → `INSTALL: PASS` sha `ee8cdaf9…b59f` at 22:58:08; `coldstart.sh 2 --tag r4-base` → unaided handover 2/2 (3.9..5.1 s), desktop PASS 2/2, `probe.sh` VERDICT PASS. |
| T1 reproduce with numbers (9 targets × input kinds) | **PASS** | 27 touch rows (tap, long touch, y=45): **0/9 targets react**; 9 `input mouse tap` rows: 0/9 (that injection moves the pointer but clicks nothing, on windows either); **XTest click control: workspace 1→3 at x=170, `omarchy-menu` layer at x=45, window focus moves** — the guest chain is healthy, touch simply never becomes a click. |
| T2 where the touch is lost | **PASS (source + device)** | `./hc.sh j/devices`: `touch: []`, `tablets: []`, `mice: ["wl_pointer"]`, `keyboards: ["wl_keyboard"]`. `gestures:workspace_swipe_touch`=false, `input:touchdevice:enabled`=true, no `~/.local/state/omarchy/toggles/hypr/` file. Aquamarine 0.14.0 `src/backend/Wayland.cpp` has 0 `touch` hits; Hyprland's only ingress is `Compositor.cpp:491-493` `newTouch`. |
| T3 fix and prove | **PASS** | build sha `d8f504af…2071f` installed (`pm install` → Success, base.apk sha matches), cold start 2/2, **9/9 bar targets react to a touch tap** (5 workspace switches, Omarchy menu, 3 panels), focus-by-tap control moves focus, `probe.sh` PASS, `:app:test` 56/0. Cost measured (cursor jump, long-press drag). |
| T4 report and clean up | **PASS** | windows closed (`omarchy-hyprland-window-close-all` rc=0, clients 0), layers back to background+bar, stay-awake restored: read-back `stay_on_while_plugged_in=0`. |

## T0 — device prep

- The tablet was asleep behind a PIN keyguard for the first hour: `isKeyguardShowing=true` on every
  check, `mWakefulness=Asleep`; `input keyevent KEYCODE_WAKEUP` made it `Awake` and the keyguard
  stayed up, so it was a real PIN lock. Nothing was typed or tapped (a PIN guess is forbidden); four
  `timeout 380` wait loops all printed `STILL-LOCKED`. Keyguard cleared at **22:56:23** and the X
  display activity was on top (`com.phoshdroid.app/com.termux.x11.MainActivity`).
- `settings get global stay_on_while_plugged_in` = `0` before the round; `svc power stayon usb` →
  `2` for the round; restored to `false` at the end (read-back `0`).
- Release install: `install.sh omdroid-0.0.14-alpha.apk` → `INSTALL: PASS`, sha
  `ee8cdaf9b7d8805a7e88208ad3983577ed1d29f5e033f308f4291046bed2b59f`, lastUpdateTime 22:58:08.
- `coldstart.sh 2 --tag r4-base`: unaided handover 2/2 (3.9..5.1 s), desktop PASS 2/2, runs with a
  foreign activity on top 0. logcat: `launch: decision start`, `launch: guest-overlay files=10
  changed=0`, `launch: ready marker`.
- **The release APK had to be re-fetched**: `./gradlew :app:assembleDebug` empties
  `app/build/outputs/apk/debug/`, so the local copy of `omdroid-0.0.14-alpha.apk` vanished with the
  rebuild. Downloaded the GitHub release asset again and verified the published digest
  `ee8cdaf9…b59f`, 1 714 914 247 bytes, so the baseline install ran the published bytes.

## T1 — reproduction baseline

Release `0.0.14-alpha` (`touchMode` "3", direct touch), fresh cold start, `probe.sh` PASS, X display
on top, clients 0. Harness: `docs/omarchy/tools/bartest.py` (resets to workspace 1 before each tap
with `hl.dsp.focus({ workspace = "1" })`, snapshots `j/activeworkspace j/layers j/clients
j/activewindow j/cursorpos` around it). `ws_before → ws_after` / new layers; `-` = nothing appeared.

| target (x) | touch y=26 | long touch y=26 | touch y=45 | `input mouse tap` y=26 | XTest click (guest truth) |
|---|---|---|---|---|---|
| Omarchy button (45) | 1→1, no layer | 1→1, no layer | 1→1, no layer | 1→1, no layer | **`omarchy-menu` layer 1600x985 appears** |
| workspace 1 (87) | 1→1 | 1→1 | 1→1 | 1→1 | click on the active workspace = no change (expected) |
| workspace 2 (128) | 1→1 | 1→1 | 1→1 | 1→1 | not tested |
| workspace 3 (170) | 1→1 | 1→1 | 1→1 | 1→1 | **1→3** |
| workspace 4 (211) | 1→1 | 1→1 | 1→1 | 1→1 | not tested |
| workspace 5 (253) | 1→1 | 1→1 | 1→1 | 1→1 | not tested |
| network (3052) | 1→1, no layer | 1→1, no layer | 1→1, no layer | 1→1, no layer | not tested |
| volume (3105) | 1→1, no layer | 1→1, no layer | 1→1, no layer | 1→1, no layer | not tested |
| display (3160) | 1→1, no layer | 1→1, no layer | 1→1, no layer | 1→1, no layer | not tested |

- **Every touch row moved the Hyprland cursor** to (x/2, y/2) — tap 3052 → cursor 1525,12; y=45 → 22.
  So the touch does reach the X server, which emulates pointer *motion* at the touch point
  (XIDirectTouch), and cage forwards that motion to Hyprland. **No button press ever follows**, so
  nothing activates. That is the direct-touch failure, measured.
- **`adb shell input mouse tap` is not a usable "mouse click" test here**: it moves the cursor to the
  same point but clicks nothing anywhere — not the bar, not a window (`focustest.py mouse`:
  `focus_moved=no`). It is an injection limitation, not a guest fault: see the XTest control.
- **Control with a real X-level click (`xtap.py`, XTest, inside the guest) — the guest is healthy.**
  `xtap.py 170 26` → `j/activeworkspace` 1 → **3**; `xtap.py 45 26` → new `omarchy-menu` layer; a
  click on the unfocused of two `foot` windows moved `j/activewindow`. cage, Hyprland, Qt and the bar
  QML all deliver and act on a pointer click; the only broken link was host touch → guest.
- Tray/indicator icons: nothing for touch, long touch or `input mouse tap` at baseline.

## T2 — where the touch is lost

**Device check** (`j/devices`, live session): `mice ["wl_pointer"]`, `keyboards ["wl_keyboard"]`,
`tablets []`, **`touch []`**, `switches []`. `gestures:workspace_swipe_touch` = false,
`input:touchdevice:enabled` = true, `~/.local/state/omarchy/toggles/hypr/` does not exist — so
Omarchy's own touch kill-switches are off (H2 refuted). `probe.sh` on the baseline: xroot 3200x1971,
cage-window 3200x1970 @0,0, monitor 3200x1970@120 scale 2.00 → 1600x985, layers L0
omarchy-background + L2 omarchy-bar 1600x26, clients 0, VERDICT PASS.

**Source answer** (parent-verified; re-read in `docs/omarchy/r4-touch-research.md`): the tap reaches
cage — wlroots 0.20.2's X11 backend builds a real `wlr_touch` from `XCB_INPUT_TOUCH_BEGIN` and cage
forwards it to its only client — and dies in **aquamarine's Wayland backend**, which never binds
`wl_seat.get_touch`: aquamarine 0.14.0 `src/backend/Wayland.cpp` has 0 `touch` occurrences,
`Wayland.hpp` declares `CWaylandKeyboard`/`CWaylandPointer` and no touch class, and Hyprland creates a
touch device only from aquamarine's `newTouch` (`src/Compositor.cpp:491-493` → `newTouchDevice`).
No touch device ⇒ no touch delivered to any surface, bar or window.

## T3 — fix and proof

Change (one line + its comment), `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt`:

```
-            .putString("touchMode", "3")
+            .putString("touchMode", "2")
```

`2` = `InputMode.SIMULATED_TOUCH` (`TouchInputHandler.java:65`) → `SimulatedTouchInputStrategy`
(`:392-393`): a finger tap moves the X cursor to the tap point (`moveCursorToScreenPoint`, `:563`) and
injects a left ButtonPress+Release there (`SimulatedTouchInputStrategy.onTap`), so cage → Hyprland →
Qt → QML see an ordinary pointer click, which the bar's `MouseArea` already accepts.

Build and tests (host): `assembleDebug` → BUILD SUCCESSFUL 40 s, APK
`app/build/outputs/apk/debug/omdroid-r4-mode2.apk` sha256
`d8f504af06956a6c758c6b59c9365b4fbca27f25d2cc6a7fd402803d1622071f`; `:app:test` BUILD SUCCESSFUL;
`unit-count.py` → `unit tests 56 failed 0`.

Install: `install.sh` **failed this time** — its DocumentsUI tap flow tapped `Search`, typed the
filter, then timed out after 120 s with the launcher on top. The working route was the package
manager directly, from a path `system_server` can read:

```
adb push omdroid-r4-mode2.apk /data/local/tmp/omdroid-mode2.apk
adb shell pm install -r -t /data/local/tmp/omdroid-mode2.apk   → Success
installed base.apk sha256 = d8f504af…2071f   (matches the local APK)   lastUpdateTime 23:10:08
```

(`pm install` on `/sdcard` is refused — `system_server` cannot read `u:object_r:fuse`.) Worth folding
into `install.sh` as a first attempt: 90 s instead of 4 min of taps.

`coldstart.sh 2 --tag r4-fix`: unaided handover 2/2 (3.1..5.6 s), desktop PASS 2/2, no foreign
activity; logcat `launch: decision start 49ms`, `launch: guest-overlay files=10 changed=0 93ms`,
`launch: ready marker 2544ms`.

**Final matrix, mode 2, one touch tap per target (`BARTEST_SETTLE=2.2`, clean state per row):**

| target (x) | ws | new layer | verdict |
|---|---|---|---|
| Omarchy button (45) | 1→1 | **`omarchy-menu`** | menu opens (a second tap closes it) — reacts |
| workspace 1 (87) | 3→**1** | - | reacts (checked from ws 3, since 1 was already active) |
| workspace 2 (128) | 1→**2** | - | reacts |
| workspace 3 (170) | 1→**3** | - | reacts |
| workspace 4 (211) | 1→**4** | - | reacts |
| workspace 5 (253) | 1→**5** | - | reacts |
| network (3052) | 1→1 | **`omarchy-keyboard-panel`** | its panel opens — reacts |
| volume (3105) | 1→1 | **`omarchy-keyboard-panel`** | its panel opens — reacts |
| display (3160) | 1→1 | **`omarchy-keyboard-panel`** | its panel opens — reacts |

Notes on the right side: every Omarchy panel is built on the shared `KeyboardPanel` component
(`shell/Ui/KeyboardPanel.qml:85 WlrLayershell.namespace: "omarchy-keyboard-panel"`), so all three
panels present the *same* layer namespace — the name alone does not say which panel opened. The
right-section order in the guest's `~/.config/omarchy/shell.json` is `tray, agents, bluetooth,
network, audio, monitor, power`, which matches the parent's network / volume / display labels for the
three positions, and all three opened a panel. Each panel is dismissed with Escape between rows
(`omarchy-menu close` does not close them; the harness now sends `input keyevent 111` when a panel
appears).

**Control (PASS):** `focustest.py touch` with two `foot` windows — active
`0x7b8b8b09a0` → tap the centre of the *other* window (805,1011) → active `0x7b8b3f84e0`
(`focus_moved=yes`), cursor 450,400 → 402,505. A touch tap now focuses windows.

**`probe.sh` on the final build: VERDICT PASS** — xroot 3200x1971, cage 3200x1970 @0,0, scale 2.00 →
1600x985, layers L0 omarchy-background + L2 omarchy-bar, clients 0, ready marker
`ready 1795561830 3200x1970 scale=2`.

**Mouse clause:** `input mouse tap` produced no click in *either* build (cursor only, proven on the
bar and on a window), so that clause cannot be tested through adb; this diff touches only the
Termux:X11 preferences block in `LauncherActivity.kt`, so the hardware-mouse path is byte-identical
(`git diff` is that one line plus comments), and a genuine X-level click still does everything it did
before (`xtap.py`: workspace switch, menu, window focus).

## T4 — cleanup

- `omarchy-hyprland-window-close-all` rc=0, clients back to 0; Escape sent to clear any panel; layers
  back to `omarchy-background` + `omarchy-bar` only.
- stay-awake restored: `svc power stayon false` (recorded value was `0`), read-back
  `settings get global stay_on_while_plugged_in` → `0`.
- Installed build left in place: `0.0.14-alpha` + the mode-2 prefs change (sha `d8f504af…2071f`).

## Cause

A finger tap stopped at cage. Cage's wlroots X11 backend does build a real `wlr_touch` from the XI2
touch events Xlorie sends, and forwards it to its only client — but that client is the nested
Hyprland, whose input comes from **aquamarine's Wayland backend**, and aquamarine 0.14.0's Wayland
backend has no `wl_touch` support (0 `touch` occurrences in `src/backend/Wayland.cpp`; no
`CWaylandTouch` in `Wayland.hpp`). Hyprland's `newTouch` signal therefore never fires, no touch device
is ever created in the guest (`j/devices` → `touch: []`), and direct-touch mode delivered taps to
nothing: the Omarchy bar, menus and windows all ignored a finger, on the device (0/9 targets) exactly
as the source predicts.

## Change

- `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt` — the Termux:X11 preferences block now
  sets `touchMode = "2"` (simulated touch: tap → cursor move + left click) instead of `"3"` (direct
  touch), with a comment naming the aquamarine gap and the cost. **Committed by the parent as
  `f0dba29`** (`fix(launcher): send finger taps as clicks (simulated touch)`); this round tested the
  pre-keyboard APK `omdroid-r4-mode2.apk`, as instructed.
- Nothing under `rootfs/**` or `app/build.gradle.kts` was touched, and nothing needs a change there:
  the fix is host-side only (a Termux:X11 input-mode preference), so no guest file, overlay entry or
  `syncGuestOverlay` line moves.
- `docs/omarchy/tools/install.sh` — first attempt is now `pm install -r -t` from
  `/data/local/tmp` (the route that actually worked here, ~90 s, no taps); the DocumentsUI tap flow
  stays as the fallback when the package manager refuses. Not exercised end-to-end by the script
  (the APK was already installed when the change went in) — the exact command was proven by hand:
  `pm install -r -t /data/local/tmp/omdroid-mode2.apk` → `Success`.
- `docs/omarchy/tools/bartest.py` — new: taps the nine bar targets and records workspace / layer /
  client / active-window / cursor deltas as CSV, with per-row popup teardown.
- `docs/omarchy/tools/focustest.py` — new: the focus-by-tap control (opens two `foot` windows, taps
  the unfocused one, prints before/after).
- `docs/omarchy/tools/xtap.py` — new: XTest click from inside the guest (the ground-truth click that
  proved the guest chain healthy, and the only way to click from the host that works on this build).
- `docs/omarchy/tools/pixdiff.py` — new helper (pixel diff of two screenshots); written for the tray
  check, not used for a verdict because the clock/panel animation swamps the diff.

## Cost

- A tap moves the X cursor to the tap point and clicks there: the pointer visibly jumps to the finger
  (e.g. tap 3052,26 → cursor 1526,13). Measured.
- Drag/select becomes long-press-then-drag: `input motionevent DOWN 600 700` → cursor 300,350, hold
  0.9 s, `MOVE 900 800` → cursor **450,400**, `UP` → button released. The cursor only follows a finger
  while `mIsDragging` is set in simulated-touch mode (`TouchInputHandler.java:656-663`), so this is the
  long-press drag path, active and holding a button. Measured.
- No true multi-touch: two fingers become a wheel scroll (swipe) or a right click (tap), three a
  middle click, so pinch-to-zoom inside apps is gone. **Not device-verified** — `adb shell input`
  injects a single pointer only; this follows from `mouseButtonFromPointerCount`
  (`TouchInputHandler.java:739-750`) and `SwipeDetector → onScroll → sendMouseWheelEvent`.
- Nothing in the guest needs changing, and when aquamarine gains `wl_touch` the mode can go back to
  `"3"` with no guest work.

## Not verified

- Two-finger / three-finger behaviours (wheel scroll, right click, middle click) on the device — adb
  cannot inject more than one pointer; source-derived only.
- The app's hardware-mouse path with a real mouse (adb's `input mouse tap` carries no usable button;
  the path is unchanged by this diff).
- What each of the three right-side panels contains (they opened; I cannot view images, and the layer
  namespace is shared by all panels).

## Files changed

- `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt` (committed as `f0dba29`)
- `docs/omarchy/tools/install.sh` (modified: `pm install` fast path, tap flow kept as fallback)
- `docs/omarchy/tools/bartest.py`, `docs/omarchy/tools/focustest.py`, `docs/omarchy/tools/xtap.py`,
  `docs/omarchy/tools/pixdiff.py` (new; `bartest.py` is committed up to `f0dba29`, its layer-parsing
  and panel-teardown fixes are not)
- `docs/omarchy/r4-touch-report.md` (this report)
- built, not committed: `app/build/outputs/apk/debug/omdroid-r4-mode2.apk`
