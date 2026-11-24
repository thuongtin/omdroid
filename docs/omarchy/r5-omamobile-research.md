# R5-OMAMOBILE: can Omamobile's phone shell make Omdroid's UI touch-friendly?

Read-only study of [derekross/omamobile](https://github.com/derekross/omamobile) at commit
`b5baaea` (shallow clone, 2026-11-24) against the Omarchy in Omdroid's guest, with what each part
needs at runtime and whether it can work on the tablet today. Every claim cites what was read:
`OM:` = the omamobile clone (`<scratch>/omarchy/r5/research/omamobile`), `BUNDLE:` =
the guest's Omarchy-Android extract (`<scratch>/omarchy/upstream/`), `ROOTFS:` = the
guest image's file list (`/tmp/omarchy-members.txt`, the v0.1.1 bundle's tar listing), or a URL
pinned to a tag/commit. Anything not read is marked **guess**.

**Verdict in one line:** Omamobile is not a UI library to import — it is 13 ordinary Omarchy shell
plugins, a phone `shell.json` and a patch series for a *newer* Omarchy than the guest runs. Five of
those plugins are pure QML with no phone hardware behind them and would work on the tablet today
under the current pointer emulation; the whole phone profile is only worth having after the
aquamarine `wl_touch` patch.

---

## 0. What the two things actually are

- **Omamobile's UI is `packages/omamobile-shell`** — 13 plugin directories, a `profile/shell.json`
  layout, one Hyprland rules file (`hypr/phone.lua`), squeekboard layouts and 29 helper binaries in
  `bin/`. Its own README states the design: *"Omarchy's phone profile for Omarchy's own shell. It
  isn't a fork: these are ordinary Omarchy shell plugins plus a phone `shell.json`, linked into the
  user's config by `omamobile-setup-user`"* (`OM:packages/omamobile-shell/README.md:3`), and
  `OM:plugins/README.md:5-8`: *"Nothing in Omarchy is patched: each directory here is a plugin with
  a `manifest.json`, discovered from `~/.config/omarchy/plugins/` … They draw with the shell's
  `qs.Commons` (Color, Style, Border) and `qs.Ui` components"*. That is exactly the third-party
  plugin surface Omdroid's guest already has (§2).
- **The rest of the repo is not UI**: kernels, modem, GNSS, camera, fingerprint HAL, Waydroid,
  installer (`OM:README.md:35-51`). `packages/omamobile-omarchy` is 31 patches against
  `/usr/share/omarchy` plus `omamobile-update` (`OM:packages/omamobile-omarchy/PKGBUILD:4,13`;
  `patches/*.patch` = 31 files, `legacy-4.0.6/*.patch` = 29).
- **Omdroid's shell is upstream Omarchy's Quickshell shell** out of the Omarchy-Android bundle:
  `BUNDLE:usr/share/omarchy/shell/{shell.qml,services,plugins,Commons,Ui}`. Third-party plugins are
  loaded from an index Omdroid builds at session start
  (`rootfs/overlay/etc/phoshdroid/omarchy-plugin-index.sh:44-57`, run from
  `rootfs/overlay/etc/phoshdroid/start.sh:63`): first-party from `$OMARCHY_PATH/shell/plugins`,
  third-party from `$HOME/.config/omarchy/plugins/*/manifest.json`. A third-party plugin is
  therefore a *drop-in directory*, not a package.

---

## 1. Inventory: what each piece does, what it needs, does it work in Omdroid today?

Runtime column sources: **QML** = permission handlers counted over each plugin's `*.qml` (this
table's counts are exact: `grep -o` per directory); **SVC** = a named D-Bus/daemon/hardware
service; **BIN** = an external binary; **API** = an Omarchy shell API generation.

What the guest image has and has not (`ROOTFS`, 556 packages in `var/lib/pacman/local/…`): it has
`quickshell 0.3.1-1`, `hyprland 0.56.1-3`, `aquamarine 0.14.0-2`, `qt6 6.11.2`, `upower 1.91.3-1`,
`pipewire 1.6.8` + `wireplumber 0.5.15`, `polkit 127`, `xdg-desktop-portal 1.22.1-2` + `-gtk
1.15.3`, `jq 1.8.2`, `wtype 0.4`, `rfkill`, `busctl`, `wpctl`, `grim`, `slurp`, `xprop`, `python3`.
It has **no** `NetworkManager`, **no** `bluez` (only `bluez-libs`), **no** `fprintd`, **no**
`squeekboard`, **no** `systemd` runtime (the package is installed, nothing runs as PID 1), **no**
sudo. Omarchy's own helpers are all there (`omarchy-capture-screenshot`, `omarchy-theme-switcher`,
`omarchy-menu`, `omarchy-bluetooth-power`, …).

