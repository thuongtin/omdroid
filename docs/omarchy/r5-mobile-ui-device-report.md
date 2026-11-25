# R5-MOBILE-DEVICE report: the Omamobile mobile UI on the tablet

Worker: Hermes child agent `70c5cfef` (parent `f8d5582c`), run in-session, no delegation.
Repo `<repo>`, branch `main`, base commit `2a64277`.
Build under test: `omdroid-mobile-2a64277.apk` (sha256 `ebd4991d…f065`, built from `2a64277`).
Device: the Xiaomi Pad (Android 16, HyperOS), serial kept out of the repo.
Scratch: `<scratch>/omarchy/r5/device/`.

## STATUS TABLE

| Step | Status | Decisive fact |
|---|---|---|
| M0 install + cold start | **PASS** | `INSTALL: PASS` sha256 `ebd4991d…f065` (installed == local); cold start handover +13.3 s, desktop PASS +12.7 s; `probe.sh -q` → `VERDICT: PASS` (root 3200x1971, monitor 1600x985 @2). Keyguard off; `stay_on_while_plugged_in` was `0`, set to `2`. |
| M1 shell up, five plugins | **PASS** | scan file `grep -c '^===thirdparty'` = **5** (back, bar, launcher, quicksettings, switcher); session log has the five `omdroid-ui: linked omamobile.*` lines; `omarchy-shell shell listPlugins` names all five, `omamobile.bar` `"active":true`, stock `omarchy.bar` `"enabled":false`; layers `omarchy-bar 1600x44`, `omamobile-dock 1600x96`, `omamobile-launcher 1600x941`, 2x `omamobile-back 77x941`. |
| M2 no QML errors | **PASS** | Shell log = `$XDG_RUNTIME_DIR/quickshell/by-id/<id>/log.qslog`, read with `qs log -i <id> -r "*=true"` (505 lines): **0** `failed to load`, **0** `TypeError`/`ReferenceError`. Two omamobile warnings, both from optional launcher paths that were not ported: `omamobile.voice/VoiceLinkClient.qml: No such file or directory` (Loader, `Launcher.qml:603`) and `Process failed to start … omamobile-osk-watch` (`Launcher.qml:519`). The rest are the known missing daemons (UPower, PipeWire, NM, BlueZ, portal, polkit). |
| M3 bar 44 px, tap opens quick settings | **PASS** | Layer `omarchy-bar 1600 x 44 @ 0,0` (44 logical = 88 screen px). `input touchscreen tap 1600 44` → new layer `omamobile-quicksettings 1600 x 985` (overlay); `shots/m3-qs-open.png`: sheet (clock, gear, 4 tiles, "No backlight") on the left 58 %, notification shade with Clear all on the right. Tile labels truncate (`Bluet…`, `No adapt…`, `NetworkM…`, `Do not distu…`) → M10. |
| M4 dock, drawer, pill, app launch | **PASS** (after fix `5030297`) | Dock visible on an empty workspace (`omamobile-dock 1600x96 @0,889`); tap → drawer, 6-column grid (`shots/m4-drawer.png`); tap Foot → `clients 1 foot`. **Before the fix the whole shell died the moment Foot mapped** (`j/layers` empty, watcher gave up after 3 restarts): `WAYLAND_DEBUG=1` shows `wl_display#1.error(…, "invalid version for zwp_linux_dmabuf_v1#54.get_default_feedback (3, need at least 4)")`, exit 255; control without `omamobile.switcher` runs with Foot open (exit 124, 0 `get_default_feedback`). After the fix (switcher cards without `ScreencopyView` under proot): shell pid stable with Foot open, Foot at `0,44 1600x882` between the bar and a `omamobile-home-strip 1600x59` pill (`shots/m4-foot-fixed.png`); long-press-drag up on the pill → home (workspace 2, dock back; log `omamobile-home-indicator: swipe -105 (pill)`). A single tap on the pill does nothing (upstream design). 14 of 19 drawer entries have no icon → M10. |
| M5 back gesture vs Android edge | **PASS** (injected input) | Focused window `--app-id=backtest` (a foot running a byte logger; plain foot is on Omamobile's terminal list and goes home instead). Long-press-drag from **x = 20 screen px** (10 logical; the strip is 14 logical wide) inward to x = 320 → log `omamobile-back: swipe left back` and the window logged `1b` (Escape), same as the `wtype -k Escape` control. Android kept the X11 activity on top; HyperOS's `miui-gesture` monitor saw the stream and cancelled (`onInputEvent action=ACTION_CANCEL`); AOSP `EdgeBackGestureHandler mIsEnabled=false`; the X11 window requests gesture exclusion `(0,0,3200,2103)`. A quick swipe from x = 3 sent nothing to the guest and no Android back. Real fingers were not tested. |
| M6 switcher | **PASS** (dock swipe-up FAIL → M10d) | Opens from `omarchy-shell shell summon omamobile.switcher '{}'` (layer `omamobile-switcher 1600x985`, overlay) and from a pill hold-then-swipe past −120 logical px. Under proot each card is an icon + window-title face (the `5030297` fallback): two cards, Foot and backtest (`shots/m6-switcher-open.png`, `m6-switcher-flick.png`). Tap the Foot card → `active foot`, workspace 1. Hold a card and drag it up (screen y 1100 → 300) → that window closes, `clients 2 → 1` (`m6-after-flickclose.png`). A hold-then-swipe up on the **dock** (empty workspace 3, y 1872 → 1500) did **not** open it: no switcher layer, `m6-switcher.png` is the plain home screen. |
| M7 the switch both ways | PENDING | |
| M8 tiles that must not lie | PENDING | |
| M9 type size | PENDING | |
| M10 look and fix | PENDING | |

## Input under simulated touch

Termux:X11 `touchMode = "2"`. Read from
`termux-x11/app/src/main/java/com/termux/x11/input/TouchInputHandler.java`, measured with
`adb shell input touchscreen …` and Hyprland's `j/cursorpos`.

| The finger does | The guest receives | Evidence |
|---|---|---|
| tap | a left click at that point (pointer moved there first) | `onTap` → `moveCursorToScreenPoint` + `onTap(BUTTON_LEFT)` (`:677-693`); every tap in M3-M6 |
| quick swipe, no hold (`input touchscreen swipe … 300`) | **nothing**: no motion, no button | cursor stayed `800,955` through a 2400,1000 → 2400,400 swipe; `onScroll` moves the pointer only while `mIsDragging` (`:646-663`) |
| hold (Android long-press) | left button **down** at the finger, held | `onLongPress` → `onPressAndHold(BUTTON_LEFT)`, `mIsDragging = true` (`:722-736`) |
| hold, then move | a real drag: motion with the button held, release on lift | cursor 800,955 → 800,850 after a hold-drag on the pill; pill `swipe -105`, back edge (M5), card flick and switcher hold-swipe (M6) all worked this way |
| hold still > 0.45 s after the press | Qt `TapHandler.longPressed` first (on the pill: `omamobile-home-indicator: voice start`), then the drag still runs | M4 log order: `voice start`, then `swipe -105 (pill)` |
| two fingers | scroll (moving) or right click (tap) | code only (`:633-644`, `mouseButtonFromPointerCount`); not tested |

So every Omamobile gesture (dock and pill swipe, back edge, card flick, sheet pull) needs a
hold first. A flick without the hold does nothing: a host input-mode limit that the real-touch
work addresses, recorded here and not worked around.

## Findings for other owners

- `omarchy-watch.py` (parent's file) restarts the shell 3 times and then gives up, leaving a
  session with no bar, wallpaper, dock or pill (`omarchy-watch.log`: `giving up on 3200x1970
  after 3 attempts`). Seen when the switcher crash killed every restart.
- The stock Omarchy shell has no `ScreencopyView` (parent's check: 0 files in the bundle), so
  the dmabuf v3/v4 crash is Omamobile's switcher only.

## Log

(sections are filled in as each step lands)
