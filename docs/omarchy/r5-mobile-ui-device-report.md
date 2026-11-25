# R5-MOBILE-DEVICE report: the Omamobile mobile UI on the tablet

Worker: Hermes child agent `70c5cfef` (parent `f8d5582c`), run in-session, no delegation.
Repo `<repo>`, branch `main`, base commit `2a64277`.
Builds under test: `omdroid-mobile-2a64277.apk` (`ebd4991d…f065`, M0-M6), the parent's `omdroid-mobile-5030297.apk` (`a0f1cb6b…b37a`, M7-M9) and my own `omdroid-mobile-r5fix.apk` (`0a229e1a…1f80`, built from the tree of `9a020d1`, M10 and the finish).
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
| M7 the switch both ways | **PASS** | APK `a0f1cb6b…b37a` (from `5030297`), guest `Switcher.qml` sha `afcee6cc…` = repo. `printf 'desktop\n' > ~/.config/omdroid/ui`, cold start (`VERDICT: PASS`, layers `omarchy-background` + stock `omarchy-bar 1600x26` only): session log `omdroid-ui: shell.json: stock bar and plugin list restored`, `looknfeel.lua: mobile rules removed`, five `unlinked omamobile.*`; `shell.json` has **0** `omamobile` ids (`bar.id` null, `plugins []`) and is semantically identical (`jq -S` + `diff`) to the pre-mobile baseline from the image; `hyprctl getoption general:gaps_in` → `5 5 5 5`; 0 plugin links; `shell.toml` gone; `looknfeel.lua` sha `d36d5ae6…` = the stock baseline, 0 markers. Screenshot `shots/m7-desktop-bar.png`: stock bar (workspace dots, centred clock, tray). `printf 'mobile\n'`, cold start (`VERDICT: PASS`): mobile layers back, `bar.id omamobile.bar` + four panels, gaps `0 0 0 0`, 5 links, the four `shell.toml` keys. |
| M8 tiles that must not lie | **PASS** | Expanded sheet, two pages (`shots/m8-qs-page1-crop.png`, `m8-qs-pages.png`). Dimmed, each with its reason: Wi-Fi `NetworkM…`, Bluetooth `No adapt…`, Torch `No flash LED`, Mobile data `No modem`, Rotation lock `No sensor`, Airplane mode `No radios`, Location `No GNSS`, Battery saver `No power profiles`, Night light `No hyprsunset`, NFC `No NFC`, Fingerprint `No sensor`, Keyboard `No keyboard`, Dictation `Not runn…`; sliders `No backlight`, `No audio output`. Working: Do not disturb `Off`, Dark theme `Tokyo Night` (on), Clipboard `History`. **No tile claims "on" for a missing backend.** Hotspot is not in the default tile set (not checked in edit mode). The handle tap expanded the sheet; a hold-drag sideways changes the page. |
| M9 type size | **PASS** (one defect → M10) | `omarchy-display-text-size` → `text size: 16 px`. Omarchy menu (`omarchy-menu toggle`, the SUPER+SPACE binding), measured on the screenshots (bright-pixel text bands in the label column): desktop text band **28** screen px, row pitch **106** (53 logical) (`shots/m9-desktop-menu.png`); mobile text band **37**, row pitch **142** (71 logical) (`m9-mobile-menu.png`): both × 1.33 = 16/12. Defect: in mobile the menu box ends above the dock and its tenth row (System) is cut off at the bottom. |
| M10 look and fix | **PASS** (4 fixes; the items under "Left" are not fixed) | Final APK `0a229e1aaf35f7f093a79f70791bc450e222d3523490950067925fd7c5661f80`, built from the tree that `9a020d1` commits (the APK's `omdroid-ui.sh`, `Launcher.qml`, `QuickSettings.qml`, `Switcher.qml` sha-match the repo and the guest), `INSTALL: PASS`, cold start `VERDICT: PASS`. **(a)** `a44b0a1`: a 1.5 s hold + release on the dock now opens the drawer (`"opened":true`), so no long press fired; quick taps still open it. **(b)** `dec7402`: 13 web-app icons linked, the drawer shows 18 of 19 icons (`shots/m10b-drawer-final.png`; Discord ships no PNG). **(c)** `9a020d1`: three tile columns, every tile name fits (`docs/screenshots/mobile-quicksettings.jpg`); only Wi-Fi's state `NetworkManager no…` is still cut. **(d)** dock swipe-up: not fixed, recorded. Injected hold-drags open nothing (0/10, old and new QML); XTest drags whose first steps are small open the switcher (3/3); the same big jumps sent through XTest open nothing (0/2). |

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

## M10 details

### Fixes (each committed with exactly its paths)

| Commit | Fix | Device proof |
|---|---|---|
| `5030297` | Switcher (`Switcher.qml`): under `OMARCHY_PROOT=1` a card is an icon + title face, no `ScreencopyView` | Before: the shell exited when any app mapped (`get_default_feedback (3, need at least 4)`), the watcher gave up. After: the shell stays up with apps open in every run since (M4, M6, M10). |
| `a44b0a1` | Search pill and home pill (`Launcher.qml`): `longPressThreshold: root.voice ? 0.45 : 3600` | Before (M4 log): `voice start` at every pill hold. After, on the final APK: a 1.5 s hold + release on the dock opens the drawer (`"opened":true`; a long press would have swallowed that tap). A quick tap still opens it. Pill hold-drags still go home or to recents. |
| `dec7402` | `omdroid-ui.sh`: mobile links each web-app PNG as `~/.local/share/icons/hicolor/512x512/apps/<Icon>.png`; desktop removes them | Device: `app icons: linked 13 web-app icons`, drawer 18 of 19 icons (was 5 of 19). Dry run on the image copy: mobile → 13 links; a second mobile start changes nothing; desktop → `removed 13 links` and the `icons` folder is gone. `bash -n` clean. |
| `9a020d1` | Quick settings (`QuickSettings.qml`): 240 px a tile column, three columns at 1600 px | Device A/B (`shots/m10c-AB.png`): three columns fit every name; four columns on a 70 % sheet clipped the fourth column. |

Committed bytes = APK bytes = guest bytes for all four files (sha256 prefixes `afcee6cc`,
`d6341cb8`, `7bf299b1`, `a2840bf5`). `SOURCE.md` has one row per changed upstream file.
`0` as the threshold was tried first and dropped. With it, quick taps on the dock opened nothing,
but that ran on shells restarted with `omarchy-restart-shell`, where quick taps on the dock also
failed with `3600`. So it was not isolated.

### (d) The dock swipe-up, one look

| Input on the dock (empty workspace) | Switcher opened |
|---|---|
| `adb input motionevent` hold 0.8-1.3 s, then moves of 42, 130, 200 screen px | 0 of 10 (M6, old and new QML, restarted and cold shells) |
| XTest from inside the guest: press, 12 steps of 31 px | 1 of 1 |
| XTest: first steps 12, 20, 20, 30 px, then 90, 200 px, 0.4 s apart | 2 of 2 (one on the final APK) |
| XTest: the injected path's jumps (42, 130, 200 px), 0.4 s or 0.03 s apart | 0 of 2 |

So the dock's `DragHandler`, which sits on the parent of the search pill's `TapHandler`
(`Launcher.qml:442-466`), does not take a drag whose first motion after the press is one big
jump. The pill strip's handlers sit side by side (`:1217-1268`) and take the same jumps. Simulated
touch sends exactly that jump: the first motion after Android's long press. Not fixed blind. A real
finger's first move may well be smaller, but that is untested. Real touch (`wl_touch`) removes the
hold altogether. Over an app, recents is still reachable with a hold-swipe on the pill.

### Left (found, not fixed)

1. Omarchy menu (SUPER+SPACE) in mobile: at 16 px type the menu box ends above the dock and its
   tenth row (System) is cut off (`shots/m9-mobile-menu.png`). This is the stock menu, not an
   Omamobile file.
2. Notification clutter: 8 copies of "Screensaver only runs in Alacritty, Foot, Ghostty, or Kit…",
   from the stock idle screensaver (`idle.screensaver 150`), fill the shade.
3. The launcher's one-time hint "Hold the pill to talk · double-tap for the keyboard" names voice
   and keyboard, and neither is ported (`Launcher.qml:629`).
4. Quick settings: expanded from its handle it opened on page 2 both times. The page dots sit
   about 16 logical px apart, too close to tap one; a hold-drag sideways pages.
5. Wi-Fi tile state `NetworkManager no…` is still cut at three columns.
6. Discord has no icon: the image ships no PNG for `omarchy-discord`.
7. The bar's middle is empty (the phone camera-cutout gap). On the tablet the strip shows only
   the clock at the left and one icon at the right.
8. `omarchy-watch.py` gives up after 3 restarts (see "Findings for other owners").

## Screenshots viewed

All under `<scratch>/omarchy/r5/device/shots/` unless a repo path is given.

| File | Verdict |
|---|---|
| `m0-1.png` | first desktop: 44 px bar (clock, icons), wallpaper, dock "Search apps…", Android key bar below |
| `m3-qs-open.png` | sheet on the left 58 %, shade on the right; tile names cut (`Bluet…`) |
| `m4-drawer.png` | 6-column drawer, 14 of 19 entries without an icon |
| `m4-foot.png` | after Foot mapped: no bar, no dock (the crash) |
| `m4-foot-fixed.png` | Foot between the bar and the 59 px pill strip |
| `m4-pill-tap.png`, `m4-pill-swipe.png` | a quick tap on the pill does nothing |
| `m6-switcher.png` | plain home screen after a dock hold-drag (no switcher) |
| `m6-switcher-open.png`, `m6-switcher-flick.png` | two icon + title cards, readable titles |
| `m6-after-flickclose.png` | one card left after the flick-close |
| `m7-desktop-bar.png` | stock bar: workspace dots, centred clock, tray |
| `m9-desktop-menu.png`, `m9-mobile-menu.png` | menu rows ×1.33 in mobile; System row cut |
| `m8-qs-collapsed.png`, `m8-qs-pages.png`, `m8-qs-page1-crop.png` | every missing backend dimmed with its reason |
| `m10b-drawer-icons.png`, `m10b-drawer-icons2.png` | drawer did not open from a tap on a restarted shell |
| `m10c-AB.png` | A (3 columns) fits all names; B (4 columns, wider sheet) clips its fourth column |
| `m10b-drawer-final.png` | 18 of 19 icons, labels readable |
| `m10c-qs-final.png` | page 2, three columns, all names fit |
| `docs/screenshots/mobile-desktop.jpg` | final home: bar (clock, Wi-Fi-off icon), wallpaper, dock; no windows, nothing overlapping |
| `docs/screenshots/mobile-quicksettings.jpg` | page 1, three columns, names fit; only `NetworkManager no…` is cut; shade with 10 notifications |

## What still needs real touch

- A flick without a hold does nothing (host input mode, see the input table).
- The dock swipe-up (above): the simulated stream's first motion is one big jump.
- Hold-then-swipe timing on the pill. Injected moves arrive about 0.4 s apart, so a swipe can read
  as "swipe and hold" and open recents instead of going home (seen once on the final APK, while
  M4 went home).
- Two-finger anything, pinch, kinetic scrolling.
- Back from the outermost pixels: a quick swipe from x = 3 delivered nothing.

## Not verified

- Real fingers. Every input here was `adb shell input` (simulated touch) or XTest from inside the
  guest.
- QML debug lines (`console.log`) did not show in the shell log of shells restarted by
  `omarchy-restart-shell`, nor in the final cold-started shell. So the absence of `voice start` on
  the final APK is shown by behaviour (the tap after a long hold), not by the log.
- M7-M9 ran on APK `a0f1cb6b` (`5030297`). The later fixes do not touch the mode switch except
  the icon links. Their desktop removal was proven in the dry run, not by a desktop cold start
  on the final APK.
- The Hotspot tile is not in the default set; edit mode was not opened.
- The menu clipping, the notification clutter and the false pill hint are not fixed.

## Finish state

Mode file removed again (missing means mobile, as before this round). No windows (`clients 0`),
quick settings closed, cold start `VERDICT: PASS` on APK `0a229e1a…1f80`.
`stay_on_while_plugged_in` restored to the recorded `0` and read back `0`.

# Round 2: polish with real touch

Real touch shipped in between (`docs/omarchy/r5-touch-device-report.md`): the guest has a
`wl_touch` device and `touchMode = "3"`. Starting build: APK `56db6d52…` from `73b7a0b`.
`stay_on_while_plugged_in` was `0` at the start of this round, set to `2` while working.

## Round 2 STATUS TABLE

| Step | Status | Decisive fact |
|---|---|---|
| R1 screensaver notifications | **PASS** | Cause: the guest has no `xdg-terminal-exec`, so `omarchy-launch-screensaver` gets an empty terminal and notifies. It also lacks `ttfx` and the branding text, so the screensaver cannot run here (details below). Fix `6b31334`: Omarchy's own `screensaver-off` flag, set once in both modes. Proof: `dbus-monitor` on `Notify` for **610 s** idle. Inside the window the idle cycle started (`idle-cycle-start: screensaver=150 lock=300` at 01:25:54) and the screensaver process exited 1. **0** "Screensaver only runs" calls (the 1 Notify seen was my own probe). `omarchy-launch-screensaver` run by hand exits 1 with no Notify. A second `omdroid-ui.sh` run changes nothing. |
| R2 pill hint | **PASS** | `9229e3b`: with the done marker cleared and an app opened, the strip's hint Notify reads "Swipe up on the pill to go home · swipe up and hold for recent apps" (`dbus-monitor`), and `omdroid-pill-hint` is claimed. The toast shows top right (`shots/r2-hint.png`). R6 checks both gestures it names. |
| R3 menu's last row | **PASS** (no change needed) | The stock menu caps the card at 70 % of the screen and ends it mid-row on purpose, as a "more below" cue (`Menu.qml:150-175`). Its `ListView` scrolls. With real touch, one quick swipe up on the list (`input touchscreen swipe 1600 1400 1600 600 180`) scrolls it so **System** is fully visible (`shots/r3-menu-ab.png`, left as opened, right after the swipe). |
| R4 pointer after touch | **PASS** | The stock `~/.config/hypr/looknfeel.lua:20` sets `hide_on_touch = false`. Before: an arrow is drawn at the last tap (`shots/r4-cursor-ab.png`, left). Fix `d5cc16d`: the mobile block sets `cursor = { hide_on_touch = true }`. On the device, reset at runtime to `false` → `omdroid-ui.sh` rewrites the block → Hyprland reloads to `bool: true` → two taps → no arrow at the tapped spot (`shots/r2r4-check.png`, left). Desktop mode drops the block, so the stock `false` returns. |
| R5 quick-settings page dots | **PASS** | `2cfe009`: each dot is a `Style.space(44)` target (59 logical, 117 screen px at 16 px type) with a 10 px dot; the current page is a wide accent pill (`shots/r5-dots-1.png`). A tap on the other dot at (862,1000) moved the accent pill from x 948-1015 to **830-897** and turned the tile page (20367 sampled tile-area pixels changed, `r5-dots-2.png`). |
| R6 quick swipes, look again | PENDING | |
| R7 own build, re-proof | PENDING | |
| R8 screenshots, finish | PENDING | |

## R1. Why the screensaver notification fired

The idle service (`shell/plugins/services/idle/Service.qml:65-68`) runs
`omarchy-launch-screensaver` after `idle.screensaver` (150 s). That script gets the terminal from
`xdg-terminal-exec --print-id` (`:14`). The guest has no `xdg-terminal-exec`, so `terminal` is
empty, the `case` falls through, and it sends "Screensaver only runs in Alacritty, Foot, Ghostty,
or Kitty" and exits 1 (`:16-21`). `$TERMINAL` is unset. `~/.config/xdg-terminals.list` names
`foot.desktop`, and foot is installed. Even with a terminal the screensaver could not run: it
draws with `ttfx` (`omarchy-screensaver:39`), which is absent too, as is the branding text it
animates (`~/.config/omarchy/branding/screensaver.txt`). Making it work means adding packages
to the image. Android already owns the screen timeout, so `omdroid-ui.sh` turns it off in both
modes with Omarchy's own flag, `~/.local/state/omarchy/toggles/screensaver-off` (the file
`omarchy-toggle screensaver-off` writes). `omarchy-launch-screensaver` checks that flag before the
terminal and exits quietly (`:9-11`). It is set once and recorded in
`~/.local/state/omdroid/ui/screensaver-off.ours`, so a user who turns the screensaver back on
keeps it on.