| Piece (QML/JS lines) | What it does for the user | Needs | Works in Omdroid today? |
|---|---|---|---|
| `omamobile.bar` (830) | Full replacement bar: clock + unread count left, connectivity/DND/battery right, camera-cutout gap in the middle; the whole strip is one target that taps or pulls down into quick settings (`OM:omamobile.bar/Bar.qml:68,251-257`) | QML: `MouseArea` ×2, no `TapHandler`/`DragHandler` (it is a `PanelWindow` with `WlrLayershell.layer: WlrLayer.Top`, `exclusionMode: Auto` — `Bar.qml:300-303`); SVC: `Quickshell.Networking` (NetworkManager), `Quickshell.Bluetooth`, `UPower.displayDevice`; BIN: `omamobile-browser-setup` (`Bar.qml:35`), `omamobile-cell-watch` (`:105`) | **Partly.** Renders and answers a click, but its status row is empty: no NetworkManager, no BlueZ, and UPower cannot see the Android battery inside proot. Its two helper processes would fail at every start (harmless warnings, or stub them out). |
| `omamobile.quicksettings` (6678) | Pull-down sheet: up to 21 rearrangeable tiles, brightness/volume sliders, media card, notification history, Wi-Fi picker, Bluetooth panel | QML: `TapHandler` ×9, `DragHandler` ×2, `MouseArea` ×29; SVC: NetworkManager, BlueZ, UPower, MPRIS, PipeWire, notifications (a panel cannot reach DND directly — `OM:plugins/README.md` "Panel plugins cannot reach do-not-disturb"); BIN: `omarchy-shell`, `omarchy-theme-switcher`, `omarchy-capture-screenshot`, `omarchy-menu`, `rfkill`, `busctl`, `omamobile-gnss` (`QuickSettings.qml:1140-1148`), `omamobile-fp-enroll`, `omamobile-bt-agent` (`BluetoothPanel.qml:191`) | **Partly.** Renders and is tappable; tiles whose service is missing are dead (Wi-Fi, Bluetooth, mobile data, hotspot, torch, fingerprint, NFC). Brightness, volume, media, dark theme, night light, rotation and screenshot map onto things the guest really has (`wpctl`, `hyprctl`, Omarchy theme state, `omarchy-capture-screenshot`). |
| `omamobile.launcher` (1605) | The home bar: one input that searches apps, opens a 3–6 column app grid, and sends a prompt to Omarchy's default agent; over an app, a 44 px pill (double-tap = keyboard, hold = voice) | QML: `TapHandler` ×5, `DragHandler` ×4, `PointHandler` ×2, `MouseArea` ×3; API: `import qs.services as OmarchyServices` — it instantiates Omarchy's `AppLibrary` itself because third-party `menu` plugins lose their shell facade (`OM:plugins/README.md` "Third-party `menu` plugins lose their shell facade"); BIN: `omamobile-launch` (app/cmd/url), `omamobile-osk-watch` and `omarchy-shell lock isLocked` (`Launcher.qml:259,519,689`) | **Yes for search + grid + pill**, if the agent-prompt half is pointed at a command the guest has, `omamobile-launch` is ported with the `uwsm-app` shim (§3), and the keyboard half is dropped (no squeekboard). `AppLibrary.qml` + `AppSearch.js` are in the guest (`BUNDLE:usr/share/omarchy/shell/services/`). |
| `omamobile.home` (12803, 36 QML files) | Android-style home screens over the wallpaper: pages of app shortcuts and widgets, long-press edit mode (add/move/resize/remove), page management, OWL widget runtime + store | QML: `TapHandler` ×10, `DragHandler` ×6, `PointHandler` ×3, `MouseArea` ×27; API: `qs.Commons`/`qs.Ui`; a bottom layer surface (`Home.qml:1175-1178`, `WlrLayer.Bottom`); BIN: `omamobile-launch app <desktopId>` (`HomeModel.js:892-912`), `omamobile-widget` (`Home.qml:343`), `omarchy-hw-display` (`Home.qml:668`), `qs ipc`, and `inotifywait` to watch the widget directory (`Home.qml:350`) — **not in the guest image** (0 hits in `ROOTFS`); network for the weather widgets' Open-Meteo calls | **Partly, and it is the biggest item.** The interaction model is single-pointer and would work; it needs the wallpaper/desktop arrangement Omdroid does not currently run (apps are maximised), the OWL runtime (`OM:omamobile.home/owl/`) shipped with it, and either `inotify-tools` added or the widget hot-reload lost (non-fatal: the watch is one `Process`). |
| `omamobile.switcher` (815) | Recent apps as cards: swipe up from the dock, tap to switch, flick up to close, hold for split/own-screen | QML: `TapHandler` ×7, `DragHandler` ×1, `MouseArea` ×7; API: `Quickshell.Hyprland` toplevels (`Switcher.qml:161,199`) + `hyprctl` dispatch | **Yes.** Hyprland IPC is present (`hyprland 0.56.1`), and the gesture is one pointer dragged up. |
| `omamobile.back` (446) | Edge swipe → `Escape` to the focused window; at an app's top level it asks for home. Terminal windows get no Escape (mode-dependent), they go home | QML: `DragHandler` ×1 (56 logical px threshold, `BackModel.js:THRESHOLD`); overlay layer (`Back.qml:146-148`); BIN: `sh` + `hyprctl` + `jq` + `wtype -k Escape`, falling back to Hyprland's Lua dispatcher `hl.dsp.send_key_state({key="code:9"})` (`BackModel.js:ESCAPE_ARGV`); `omamobile-home` for the top-level case | **Yes, with one host caveat.** All the binaries exist in the image. The swipe must start inside the app's surface, and Android's own back gesture owns the screen edge — a few px in, or a gesture-exclusion request (**guess** — not tested). |
| `omamobile.keyboard` (635) | Show/hide the on-screen keyboard for the pill, the Hide key, the globe's language sheet | QML: `TapHandler` ×7; SVC: squeekboard's D-Bus `sm.puri.OSK0` `SetVisible` (`Keyboard.qml:170-171`), `omamobile-osk-watch` | **No.** No squeekboard in the image, and Omdroid already has a better keyboard: Android's own plus the Termux:X11 extra-key bar (`docs/omarchy/r4-input-research.md`). Drop, not port. |
| `omamobile.fingerprint` (1033) | Under-display fingerprint target during verification + enrollment flow | SVC: `fprintd` + the sensor; BIN: `omamobile-fp-enroll` | **No.** No fprintd, no sensor inside proot, and the surface is an under-*display* sensor. |
| `omamobile.call` (1173) | Incoming call over the lock, heads-up card, in-call controls | SVC: `omatel-agent` user unit + the modem (`omamobile-call-watch`) | **No.** No modem, no systemd, no `omatel-agent`. |
| `omamobile.mobilenetwork` (884) | Carrier/signal/registration, data, roaming, APN, SIM PIN | SVC: modem via `omamobile-mobile-network` | **No** — "No modem" is all it would ever say. |
| `omamobile.voice` (2111) | Hold-to-talk bar; dictation into the focused app or the agent, through Voxtype | SVC: Voxtype daemon, PipeWire source, whisper model; BIN: `omamobile-voice-preview`, `voxtype` | **No** as shipped. PipeWire is there, but nothing captures the Android microphone into the guest and Voxtype is not installed. |
| `omamobile.access` (405) | Replaces GTK's permission dialog with a bottom sheet ("Allow Camera to use the camera?") | SVC: an xdg-desktop-portal Access backend (`omamobile-portal-access`, D-Bus activated, its own `.portal` file) | **No.** Needs its own portal backend and D-Bus activation, and there is no camera. |
| `omamobile.update` (1118) | Omarchy's update as a phone sheet, with battery check and patch state | BIN: `omamobile-update` (needs `pacman`, `sudo`, the patch series) | **No.** No sudo, no systemd, and Omdroid does not upgrade its guest in place — the image is repacked. |
| `omamobile-settings` (52 files) | Native Qt Quick Settings app: display brightness/refresh, battery charge limit, About | SVC: sysfs backlight/charger, a systemd user unit for the charge limit | **Partly.** A normal Qt app, so it launches, but its pages drive sysfs and user units that do not exist here. Not a UI win. |
| `omamobile-owl-widgets` (24 files) | Store of OWL widgets for the home screen (Simon Schubert's MIT widget set, conformance-filtered) | API: the home plugin's OWL runtime; network for weather widgets | **Only with `omamobile.home`.** |
| `omamobile-apps` (8 files) | Meta-package: Maps/GeoClue, NFC, Camera, Loupe, Phone, Messages | SVC: geoclue/GPS, neard, libcamera, modem | **No** — hardware packages. (Loupe would run; not a shell topic.) |

**The portable set is `bar`, `quicksettings`, `launcher`, `back`, `switcher`: 10,374 lines of QML/JS**
that need only things the guest has (Hyprland IPC, `qs.Commons`, `qs.Ui`, `shell.summon`, `jq`,
`wtype`, `hyprctl`), if their status/tile halves are allowed to degrade and two shell-package
binaries (`omamobile-launch`, `omamobile-home`) are ported with them.

**The widgets inside `omamobile.home`** (all `OM:plugins/omamobile.home/*.qml`, the ones its edit
mode offers as built-ins):

- `ClockWidget` — clock/date in the bar's format; no service. **Works.**
- `BatteryWidget` — `Quickshell.Services.UPower`; inside proot UPower cannot see the Android
  battery, so it would read empty. **Degraded.**
- `MediaWidget` — `Quickshell.Services.Mpris`; works only when a player is publishing MPRIS (the
  guest runs PipeWire/WirePlumber but usually no player). **Degraded.**
- `NotesWidget` — a local note. **Works.**
- `WeatherWidget`, and the weather-based OWL widgets — Open-Meteo over `http()` (network reaches the
  host's stack in proot) and, for the OWL set, `~/.local/state/omamobile/weather.json` written by
  `omamobile-weather`. **Works with that helper ported, or without the OWL store.**
- `AgendaWidget` — `khal` calendar if installed, else an empty card (`AgendaWidget.qml:37`).
  **Empty unless `khal` is added.**
- `TogglesWidget` — Bluetooth/Networking tiles plus notification DND through `qs ipc`
  (`TogglesWidget.qml:56`). **Degraded** (same missing services as quick settings).
- `CommandWidget` — the output of a command the user configures, run as the user
  (`CommandWidget.qml:10-13,28`). **Works**, and is the reason a port must treat a user's
  `shell.json` as code.
- `UserWidgetCell` / `OwlCell` — the user's own QML or OWL widget, loaded by `omamobile-widget` and
  hot-reloaded with `inotifywait`. **Works if that helper and inotify-tools are shipped.**

---

## 2. Version fit: the guest is pre-4.5, Omamobile targets 4.5

**Guest Omarchy revision.** `BUNDLE:BlackFireAlex-omarchy-android-0f4cee8/manifest/components.lock:2`
pins `omarchy` to git `158e8cfb3a03f7b390e4213eaf15edcea0dfaa98`. That commit is dated
**2026-08-29** (GitHub API `repos/basecamp/omarchy/commits/158e8cfb…`), and
`compare/v4.5.0...158e8cfb` answers **`status: behind`, `ahead_by: 0`, `behind_by: 1218`** — the
guest's tree is an *ancestor* of v4.5.0, i.e. between `v4.0.0` (2026-08-14) and `v4.5.0`
(2026-11-05). Against `v4.0.6` (2026-10-19) it has **diverged**: 184 ahead, 158 behind (the 4.0.x
maintenance branch). The bundle carries no `usr/share/omarchy/version` file, so the commit is the
truth.

**Omamobile targets 4.5.** `OM:README.md:41`: *"phones run 4.5 and `patches/`, where fixes go, and
one still on 4.0.6 uses `legacy-4.0.6/`"*; `OM:packages/omamobile-omarchy/PKGBUILD:6` only says
`depends=('omarchy>=4.0.6' …)`. The 4.5 series is `OM:packages/omamobile-omarchy/patches/` (31
patches; `0003`'s header: *"Omarchy 4.5 port (from the 4.0.6 series): … 4.5's held-key guard
(`dropsAutoRepeat`) … 4.5's `idleMs`"*), and the legacy series is `legacy-4.0.6/` (29 patches).
**Neither series matches the guest's revision**: the guest is neither v4.0.6 nor v4.5.0 but the
master snapshot in between, and patches apply by context, not by range.

**What fits, concretely — read in the guest's shell and checked against the plugins' usage.**

| API the plugins use | Guest has it? | Evidence |
|---|---|---|
| `qs.Commons` singletons `Color`, `Style`, `Border`, `Util` | **Yes**, same tokens | `BUNDLE:usr/share/omarchy/shell/Commons/qmldir`; `Style.qml:231` (`spacing` object: `xxs…huge`, `controlHeight`, `controlPaddingX/Y`), `:321` (`font` object: `family`, `caption`, `body`, `title`, `display`, `displayLarge`), `:189-199` (`normalFill`, `pressedFillFor`, `selectedFillFor`, …), `Color.qml:19-23` (`foreground/background/accent/urgent/muted`), `:73-101` (`bar`, `popups`, `menu`). omamobile uses `Style.font` 505×, `Style.spacing` 317×, `Style.space` 133×, `Style.cornerRadius` 92×, `Style.gapsOut` 45×, `Color.accent` 146×, `Color.popups` 76× — all present. |
| `qs.Ui` component set | **Yes** | `BUNDLE:usr/share/omarchy/shell/Ui/qmldir` lists 32 types; the five portable plugins instantiate only `PanelSlider` ×2, `TextField` ×4 and `ToggleSwitch` ×2 from it. |
| Plugin manifests `schemaVersion: 1`, `kinds: panel / bar`, `keepLoaded` | **Yes** | `BUNDLE:usr/share/omarchy/shell/services/PluginRegistry.qml:44-60` validates exactly `schemaVersion`, `id`, `name`, `version`, `kinds`, `entryPoints`; `keepLoaded` honoured at `shell.qml:628-632`. |
| Enabling a third-party plugin from `shell.json` (`plugins[]`, `bar.id`, `disabledPlugins[]`) | **Yes** | `PluginRegistry.qml:114-151` ("Enabled = the plugin id is referenced somewhere in shell.json … `bar.id`, a layout entry … or a top-level entry in `plugins[]`"), `findEntryLocation` `:196-215`. The guest's own user config is `bar.layout` + `"plugins": []` (`BUNDLE:home/omarchy/.config/omarchy/shell.json:7-65`), so `omarchy.bar` is active until `bar.id` changes. |
| Panel host API `shell.summon / hide / toggle / isPluginOpen` + IPC verbs | **Yes** | `BUNDLE:usr/share/omarchy/shell/shell.qml:452,492,522,509`; IPC verbs `listPlugins`, `listShellConfig`, `debugBarGeometry`, `summon`, `hide`, `toggle`, `togglePanelAt`, `call` at `shell.qml:1014-1050`. omamobile uses `shell.summon` 16×, `shell.hide` 22×, `shell.toggle` 2×, `shell.appLibrary` 7×, `shell.firstPartyServiceFor` 2×, `shell.pluginRegistry` 1×; all of those exist (`shell.qml:452,492,522,32,291,30`). |
| Panel injection (`omarchyPath`, `shell`, `manifest`, `barWidgetRegistry`, `pluginRegistry`, `service`) | **Yes**, verbatim | `shell.qml:645-655` sets exactly those if the plugin declares them; omamobile's panels declare `omarchyPath`/`shell`/`manifest`/`pluginRegistry`/`service`. |
| Bar option injection (`omarchyPath`, `shell`, `manifest`, `barWidgetRegistry`, `pluginRegistry`, `barConfig`) | **Yes** | `shell.qml:226-234` (`configureBar`), `barConfig` at `:127`; `OM:omamobile.bar/Bar.qml:23-28` declares exactly these. |
| **`omarchy.capabilities`** (first-party-only capability stamping, e.g. `authentication` for the lock) | **No** | 0 hits in `BUNDLE:usr/share/omarchy/shell`; omamobile documents it as the reason there is no `lockpad` plugin (`OM:plugins/README.md` "Lock screen PIN pad"). The guest's shell predates it — relevant only if a port wanted to touch the lock. |
| **`manifestHasKind` / facade pruning** | **No** | 0 hits in the guest shell. omamobile's workaround (its launcher instantiating `AppLibrary` itself) is harmless either way; nothing *requires* the new hook. |
| `bar.quickSettings` as a host feature | **Not needed** | The bar reads its own `barConfig.quickSettings` and calls `shell.summon` (`OM:omamobile.bar/Bar.qml:68,251`); nothing host-side. |
| `qs.services.AppLibrary` (launcher) | **Yes** | `BUNDLE:usr/share/omarchy/shell/services/AppLibrary.qml` + `AppSearch.js`. |
| `Quickshell` modules `Io/Wayland/Hyprland/Networking/Bluetooth/Services.*` | Modules yes (quickshell 0.3.1), **services behind** `Networking`/`Bluetooth`/`UPower`/`Mpris` are what is missing | `ROOTFS:var/lib/pacman/local/quickshell-0.3.1-1`; no NetworkManager/bluez in the package DB. |

**Mismatches to name, not hand-wave:**

1. **The lock/touch patches are written against 4.5 internals that do not exist here**:
   `dropsAutoRepeat`, the lock's `idleMs`, the lock's i18n "Enter Password" placeholder
   (`OM:packages/omamobile-omarchy/patches/0003-…patch:1-13`). Porting any of them means
   re-deriving each hunk against `BUNDLE:usr/share/omarchy/shell/plugins/lock/` at `158e8cfb`.
2. **`omamobile-omarchy`'s machinery is systemd-shaped**: a libalpm hook that re-applies the series
   after every Omarchy upgrade, `.service`/`.timer` units, `zram-generator`, `sudo`
   (`OM:packages/omamobile-omarchy/PKGBUILD:6`, `install:14-24`). None of that can run in proot.
   In Omdroid the series would be applied **at image build time** by the packager, or not at all.
3. **The `shell.json` shape matches** — `bar.layout.{left,center,right}` + `centerAnchor`
   (`BUNDLE:home/omarchy/.config/omarchy/shell.json:7-60`; `PluginRegistry.qml:167-195`) — and
   `omamobile.bar` deliberately ignores it (empty `layout` in `OM:profile/shell.json:10-14`) because
   a phone bar is one strip.
4. **Scale/geometry**: Omamobile assumes a 480×1040 logical phone at scale 3 and ≥44 logical px
   targets (`OM:plugins/README.md:14`). Omdroid's root is 3200×1971 physical at scale 2 → 1600×985
   logical (`docs/omarchy/r4-touch-report.md:13` measured an `omarchy-menu` layer at 1600×985). The
   plugins scale through `Style.font`/`Style.spacing`, so they will *fit*, but a 44 px bar across
   1600 px of landscape is a thin strip: usable, not phone-like.

---

## 3. How it would get in (the mechanism, exactly)

**Route: an overlay directory in the APK, not pacman packages.** The packager installs
`rootfs/overlay/…` into the image (`rootfs/package-omarchy-rootfs.sh:70-77`), the APK syncs the
same files into the guest on every start (`app/build.gradle.kts` `syncGuestOverlay`), and the
shell's plugin index already reads third-party manifests from the user config
(`omarchy-plugin-index.sh:54-57`). So the port is: copy plugin directories to
`~/.config/omarchy/plugins/omamobile.*` (or into `/usr/share/omamobile/shell/plugins` with
symlinks, as `omamobile-setup-user` does — `OM:bin/omamobile-setup-user:41-45`), edit
`~/.config/omarchy/shell.json`, add one Hyprland rules file. No pacman, no systemd, no sudo.

**One ordering detail that would bite:** the index is written **once per session**, before cage and
Hyprland start (`start.sh:63`), into `$XDG_RUNTIME_DIR`, which `SessionPrep` wipes before every
session (`SessionPrep.kt:18` on `tmp/omarchy-runtime`). So plugins must be in place before the
index runs — i.e. baked into the overlay or copied in by `syncGuestOverlay`, not dropped in while a
session is live. A shell restart alone does not rescan.

| What | Where it would live | Touched by |
|---|---|---|
| The 5 portable plugins | `rootfs/overlay/etc/phoshdroid/omamobile/plugins/omamobile.{bar,quicksettings,launcher,back,switcher}/` (a new overlay dir, copied into `~/.config/omarchy/plugins/` at start) | packager + `syncGuestOverlay` (+ a line in `start.sh` before the index) |
| Their helper binaries | `omamobile-launch` and `omamobile-home` (and stubs for `omamobile-cell-watch`, `omamobile-browser-setup`, `omamobile-bt-agent`, `omamobile-osk-watch`) into the guest PATH | overlay |
| `shell.json` phone layout | `rootfs/overlay/home/omarchy/.config/omarchy/shell.json` (or a merge step before the shell starts) | overlay |
| Hyprland rules (gaps, maximise, no opacity, modal sizing) | `~/.config/hypr/looknfeel.lua` `dofile(...)` of an `omamobile-phone.lua` (`OM:bin/omamobile-setup-user:300-308`), or an Omarchy default-hypr overlay | overlay |
| Lock/notification patches (optional) | baked into the image at repack time, from `OM:patches/` re-based onto `158e8cfb` | `package-omarchy-rootfs.sh` |

**`omamobile-omarchy`'s patches: which ones Omdroid would actually want.** They fix Omarchy's *own*
surfaces, not the phone plugins, and each is small. Relevant on a touch-first tablet: `0003` lock
number pad, `0011` PIN/password choice, `0015` inline notification reply, `0017` swipe-to-dismiss
notifications, `0018` menu back button + swipe-right, `0023` lock glance view, `0029`
double-tap-to-wake. **None is required for the five portable plugins to load**; they are the
difference between "the phone plugins look like a phone" and "the underlying Omarchy surfaces still
behave like a desktop". Omdroid does not need `0001` (first-run keybindings), `0012`
(`omamobile-update`), `0016` (pacman), `0021`/`0032` (sleep/idle), `0031` (units) at all.

**Hyprland config the phone profile changes** (`OM:packages/omamobile-shell/hypr/phone.lua`), and
what it would mean here: drop Omarchy's floating tag and maximise everything (`:9-11`), zero gaps
and borders (`:19-21`), opacity 1 (`:25-27`), `misc:exit_window_retains_fullscreen` (`:31-33`),
modal dialogs centred and capped to the monitor (`:35-41`), one window per workspace via
`omamobile-launch`'s per-launch exec rules. **Monitor/scale is not in `phone.lua` at all** — the
phone's scale is written into `~/.config/hypr/monitors.lua` by `omamobile-setup-user:180-195`
(`omarchy_monitor_scale = 3`, and `omarchy_gdk_scale` raised to match because X11 GTK apps drew at
two thirds size) and the pointer is hidden with
`hl.config({ cursor = { invisible = true, hide_on_touch = true } })` (`:203-210`). Omdroid already
derives its own scale from the X root at 2 (`UiScale.kt`, `start.sh`), so of that block only the
cursor hiding and the GDK-scale match are worth taking. On the tablet maximising is already what
works (the r4 harness measured a 1600×985 layer), so only the gaps/opacity/modal rules are worth
taking; the "one app per screen" rule is a UX decision, not a technical one.

**Two porting frictions found in the helper binaries, both small.** (i) `omamobile-launch` starts apps
as `uwsm-app -- gtk-launch <id>.desktop` (`OM:bin/omamobile-launch:357`) and commands through the same
wrapper for a systemd scope (`:361-377`). The command path already degrades when `uwsm-app` is not on
`PATH` (`:372-377` returns the argv unchanged) but the app path does not, so the grid would fail to
launch anything. Fix with a three-line `uwsm-app` shim in the overlay PATH that drops a leading `--`
and execs the rest: then both paths work unchanged, with no edit to omamobile's script. (ii)
`omamobile.home` watches its widget directory with `inotifywait` (`Home.qml:350`), which the image
does not have — either add `inotify-tools` or accept that user-widget edits need a shell restart.
`omamobile-launch` also drives Hyprland through `hyprctl eval` with the Lua form
`hl.exec_cmd(cmd, { workspace = "empty" })` (`OM:bin/omamobile-launch:108,178-181`); Hyprland 0.56.1
has that (`src/debug/HyprCtl.cpp:1112-1140`, `registerCommand(… "eval" …)` at `:2042`) and the guest
already runs a Lua config (`BUNDLE:home/omarchy/.config/hypr/hyprland.lua`), so that part fits as-is.

**Mind proot:** no systemd units (so `omamobile-setup-user.service`, `omamobile-osk-guard`,
`omamobile-doubletap`, `omamobile-sleepd`, the portal backend and the `omatel-agent` unit are all
unavailable), no sudo (`omamobile-update`), no hardware (modem, sensors, fingerprint, torch), and
`omamobile-setup-user` also rewrites `~/.config/hypr/monitors.lua`'s `omarchy_monitor_scale`
(`:187-195`) — in Omdroid that value is derived from the X root (`start.sh`, `UiScale.kt`), so that
step must be replaced, not copied.

**Licence/attribution a port must keep:** omamobile is MIT and every file carries an SPDX header
(`OM:README.md:66`); `omamobile-omarchy` ships `LICENSE.omarchy` for the patched Omarchy text
(`OM:packages/omamobile-omarchy/install`). The squeekboard layouts are **GPL-3.0-or-later**
(`OM:packages/omamobile-shell/README.md:13`) — do not vendor those into an MIT-only tree. The OWL
widget set and its guide are Simon Schubert's MIT, attributed in the files
(`OM:plugins/README.md:11`, `widgets/LICENSE-owl-guide`).

---

## 4. The touch question, settled

**Today's tablet delivers mouse events, not touch.** The nested Hyprland has no touch device:
aquamarine 0.14.0's Wayland backend has **0** occurrences of `touch` in `src/backend/Wayland.cpp`
(878 lines) and `include/aquamarine/backend/Wayland.hpp` (197 lines) declares no `CWaylandTouch`
(both read at tag `v0.14.0`; the same finding, with the device evidence, is in
`docs/omarchy/r4-touch-research.md:51-62` and `r4-touch-report.md:14`). Hyprland's only ingress is
`events.newTouch` (`Hyprland v0.56.1 src/Compositor.cpp:478-480` → `CInputManager::newTouchDevice`,
`src/managers/input/InputManager.cpp:1938`), so no `CTouchDevice` is ever created and `hyprctl -j
devices` answers `touch: []`. The current build sends the finger as a **pointer**
(`app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt:552` sets `touchMode=2`, simulated
touch), so:

| Piece | Under pointer emulation | Why |
|---|---|---|
| `omamobile.bar` tap / pull-down | **Works** | `MouseArea` ×2 in `Bar.qml` (the pull-to-open at `:251-257`); Qt's pointer handlers accept `PointerDevice.AllDevices` by default (`qtdeclarative v6.11.2 src/quick/handlers/qquickpointerdevicehandler.cpp:99-104`), and `TapHandler` accepts all buttons (`qquicktaphandler.cpp:133,517`). |
| `omamobile.quicksettings` tiles, sliders | **Works** | `TapHandler` ×9 + `DragHandler` ×2 — single-pointer both. |
| `omamobile.launcher` search, grid, pill tap/long-press | **Works** | `TapHandler` ×5, `DragHandler` ×4, `PointHandler` ×2, `MouseArea` ×3. |
| `omamobile.switcher` swipe-up, card flick | **Works** | One-pointer drag; there is no `PinchHandler` and no `MultiPointTouchArea` anywhere in the plugins (0 and 0 over all 13). |
| `omamobile.back` edge swipe | **Works, with a host caveat** | The `DragHandler` starts inside the app's surface; Android's own back gesture owns the physical edge, so the swipe must start a few px in or the shell must declare gesture exclusion (not measured; **guess** on the exclusion API). |
| `omamobile.keyboard` / squeekboard | **Dead** | squeekboard is a Wayland client that needs the compositor's virtual-keyboard/text-input paths and touch for its own keys; not installed, and superseded by Android's keyboard. |
| Two-finger anything (scroll, pinch, two-finger tap) | **Dead** | Emulation maps a second finger to scroll/right-click at the app level, never to multi-point `wl_touch`. None of the plugins uses it; Omarchy's desktop surfaces do. |
| Hyprland touch gestures (`gestures:workspace_swipe_touch`) | **Dead** | Hyprland's touch-gesture path needs a `CTouchDevice`; the option is `false` by default anyway (`r4-touch-report.md:80-81`). |

So **the five portable plugins are usable today**; nothing in them consumes `wl_touch` by name —
they are written device-agnostically, which is exactly why pointer emulation carries them. What
genuinely needs the real fix is everything *around* them: the lock keypad's feel, notification
swipe-dismiss, double-tap-to-wake, kinetic flicks in Qt views, and any surface that leans on
touch-specific behaviour.

**What adding `wl_touch` to aquamarine's Wayland backend takes.** `CWaylandPointer`
(`aquamarine v0.14.0 src/backend/Wayland.cpp:272-344`; declared
`include/aquamarine/backend/Wayland.hpp:111-124`) is the exact template: it is created in
`initSeat()` off `wl_seat.setCapabilities` (`Wayland.cpp:348-367` — `HAS_POINTER` creates it and
fires `events.newPointer` on an idle callback), then wires
`setMotion/setEnter/setLeave/setButton/setAxis/setFrame`. A `CWaylandTouch : public ITouch` is the
same shape with `wl_touch`'s `down/up/motion/frame/cancel` mapped to `ITouch::SDownEvent` /
`SUpEvent` / `SMotionEvent` / `SCancelEvent` — the interface `Backend.hpp:20` declares as
`class ITouch` and `:153` as the `newTouch` signal, and which the libinput path already emits
(`src/backend/Session.cpp:728-754` for the four event types, `:973` for
`events.newTouch.emit(...)`; 31 `touch` hits in that file) — plus a `HAS_TOUCH` branch in
`initSeat()` and the `CCWlTouch` binding. Size: **~150-220 new lines** in `Wayland.cpp`,
**~25-35** in `Wayland.hpp` (the class plus the backend's `touches` vector), **~10** in
`initSeat()`; no host/guest contract change, and the packager already carries an aquamarine patch
and re-pins the package (`rootfs/package-omarchy-rootfs.sh:101-118`), so it is a repack, not a new
build system.

**Hyprland needs no change**: `Compositor.cpp:478-480` already listens for `newTouch`, and its touch
path resolves the layer surface under the point and sends `wl_touch.down` to it
(`Hyprland v0.56.1 src/managers/input/Touch.cpp:17-118`, read for `r4-touch-research.md:225-236`).

**cage forwards touch already**, verified directly at `v0.3.1`: the seat advertises touch when a
touch device exists (`seat.c:124`, `!wl_list_empty(&seat->touch)`), a new wlr touch is attached to
the cursor and mapped to an output (`handle_new_touch`, `seat.c:173-189`, dispatched at `:449`),
and a touch-down resolves the surface under the point and notifies the client
(`handle_touch_down`, `seat.c:501-521` → `wlr_seat_touch_notify_down`). The upstream half — wlroots
0.20's X11 backend turning `XI_TouchBegin/Update/End` into `wlr_touch` — was read in
`r4-touch-research.md:46-50` (`backend/x11/input_device.c:221-277`, `:70-105`). The device test
confirmed the tap reaches cage and dies only at aquamarine.

**Upstream status: no one is working on it.** GitHub issue/PR searches on 2026-11-24 —
`repo:hyprwm/aquamarine touch` (17 results, every one DRM/KMS unrelated),
`repo:hyprwm/aquamarine is:pr touch` (4, unrelated), `repo:hyprwm/aquamarine wayland touch input`
(4, unrelated), `repo:hyprwm/Hyprland nested touch` (13, unrelated), `repo:hyprwm/Hyprland touch
device cage` (0). So the patch would be ours to write and, plausibly, to send upstream (both
projects are BSD-3-Clause — `BUNDLE:BlackFireAlex-omarchy-android-0f4cee8/manifest/components.lock:3-4`).

What the patch would make possible that emulation cannot: real `wl_touch` in QML (multi-finger
gestures, `PointHandler` device discrimination, kinetic scrolling), Hyprland's own touch gestures
and edge swipes, and a squeekboard that types on touch-down rather than on a synthetic click.

---

## 5. Recommendation, ranked

**(a) A touch-friendly Omarchy without Omamobile — do this first.** What Omarchy already gives,
measured: hit sizes come from three theme tokens. `Commons/Style.qml:19-26` documents them —
`[font] base-size` is the rem root, `[spacing] scale` multiplies margins/gaps/padding/controls, and
`[bar] size-horizontal` / `size-vertical` set the bar's cross-axis size (defaults 26 / 28 logical px,
`Style.qml:342-343`, scaling with `base-size`), all in the theme's `shell.toml`. So a 44 px bar and
bigger type are a **theme change**, not code: `base-size` 12 → 16 (everything follows:
`Style.font.*` `Style.qml:321-341`, `Style.spacing` `:231-254`) and `size-horizontal` → 44. The bar
widgets are `WidgetButton`s with a `MouseArea` and already react to a click
(`r4-touch-research.md:240-250`; the r4 harness clicked a workspace item and the Omarchy menu at
(45,26) with an X-level click), the menu and panels are `qs.Ui` components sized by the same tokens,
and Hyprland's `general.gaps_in/out` and `border_size` are plain config. First concrete step: set
`gaps_in = 0, gaps_out = 0, border_size = 0` in `~/.config/hypr/looknfeel.lua` (as
`OM:hypr/phone.lua:19-21` does), then override two shell sections in the theme —
`shell.bar.toml` with `size-horizontal = 44` and `shell.font.toml` with `base-size = 16` — which is
the mechanism the shell documents (`docs/theming.md:184-194`: a theme may ship `shell.toml` or one
`shell.<section>.toml` per section; defaults in `default/themed/shell.toml.tpl:5-16` for `[bar]`,
`:101-106` for `[font]`). Then look at it. Risk: taste, not engineering. Effort: an evening, no
repack, reversible.

**(b) Cherry-pick the five pointer-clean plugins** (`bar`, `quicksettings`, `launcher`, `back`,
`switcher`) into an overlay directory, with their status halves allowed to show less. This is the
real answer to the question: it buys an Android-shaped bar, a pull-down sheet, a launcher pill and a
back gesture for ~10.4k lines of MIT QML written for *this* shell's plugin API (§2), with no fork of
Omarchy and no new daemon. First concrete step: copy
`OM:packages/omamobile-shell/plugins/omamobile.{bar,quicksettings,launcher,back,switcher}` plus
`bin/omamobile-{launch,home}` and a three-line `uwsm-app` shim (§3) into a new
`rootfs/overlay/etc/phoshdroid/omamobile/`, have `start.sh` link them into
`~/.config/omarchy/plugins/` **before** the index runs (`start.sh:63`), point `shell.json` at
`bar.id: omamobile.bar` + the four `plugins[]` entries, and verify the index lists them
(`grep -c thirdparty "$XDG_RUNTIME_DIR/omarchy-plugin-scan.txt"`). Risk: the tile services and
`omamobile-launch`'s uwsm/shim path; budget one round on bar + quicksettings alone (they need no
helper binary at all beyond stubs) and judge from the render.

**(c) The whole phone profile after the aquamarine touch patch.** Only once (b) reads well at
1600×985 and the touch device exists: then re-base `omamobile-omarchy`'s 4.5 series onto the guest's
Omarchy (or, better, re-pin the guest to 4.5 so the series applies as published), take the phone
`shell.json`, `hypr/phone.lua`, `omamobile-launch`/`omamobile-home`, and add `CWaylandTouch` (§4).
Risk: the patch series is the fragile part (context drift against a moving Omarchy), and the phone
profile's most visible parts — lock keypad, notification swipe, double-tap wake — are exactly the
patched ones. Effort: the aquamarine patch is a day or two including a repack; the patch re-base is
the open-ended part.

**Not recommended at any point:** `omamobile.keyboard` (Android's keyboard wins), `fingerprint`,
`call`, `mobilenetwork`, `voice`, `access`, `update`, `omamobile-settings`, `omamobile-apps` —
every one of them is a proxy for hardware or a systemd service that proot does not have (§1).

**What I would do first, plainly:** (a), tonight — it is config, it costs nothing, and it tells us
how much of the "phone feel" is scale rather than widgets. Then (b) with bar + quick settings as a
two-plugin spike, because those two are the pieces whose absence actually hurts a finger-driven
session and they need nothing from Omamobile's patches. (c) only if (b) reads well and the tablet is
going to be used as a tablet rather than a small laptop.

---

### Appendix: what was read, and what was not

- **omamobile at `b5baaea`**: `AGENTS.md`, `README.md`, `docs/ROADMAP.md`,
  `packages/omamobile-shell/` (`README.md`, `plugins/README.md` 1215 lines, all 13 `manifest.json`,
  `profile/shell.json`, `hypr/phone.lua`, `bin/omamobile-setup-user`, `install`, the per-plugin
  QML/JS), `packages/omamobile-omarchy/` (`PKGBUILD`, `install`, patch headers), and the READMEs of
  `omamobile-{settings,owl-widgets,apps}`. Handler census over all plugin QML: `TapHandler` 41,
  `DragHandler` 15, `PointHandler` 5, `MouseArea` 107, `MultiPointTouchArea` 0, `PinchHandler` 0;
  per-plugin counts are in §1.
- **Guest bundle**: `BlackFireAlex-omarchy-android-0f4cee8/manifest/{components,release}.lock`, the
  whole `shell/` tree's `PluginRegistry.qml`, `shell.qml`, `Commons/{Style,Color,qmldir}`,
  `Ui/qmldir`, both `shell.json` files, and the rootfs tar listing (556 packages).
- **Omdroid**: `AGENTS.md`, `rootfs/overlay/etc/phoshdroid/{start.sh,omarchy-plugin-index.sh}`,
  `rootfs/package-omarchy-rootfs.sh`, `docs/omarchy/r4-touch-research.md`, `r4-touch-report.md`,
  `r4-input-research.md`, `LauncherActivity.kt`, `SessionPrep.kt`.
- **Pinned URLs**: `hyprwm/aquamarine v0.14.0` (`src/backend/Wayland.cpp`,
  `include/aquamarine/backend/Wayland.hpp`, `src/backend/Session.cpp`), `hyprwm/Hyprland v0.56.1`
  (`src/Compositor.cpp`, `src/managers/input/InputManager.cpp`), `cage-kiosk/cage v0.3.1`
  (`seat.c`), `qt/qtdeclarative v6.11.2` (`src/quick/handlers/qquick{pointerdevice,tap,drag}
  handler.cpp`), and the GitHub API for `158e8cfb`'s date, `compare/v4.5.0...158e8cfb`,
  `compare/v4.0.6...158e8cfb`, and the issue searches quoted in §4.
- **Not read / not checked:** Hyprland's `Touch.cpp` directly (relied on the line-level reading in
  `r4-touch-research.md:225-236`; the same file was read there, not here), `omamobile.home`'s `owl/`
  runtime internals, and **no render was produced** — whether the five plugins look right at
  1600×985 is option (b)'s first gate, and this round had no device and no shell.
