# R5-MOBILE-UI report: Omamobile's phone shell pieces in Omdroid

Worker: Hermes child agent (parent `f8d5582c`). No device in this run. Repo
`<repo>` at base commit `24178f7`.
Ported from `derekross/omamobile` at `b5baaea7a96733a587b53e8669fde4301769fd5f`.
Guest facts are read from the image itself: `app/src/main/assets/rootfs.bin`
extracted to `<scratch>/omarchy/r5/mobile-ui/root/`.

## STATUS TABLE

| Step | Status | Decisive fact |
|---|---|---|
| U1 mechanism | **PASS** | Written down before code; every entry below cites the guest file it was read from. The theme override has one home only: `~/.config/omarchy/shell.toml` (the state theme dir is deleted by `omarchy-theme-set` and its `shell.<section>.toml` files are merged at theme-set time, not read at runtime). |
| U2 vendor + adapt | **PASS** | 5 plugins + 2 helper scripts vendored: 42 upstream files byte-identical to `b5baaea` (`diff -r`, `cmp`), plus `LICENSE`, `SOURCE.md`, 3 stub helpers. Every import resolves in the guest: 19 QML files parse under `qmlformat` (0 failures), 12 of 14 JS files pass `node --check` (2 fail only on QML's `.pragma library` line). |
| U3 session wiring | **PASS** | `omdroid-ui.sh` (new, 1 line in `start.sh`, before the index), `bash -n` clean. desktop restores: theme keys removed, `shell.json` back to stock keys, `looknfeel.lua` byte-identical to baseline, plugin links gone. |
| U4 packaging | **PASS** | packager + `syncGuestOverlay` list the same files; `:app:mergeDebugAssets :app:test` → BUILD SUCCESSFUL, 47 files in the generated tree and in both merged asset trees; `unit-count.py` → `unit tests 63 failed 0`. |
| U5 dry run | **PASS** | Five starts against a scratch copy of the guest home: first (mobile), second (byte-identical, nothing rewritten), user-edited (left alone), switch to desktop (exact restore), back to mobile. `omarchy-plugin-index.sh` lists all five as `thirdparty`. Outputs pasted below. |
| U6 report | **PASS** | This file. |

## U1. Mechanism: what goes where, written when, undone how

| What | Where it lives | Written when | How `desktop` undoes it |
|---|---|---|---|
| The five plugin trees | `rootfs/overlay/etc/phoshdroid/omamobile/plugins/omamobile.*` → guest `/etc/phoshdroid/omamobile/plugins/` | image build (packager) + every APK update (`syncGuestOverlay`) | left on disk, unused |
| Their plugin entries | symlinks `/home/omarchy/.config/omarchy/plugins/omamobile.*` → `/etc/phoshdroid/omamobile/plugins/omamobile.*` | `omdroid-ui.sh`, every mobile start | removed (only links pointing into `/etc/phoshdroid/omamobile`) |
| Helper binaries | `/etc/phoshdroid/omamobile/bin/{omamobile-launch,omamobile-home,omamobile-*-watch,omamobile-browser-setup}`; `/usr/local/bin/<same names>` symlinks | image build creates the `/usr/local/bin` symlinks; the scripts sync with the APK | kept (nothing calls them in desktop) |
| Plugin selection | `~/.config/omarchy/shell.json`: `bar.id = omamobile.bar`, `bar.quickSettings = omamobile.quicksettings`, four ids in `plugins[]` | `omdroid-ui.sh` mobile, surgical `jq` edit | `bar.id`/`bar.quickSettings` deleted and our four `plugins[]` entries dropped, each only while it still holds our value |
| Touch theme | `~/.config/omarchy/shell.toml`: `[bar] size-horizontal = 44`, `[bar] scale-with-font = false`, `[font] base-size = 16`, `[spacing] control-height = 44` | `omdroid-ui.sh` mobile (key upsert) | those keys removed, each only while it still holds our value |
| Hyprland rules | one marked block appended to `~/.config/hypr/looknfeel.lua` | `omdroid-ui.sh` mobile | the block is stripped; the rest of the file is untouched |
| The switch | `~/.config/omdroid/ui` | never written by us | read only |

**Why the theme override lives in `~/.config/omarchy/shell.toml` and not in the theme.**
`Color.qml:232-247` reads exactly two files: `currentThemePath/shell.toml` (the generated
one) and `~/.config/omarchy/shell.toml` (the machine-level override), then merges with
**user keys winning** (`mergeShell`, `Color.qml:200-210`). The second is watched live
(`watchChanges: true`) and is where `omarchy display text size` writes `[font] base-size`
(`usr/share/omarchy/bin/omarchy-display-text-size:31,50-88`). The generated theme dir is
wiped on every theme change (`omarchy-theme-set:292` `rm -rf "$CURRENT_THEME_PATH"`), and
`shell.<section>.toml` files are merged into the generated `shell.toml` at theme-set time
(`omarchy-theme-set-templates:319-372`), not read at runtime — so anything written into the
theme dir would not survive a theme switch.

**Why these values.** `[font] base-size` is the rem root: every `Style.font.*` derives from
it (`Style.qml:321-341`), the spacing scale follows it by default
(`effectiveSpacingScale`, `Style.qml:211`), so 12 → 16 grows type and padding together.
`[bar] size-horizontal` with `scale-with-font = false` gives exactly 44 logical px rather
than 44 × 16/12 = 59 (`barToken`, `Style.qml:296-302`). An explicit `[spacing]` override is
**not** scaled (`spacingToken`, `Style.qml:225-229`), so `control-height = 44` is 44.

**Bar option selection** is `shell.json`'s `bar.id`: `PluginRegistry.isEnabled` picks the
bar whose id equals `bar.id`, defaulting to `omarchy.bar` when absent
(`PluginRegistry.qml:114-140`), and `shell.qml:226-234` hands the whole `bar` object to the
bar as `barConfig` — which is how `quickSettings` and `clockFormat` reach `omamobile.bar`.

**Ordering.** `omarchy-plugin-index.sh` runs once per session, before cage and Hyprland
(`start.sh`, the line after the new call), into `$XDG_RUNTIME_DIR/omarchy-plugin-scan.txt`,
and `SessionPrep.kt` wipes that runtime dir before every session. `omdroid-ui.sh` therefore
runs one line earlier, so the symlinks exist when the index is built. The index script itself
needed no change: its third-party glob `"$home/.config/omarchy/plugins"/*/manifest.json`
follows symlinks (proved in U5).

## U2. What the five plugins need, and where the guest provides it

Every import in all five trees: `QtQuick`, `Quickshell`, `Quickshell.Io`,
`Quickshell.Wayland`, `Quickshell.Hyprland`, `Quickshell.Networking`, `Quickshell.Bluetooth`,
`Quickshell.Services.UPower`, `Quickshell.Services.Mpris`, `Quickshell.Services.Pipewire`,
`Qt.labs.folderlistmodel`, `qs.Commons`, `qs.Ui`, `qs.services`. Module presence checked
against the image: `usr/lib/qt6/qml/Quickshell/{,Io,Wayland,Hyprland,Networking,Bluetooth,
Services/{UPower,Mpris,Pipewire}}`, `Qt/labs/folderlistmodel`, and the shell's own
`usr/share/omarchy/shell/{Commons,Ui,services}`. The types that the qmltypes file does not
list (registered in the binary) were checked in `usr/bin/quickshell` strings:
`HyprlandToplevel`, `refreshToplevels`, `toplevels`, `focusedWorkspace`, `ToplevelManager`,
`NotificationServer`.

| Plugin | External things it uses | Guest provides it? |
|---|---|---|
| `omamobile.bar` (830 lines) | `Networking.devices/wifiEnabled`, `DeviceType`, `Bluetooth` via `StatusModel.js`; `UPower.displayDevice` (`BatteryIndicator.qml`); `shell.firstPartyServiceFor("omarchy.notifications")`; `SystemClock`; processes `omamobile-browser-setup`, `omamobile-cell-watch`, `omamobile-call-watch --observe`; `omaphone --in-call` on a call-chip tap | QML types present. `firstPartyServiceFor` = `shell.qml:291`. No NetworkManager/BlueZ/UPower daemon → the icons fall to "off"/hidden (no crash). The three processes: **stubs added**; `omaphone` is tap-only and simply does nothing. |
| `omamobile.quicksettings` (6,678 lines) | `Qs` IPC to the shell (`qs ipc -p $shellDir call notifications …`); `omarchy-shell`, `omarchy-theme-switcher`, `omarchy-capture-screenshot`, `omarchy-menu`, `brightnessctl`, `rfkill`, `busctl`, `wpctl`, `hyprctl`; `tile-state.sh` / `tile-action.sh` shipped in the plugin; `omamobile-gnss`, `omamobile-fp-enroll`, `omamobile-bt-agent`, `omamobile-record`, `omamobile-wifi`, `omamobile-bluetooth` | All the Omarchy helpers are in `usr/share/omarchy/bin` (on PATH: `envs.lua:31-36` puts `$OMARCHY_PATH/bin` first). `qs` = `/usr/bin/qs`. `busctl`, `rfkill`, `wpctl`, `hyprctl` present. **`brightnessctl` is not in the image** → the brightness slider shows its own "No backlight". The `notifications` IPC target exists (guest `plugins/notifications/Service.qml:857-905`: `setDnd`, `isDnd`, `dndState`, `clear`, `dismissAll`, `showHistory`). The `omamobile-*` helpers are absent by design: their tiles/panels degrade (`"unavailable"`, `QuickSettings.qml:194,206,221`) or the `tile-state.sh` probe prints `none`. |
| `omamobile.launcher` (1,605 lines) | `qs.services as OmarchyServices` → `AppLibrary` + `AppSearch.js`; `omamobile-launch`; `omarchy-shell shell summon omamobile.switcher`, `omarchy-shell lock isLocked`; `qs ipc … call omamobile.home/keyboard/voice`; `~/.config/omarchy/defaults/agent` | `AppLibrary.qml`/`AppSearch.js` present in `shell/services/`; `omamobile-launch` **ported**; `lock` IPC target = `plugins/lock/Service.qml:529`; the `omamobile.home/keyboard/voice` IPC calls are no-ops (those plugins are not ported) and the code treats them as best-effort; the agent file is absent → the prompt half hides itself (`hasAgent` false). |
| `omamobile.back` (446 lines) | `hyprctl`, `jq`, `wtype -k Escape`, the Hyprland Lua dispatcher fallback, `omamobile-home`, `fbcli` | All present (`/usr/bin/{hyprctl,jq,wtype}`), `omamobile-home` **ported**; `fbcli` guarded by `command -v` and simply skipped. |
| `omamobile.switcher` (815 lines) | `Quickshell.Hyprland` toplevels + `hyprctl eval` dispatches; `omamobile-launch show-with/own-screen`; one `qs ipc` to `omamobile.home` | Present; `omamobile-launch` ported. The `omamobile.home` call is a no-op. |

Two facts that bound the blast radius on the device:

- **A bar option that fails to load falls back to the stock bar.**
  `shell.qml:261-270` loads `entryPoints.bar` of the selected bar and, on error, logs
  `bar option … failed to load, falling back to omarchy.bar` and deselects it. So a broken
  `omamobile.bar` costs the phone bar, not the session.
- **`import qs.services as OmarchyServices` (launcher only) is the one import with no
  precedent in the guest tree**: the shell itself only imports `qs.Commons` and `qs.Ui`.
  A directory import without a `qmldir` gives each `.qml` file in it as a type, so
  `OmarchyServices.AppLibrary` should resolve to `shell/services/AppLibrary.qml`; if it does
  not, the launcher panel fails to load (the shell logs `panel plugin omamobile.launcher
  failed to load`) and the other four plugins are unaffected.

**Local changes to upstream: none.** The two frictions the research predicted were both
avoided rather than patched:

1. `omamobile-launch` starts apps as `uwsm-app -- gtk-launch <id>`. The image already ships
   `/usr/local/bin/uwsm-app` (Omarchy-Android's own shim: with `OMARCHY_PROOT=1` it drops the
   `--` and execs the rest). No shim added; `gtk-launch` and `python3` are both in the image.
2. `inotifywait` was only needed by `omamobile.home`, which is not ported.

**Stubs added** (`/etc/phoshdroid/omamobile/bin/`, each a 6-line script named like the
upstream tool so a later round can drop the real one in):

| Stub | Upstream job | Why stubbed |
|---|---|---|
| `omamobile-browser-setup` | fit a phone browser window | no browser profile to fit; the bar runs it at every load, so it must succeed silently |
| `omamobile-cell-watch` | stream ModemManager state to the bar | no modem, no ModemManager in proot; prints nothing so no carrier icon is claimed |
| `omamobile-call-watch` | watch omatel's agent for a call | no modem, no `omatel-agent`, no systemd user unit |

## U3. Session wiring

`start.sh` gained one line (and a six-line comment) immediately before the index:

```bash
# UI mode for this session: mobile ... or the stock desktop. ...
bash /etc/phoshdroid/omdroid-ui.sh

# Build the shell plugin index for this session. ...
bash /etc/phoshdroid/omarchy-plugin-index.sh
```

`omdroid-ui.sh` (new, `rootfs/overlay/etc/phoshdroid/omdroid-ui.sh`, `bash -n` clean):

- reads `~/.config/omdroid/ui`; missing, empty or unrecognised means `mobile` (an unknown
  value is logged and treated as mobile);
- mobile: theme key upsert, `shell.json` surgical edit, Hyprland marked block, plugin
  symlinks, helper symlinks;
- desktop: the same list undone, then the plugin symlinks removed;
- every action logs `omdroid-ui: …`, which lands in `/tmp/omarchy-session.log` because
  `start.sh` redirects the session there.

**No-clobber rule, per file** (this is the whole rule; nothing else is written):

| File | What we write | When we refuse |
|---|---|---|
| `~/.config/omarchy/shell.toml` | four keys, upserted line-by-line | a key that already holds a value other than ours is left alone and logged (`… is not ours; leaving it`). desktop removes only keys we created and only while they still hold our value. |
| `~/.config/omarchy/shell.json` | `bar.id`, `bar.quickSettings`, four `plugins[]` ids, with `jq` (the same tool Omarchy's own `omarchy-bar` uses) | desktop restores `bar.id`/`bar.quickSettings` only while they still equal our values, and drops only our four plugin ids; every other key (idle timers, bar layout, a user's own plugins) is untouched. |
| `~/.config/hypr/looknfeel.lua` | one appended marked block (`-- >>> omdroid mobile ui >>>` … `-- <<< omdroid mobile ui <<<`) | existing lines are never rewritten; desktop removes exactly the block. |
| `~/.config/omarchy/plugins/omamobile.*` | symlinks | a real directory at that path is kept and logged |
| `/usr/local/bin/omamobile-*` | symlinks (also created by the packager) | an existing non-symlink is kept and logged |

## U4. Packaging

- `rootfs/package-omarchy-rootfs.sh`: copies `omdroid-ui.sh` and the whole `omamobile/` tree,
  `chmod 755` on the five helpers, and creates the `/usr/local/bin` symlinks.
- `app/build.gradle.kts` `syncGuestOverlay`: `include("omdroid-ui.sh")` and
  `include("omamobile/**")` added beside the existing list, so an APK update refreshes the
  plugin trees in an existing install (the `/usr/local/bin` symlinks point into
  `/etc/phoshdroid`, so they follow).
- Gate, run in the foreground:
  `./gradlew :app:mergeDebugAssets :app:test --console=plain` →
  **BUILD SUCCESSFUL in 1m 6s** (190 tasks).
- `python3 docs/omarchy/tools/unit-count.py` → **`unit tests 63 failed 0`**.
- `find app/build -path '*guest-overlay*omamobile*' -type f | wc -l` → **141**, which is 47 × 3:
  the generated tree plus the debug and release `mergeAssets` copies:
  ```
   47 app/build/generated/guestOverlay/guest-overlay/etc/phoshdroid
   47 app/build/intermediates/assets/debug/mergeDebugAssets/guest-overlay/etc/phoshdroid
   47 app/build/intermediates/assets/release/mergeReleaseAssets/guest-overlay/etc/phoshdroid
  ```
  **47 = 42 upstream files + 3 stub helpers + `SOURCE.md` + `LICENSE`** — the vendored count
  plus our own, as the brief asks. `assembleDebug` was not run and `app/build/outputs/apk/`
  was not touched.

## U5. Dry run without the device

Scratch tree: `<scratch>/omarchy/r5/mobile-ui/root` (extracted from
`rootfs.bin`: `./home`, `./etc/phoshdroid`, `./usr/share/omarchy`,
`./usr/lib/qt6/qml/Quickshell`, `./usr/local/bin/uwsm-app`, `./usr/bin/{quickshell,qs}`).
Driver: `<scratch>/omarchy/r5/mobile-ui/dryrun.sh`, full log beside it in
`dryrun.out`. The script under test is pointed at that tree with `OMDROID_ROOT`, the packager
step is simulated by copying `omdroid-ui.sh` and `omamobile/` into `root/etc/phoshdroid/`.

Baseline: `shell.toml` absent (stock), mode file absent, 0 plugin links.

**Start 1 — first start, mobile:**

```
omdroid-ui: mode mobile (…/.config/omdroid/ui)
omdroid-ui: shell.toml: mobile sizes applied
omdroid-ui: shell.json: bar.id=omamobile.bar, four panels enabled
omdroid-ui: looknfeel.lua: mobile rules in place
omdroid-ui: linked omamobile.bar … (5 plugins)
--- state: after start 1
  shell.toml: a0c4676ec96c76be
  shell.json: 763c589bac7ad22d
  looknfeel:  f8a27d1b32f836b8
  links:      5 plugin links, 5 helper links
```

`shell.toml` after start 1, and the semantic diff of `shell.json` against the stock file —
three changes, nothing else:

```
[bar]                     --- shell.json.baseline
size-horizontal = 44      +++ shell.json
scale-with-font = false   +    "id": "omamobile.bar",
                          +    "quickSettings": "omamobile.quicksettings",
[font]                    -  "plugins": [],
base-size = 16            +  "plugins": [ {omamobile.back}, {omamobile.launcher},
                          +               {omamobile.quicksettings}, {omamobile.switcher} ]
[spacing]                 (idle.screensaver 150, idle.lock 300 and the whole bar.layout
control-height = 44        unchanged)
```

`python3 -c tomllib` on that file: **`shell.toml: parses, values match`** — the four keys and
nothing else.

**Start 2 — idempotent:** the three hashes are byte-identical to start 1
(`a0c4676e…`, `763c589b…`, `f8a27d1b…`), so a second start rewrites nothing.

**Start 3 — user edits:** `base-size` 16 → 18 in `shell.toml`, `idle.screensaver` 150 → 900
in `shell.json`, then start again:

```
omdroid-ui: shell.toml: [font] base-size = 18 is not ours; leaving it
…
[font]
base-size = 18
```

**Start 4 — the switch (`printf 'desktop\n' > ~/.config/omdroid/ui`):**

```
omdroid-ui: mode desktop (…)
omdroid-ui: shell.toml: mobile sizes removed
omdroid-ui: shell.json: stock bar and plugin list restored
omdroid-ui: looknfeel.lua: mobile rules removed
omdroid-ui: unlinked omamobile.bar … (5 plugins)
--- state: after start 4 (desktop)
  shell.toml: 9244995213c63aa2   (only the user's [font] base-size = 18 is left)
  shell.json: b4c6f80fd6103f81
  looknfeel:  d36d5ae6fe6a3b57   (= the baseline hash)
  links:      0 plugin links
--- looknfeel after desktop is byte-identical to the baseline
  identical
--- shell.json after desktop: only the user's own edit differs from stock
-    "screensaver": 150
+    "screensaver": 900
```

**Start 5 — back to mobile:** `bar.id`, `quickSettings` and the four plugin links return, and
the user's `base-size = 18` is still theirs (`[font] base-size = 18 is not ours; leaving it`);
the hash is a new one (`108585a4…`) exactly because of that retained user value.

**Plugin index against that tree** (`HOME`/`OMARCHY_PATH`/`XDG_RUNTIME_DIR` pointed at the
scratch root, so the real script runs unmodified):

```
scan file: …/root/run/omarchy-plugin-scan.txt (84 headers)
893:===thirdparty::…/plugins/omamobile.back===
910:===thirdparty::…/plugins/omamobile.bar===
926:===thirdparty::…/plugins/omamobile.launcher===
967:===thirdparty::…/plugins/omamobile.quicksettings===
984:===thirdparty::…/plugins/omamobile.switcher===
manifests parsed: all five report "id": "omamobile.<name>"
shell.json: valid JSON
```

## What Phil will see (1600×985 logical, stock scale 2 at the 3200×1971 root)

- **Bar**: one 44 px strip across the top — clock and unread count at the left, DND / wi-fi /
  battery at the right, the middle left empty (that is the phone camera-cutout gap; the
  tablet has no cutout to fill it). The whole strip is one target: a tap or a pull-down opens
  quick settings.
- **Pull-down**: the quick-settings sheet, four tiles collapsed, expandable to pages of 44 px
  toggles; brightness and volume sliders; a media card when something publishes MPRIS; the
  shell's notification history. Tiles with no backend say so instead of lying (see Stubs).
- **Launcher**: on an empty workspace, a dock strip along the bottom; tap it for the drawer
  (search row, 4-column app grid, agent row when an agent is configured), swipe up for recent
  apps. Over an app, a 44 px pill at the bottom that brings the drawer back.
- **Back**: a 14 px strip at each screen edge; drag inward past 56 px sends Escape to the
  focused window (or goes home when the focused app is one of Omamobile's terminals list).
  Android's own back-gesture edge may claim the outermost pixels — the device phase must
  measure that.
- **Switcher**: swipe up on the dock for open windows as cards; tap to switch, flick up to
  close, hold for the show-with / own-screen actions.
- **Windows**: no gaps, no borders, fully opaque, dialogs centred and capped to the monitor.
- **Type and controls**: 16 px base type, 44 px control rows (stock: 12 px / 28 px).

## Stubs (what shows "unavailable", and why)

| Surface | What it reads | State here |
|---|---|---|
| Wi-Fi tile, Wi-Fi panel, bar wi-fi icon | `Quickshell.Networking` → NetworkManager | no NetworkManager package in the image → tile answers `unavailable` (`QuickSettings.qml:206`), icon falls to "off" |
| Bluetooth tile, Bluetooth panel, bar BT icon | `Quickshell.Bluetooth` → BlueZ | only `bluez-libs`, no daemon → `unavailable` (`QuickSettings.qml:194`) |
| Mobile data / hotspot / airplane | `tile-state.sh` probes `nmcli`, ModemManager markers | probe prints `none`; no `nmcli` in the image |
| Battery (bar icon, battery-saver tile) | `UPower.displayDevice` | `upower` package present but no system bus daemon in proot → null device, icon hidden |
| Brightness slider | `brightnessctl` | not in the image → the row's own "No backlight" |
| Torch, NFC, location, fingerprint, keyboard, dictation, screen record | `omamobile-*` helpers / hardware | helper absent; those tiles are dimmed or say unavailable; dictation prints `none` from `tile-state.sh` |
| Notification DND + history | the shell's `notifications` IPC target | present and functional (`plugins/notifications/Service.qml:857-905`) |
| Volume, media, dark theme, night light, rotation, screenshot, stay awake, clipboard | `wpctl`, MPRIS, `omarchy-theme-switcher`, `hyprsunset`, `hyprctl`, `omarchy-capture-screenshot` | all present; these are the tiles that work |
| Call chip, carrier icon | `omamobile-call-watch`, `omamobile-cell-watch` | stubs print nothing → no chip, no carrier icon |

## The switch

```bash
mkdir -p ~/.config/omdroid && echo desktop > ~/.config/omdroid/ui   # stock session next start
echo mobile > ~/.config/omdroid/ui                                   # phone UI next start
rm ~/.config/omdroid/ui                                              # same as mobile
```

It is read at every session start, before the shell, so it takes effect on the next start
(not live). `desktop` is the escape hatch: stock bar, stock sizes, stock gaps.

## Files

New:

- `rootfs/overlay/etc/phoshdroid/omdroid-ui.sh` (13.4 KB) — the mode installer
- `rootfs/overlay/etc/phoshdroid/omamobile/` — 47 files, 504 KB:
  - `LICENSE`, `SOURCE.md`
  - `plugins/omamobile.{bar,quicksettings,launcher,back,switcher}/` — 40 files, byte-identical to `b5baaea`
  - `bin/omamobile-launch` (19 KB), `bin/omamobile-home` (1.5 KB) — byte-identical to `b5baaea`
  - `bin/omamobile-{browser-setup,cell-watch,call-watch}` — Omdroid stubs

Changed:

- `rootfs/overlay/etc/phoshdroid/start.sh` — one call, before the plugin index
- `rootfs/package-omarchy-rootfs.sh` — overlay copies, `chmod`, `/usr/local/bin` symlinks
- `app/build.gradle.kts` — two `include(...)` lines in `syncGuestOverlay` + comment
- `docs/omarchy/r5-mobile-ui-report.md` — this file

Nothing under `app/src/**`, `termux-x11/**`, `rootfs/patches/**` or `rootfs/build-aquamarine.sh`
was touched, and no git command was run.

## What the device phase must check (with the evidence for each)

1. **The shell comes up at all, with five third-party plugins.** After a start:
   `grep -c '^===thirdparty' $XDG_RUNTIME_DIR/omarchy-plugin-scan.txt` = 5 on the device, and
   `/tmp/omarchy-session.log` shows the five `omdroid-ui: linked …` lines. Evidence: a
   screenshot of the bar, and `omarchy-shell shell listPlugins` naming all five.
2. **Nothing in the QML errored.** `grep -i 'panel plugin .* failed to load' /tmp/omarchy-shell.log`
   (or wherever the shell's stdout went) is empty; `qs log` shows no `TypeError` from
   `omamobile.*`. A failed plugin load is the one failure mode this round could not exercise.
3. **The bar is 44 px and the strip responds.** Tap the bar → quick settings sheet appears;
   screenshot with the sheet open. This is the piece with no helper binary behind it, so it is
   the cheapest proof the plugin API fit is right.
4. **The dock, the drawer and the pill.** On an empty workspace the dock is visible; tap →
   drawer with app icons; launch one app from the grid and confirm it lands (that exercises
   `omamobile-launch` → `uwsm-app` → `gtk-launch`). Over the app, the 44 px pill is back.
5. **Back gesture vs Android's edge gesture.** Drag from 20 px inside the left edge. Evidence:
   the focused app receives Escape (a terminal shows `^[` or the app goes back one level).
   If Android's gesture steals it, record the pixel width that works.
6. **Switcher.** Swipe up on the dock → cards for the open windows; tap one; flick one closed.
7. **The switch both ways.** `echo desktop > ~/.config/omdroid/ui`, restart, screenshot the
   stock bar; `diff` the guest's `~/.config/omarchy/shell.json` against its pre-mobile copy
   (`~/.local/state/omdroid/ui/` holds our records; the shell.json should have no
   `omamobile` ids) and confirm `hyprctl getoption general:gaps_in` is back to 5.
8. **Tiles that must not lie.** Open quick settings and read the tiles: Wi-Fi, Bluetooth,
   mobile data, hotspot, torch, NFC, fingerprint, location must say unavailable/dimmed, not
   "on". Screenshot the expanded page.
9. **Type size.** Compare a menu (SUPER+space) against the stock screenshot: 16 px base type,
   44 px rows. `omarchy display text size` should report 16 px.

## Not verified

- **No render, no device, no running shell.** Every visual claim above is read from the
  plugins' own code and the shell's style tokens; nothing was seen on screen. Whether the
  five plugins load without a QML error is U2's static check only (imports resolve, files
  parse) — the first real proof is device-phase item 2.
- **`import qs.services` (launcher) is the one unresolved import,** for the reason in U2: no
  other file in the guest tree uses that module path, so its resolution is inference from
  QML's directory-import rule rather than an observed load.
- **Whether Omamobile's API expectations match this exact Omarchy snapshot.** The research
  cited `PluginRegistry.qml`, `shell.qml` and `Color.qml`/`Style.qml` line by line and this
  round re-checked the same entry points (`bar.id` selection, `barConfig` injection,
  `firstPartyServiceFor`, the `notifications` and `lock` IPC targets), but no shell actually
  instantiated the plugins.
- **Touch.** Taps still arrive as mouse clicks until the aquamarine `wl_touch` patch lands.
  The plugins use `TapHandler`/`DragHandler`/`MouseArea` only, which accept all pointer
  devices, so nothing here depends on which of the two arrives.
- **`omamobile-launch` was not executed** (it needs a live Hyprland); its Hyprland calls
  (`hyprctl eval` with the Lua dispatcher, workspace rules) and the `uwsm-app` shim were
  checked by reading both, not by running them.
- **The theme pass was not seen.** 44/16/44 are the research's numbers, so this is a taste
  gate as much as a technical one; the switch makes it one command to undo.
