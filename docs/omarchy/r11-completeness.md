# R11 S4: completeness (Omarchy features that are broken or meaningless under Omdroid)

Branch `r11/completeness`, worktree `proot-post-r11-complete`, from `90d7494`. Brief:
`<scratch>/omarchy/r11/brief-r11-complete.md`. Evidence labels: **measured** (command or log given,
host or device), **read** (file:line or script), **estimated** (basis stated). Device builds are named
per item: **R10** = the R10 integration APK (`bef783d7...`), **d69b2d4** = APK `8e71f124...` built from
that commit, **phase 3** = the APK built from the commit named in `phase3.log` (see "Device proof").

## STATUS TABLE

| Step | What | State | Proof |
| --- | --- | --- | --- |
| 1 | Audit: menu, bar widgets, default keybindings | **PARTIAL** | Menu, tools, toggles, power, lock and idle measured on the tablet (R10, `audit-1.log`); 187 default bindings classified from source (read), not pressed one by one; bar widgets read plus seen in screenshots. Section 1. |
| 2 | F6: the UI scale follows the display, live | **FIX COMMITTED, device proof PENDING** | d69b2d4 run: dock wrote `ui-scale 1`, the watcher fitted scale 1 (`monitor fit 1920x1080 scale 1 rc=0; GDK_SCALE 1`), then the config reload put scale 2 back and the old size fit re-applied 2; the run undocked 6 s later, so the docked end state was never sampled (my own screenshot of that moment shows the scale-2 bar). Fix `c0a9e92` (size fit carries the wanted scale); the watcher test reproduces the bug on the old code (evals `['1','2','1']`) and passes on the new (12/12). Control `OMDROID_SCALE_FOLLOW=0`: the docked monitor stays `scale 2.00` (the old behaviour, measured). Phase 3 settles both directions. |
| 3 | Power and session entries | **PARTIAL** | Menu verified by screenshot on d69b2d4 (rows: Back to Android, Logout, Restart, Shutdown; no Lock, Screensaver, Hibernate). The host took `restart` (`session: request RESTART`) but the guest was not ended, and `omdroid-session stop` / `shutdown` then exited 1 (never taken). The first `home` request (via `omarchy-system-lock`) returned 0 but left no host log line and the X activity stayed on top. Cause not proven (main-thread block suspected: `stopBroker()` waited on the main thread). Fix `084c213` (kill off the main thread, bounded waits, a log line per step) and `28039e9` (guest request log). Phase 3 re-runs every request with a full logcat per step. |
| 4 | Idle lock | **DECIDED** | Cause: `/etc/pam.d/omarchy-lock-password` is absent from the image (measured `ls`; read `lock/Service.qml:497,532`), so `omarchy-shell lock lock` answers `missing-pam` on stdout and `omarchy-system-lock` exits 0 without locking (measured, audit-1). Decision: Android owns locking; the guest idle service is held off with Omarchy's own stay-awake flag (measured on d69b2d4: `idle-cycle-cancel: stay-awake`), the Lock row is hidden. Section 4. |
| 5 | Clipboard Android <-> Omarchy | **PENDING** | Guest-internal `wl-copy` -> `wl-paste` works (measured, audit-1). The bridge question is measured in phase 3, section D. |
| 6 | Hyprland start-up warning banners | **PENDING** | Code `690baf0` (marked block in `looknfeel.lua` setting `misc.disable_hyprland_guiutils_check` and `disable_watchdog_warning`; both option names read from the shipped binary with `strings`). Device screenshot comparison in phase 3. |

## 1. Audit

### 1.1 Tools the Omarchy scripts call, measured in the session PATH (R10, `audit-1.log`)

Present: `systemctl`, `systemd-run`, `loginctl`, `busctl`, `journalctl` (binaries only: no systemd runs, no system bus), `pactl`, `wpctl`, `pw-cli`, `foot`, `nautilus`, `chromium`, `grim`, `slurp`, `wl-copy`, `wl-paste`, `ffmpeg`, `btop`, `fastfetch`, `nano`, `jq`, `notify-send`, `upower`, `wtype`.
Missing: `uwsm`, `xdg-terminal-exec`, `nvim`/`vim`, `gum`, `nmcli`/`iwctl`/`impala`, `bluetoothctl`/`bluetui`, `powerprofilesctl`, `brightnessctl`, `hyprsunset`, `hyprpicker`, `gpu-screen-recorder`/`wf-recorder`, `tesseract`, `zbarimg`, `localsend`, `tailscale`, `docker`, `mise`, `fzf`, `walker`, `swayosd-client`, `limine`, `mkinitcpio`, `fwupdmgr`, `alacritty`/`kitty`/`ghostty`. `/etc/pam.d/omarchy-lock-*` absent. `/sys/class/dmi/id/chassis_type` absent.

### 1.2 Verdicts, ranked by how often a user meets the gap

| # | Feature | Verdict | Evidence | Fix |
| --- | --- | --- | --- | --- |
| 1 | Every menu row that opens a floating terminal or a config editor (Setup, Update, Install, Remove, Style rows, About, Screensaver; 200 of the 270 menu rows that have an action, counted from `menu-dump.txt` by their action or by the scripts it calls naming `xdg-terminal-exec`, `launch-floating-terminal`, `launch-config-editor`, `launch-tui`, `launch-screensaver`, `launch-about` or `menu-plugin`) | **broken**: `exec: xdg-terminal-exec: not found` | measured: `omarchy-launch-screensaver`, `omarchy-launch-config-editor` (audit-1); read: `omarchy-launch-tui`, `omarchy-launch-floating-terminal-with-presentation` call `uwsm-app -- xdg-terminal-exec` | `xdg-terminal-exec` shim over foot, nano as default editor (`690baf0`). Device proof: phase 3 A |
| 2 | System menu: Suspend, Hibernate, Logout, Reboot, Shutdown | **broken, silent** | measured: `systemctl suspend` -> "System has not been booted with systemd"; `omarchy-system-reboot` / `-shutdown` -> "Failed to find executable systemctl", rc 1; `uwsm stop` rc 127 | host requests (`omdroid-session`, step 3) |
| 3 | System menu: Lock | **meaningless**: exits 0, nothing locks | measured: `lock lock` -> `missing-pam`; `isLocked` false | hidden; Android owns locking (step 4) |
| 4 | System menu: Screensaver | **broken** (no terminal chooser, no `ttfx`) | measured rc 1 | hidden; the idle screensaver was already off (`screensaver-off` toggle, R9) |
| 5 | Idle cycle (screensaver at 150 s, lock at 300 s) | **meaningless** | measured: the idle service runs; the lock never engages | stay-awake flag (step 4) |
| 6 | Screenshot, screenrecord, OCR, QR, colour picker (PRINT, Capture menu: 4 bindings, 6 rows) | **broken** | read: `omarchy-capture-*` need `hyprpicker`, `slurp`, `gpu-screen-recorder`, `tesseract`, `zbarimg`; `hyprpicker` and the others are missing (measured), `grim` and `slurp` exist | **not fixed** (packages, outside my files) |
| 7 | Nightlight (SUPER+CTRL+N, Toggle row, Hyprsunset rows) | **broken** | measured: `exec: hyprsunset: not found` | not fixed (package) |
| 8 | Wi-Fi, Bluetooth, power profiles, brightness, hardware rows, laptop display, battery percentage, lid switch | **meaningless**: Android owns them; the guest has none of the tools; `omarchy-hw-laptop` fails on a missing DMI file | measured: every `omarchy-hw-*` guard exits 1 (audit-1) | the menu does not evaluate `when:` guards under proot (read `Menu.qml:1017-1026`), so the rows stay visible; **not fixed** beyond System (a per-row hide list is the follow-up) |
| 9 | Network status in the bar and the Wi-Fi QR row | **meaningless**: `omarchy-network-status` prints `disconnected`; the network panel returns `ethernet` in proot mode (read `panels/network/Panel.qml:443`) | measured / read | none |
| 10 | Audio panel and volume keys | **partial**: `wpctl` cannot reach PipeWire (measured); the shell takes the `pactl` path in proot (read `panels/audio/Panel.qml`); the tablet has no volume keys of its own docked | measured / read | none |
| 11 | Update, channel, firmware, reinstall, reset, drive encryption, security setup | **meaningless or dangerous** under proot: `pacman -Syu` is refused by design, no `limine`, no `mkinitcpio` | read | not fixed (refusing an upgrade is the `yay`/broker policy, R6) |
| 12 | Terminal (SUPER+RETURN), browser, file manager, menus, tiling bindings (68), notifications | **works** | measured: foot opens (`launch-terminal rc=0`); menus render (screenshots) | n/a |
| 13 | Gaps and window toggles, top-bar toggle, stay-awake toggle | **works** | measured: the toggles flip their state files; the bar layer disappears and returns | n/a |
| 14 | Clipboard history (4 bindings) | **partial**: the plugin skips its init in proot mode (read `Clipboard.qml:245,313`) | read | step 5 |
| 15 | Apps absent from the image (tmux, herdr, spotify, signal, 1password, obsidian, omawrite, docker, cliamp, omacalc: 12 bindings) | **meaningless until installed** | read | none |
| 16 | Voice dictation (3 bindings) | **meaningless**: no model, no microphone path | read (`omarchy-voxtype-daemon` exits 0 with no model, R10) | none |

### 1.3 Default keybindings by source (read: 187 `o.bind` lines in `default/hypr/bindings/*.lua`)

Tiling 68 (Hyprland itself, works), menus and shell panels 27, web apps 12 (chromium `--app`, needs the network: not pressed), apps absent from the image 10, media keys 10 (playerctl absent), audio 9, brightness 9, toggles 9, browser/files/editor 6, clipboard 4, laptop display and lid 4, capture 4, voice 3, calculator 2, nightlight 1, terminal 1, other 18. The categories are by keyword, so a few rows are approximate. The device reports 231 live binds (`audit1/binds.raw`); every one is dispatched through `__lua`, so the command is not visible over IPC and each key still needs a press to prove it.

### 1.4 Bar widgets

Seen in the screenshots (docked desktop UI: workspaces, clock, three right-hand indicators; mobile UI: clock, workspace pill, one indicator). Read: `SystemUpdate` is off in proot mode (`SystemUpdate.qml:51`), the keyboard-layout widget skips its brief process (`KeyboardLayout.qml:83`), weather is guarded, `omarchy-battery-present` exits 1 (no battery widget), the network indicator is constant. None is broken, they are inert.

### 1.5 Screenshots viewed (my own look, not a verdict)

- `audit1/aud-menu-system.png` (R10, stock): the System rows are the stock seven (read from the dump; the PNG was loaded but I did not write down a per-row reading for it).
- `phase2/p2-menu-system.png` (d69b2d4): card "System..." with four rows: Back to Android (highlighted), Logout, Restart, Shutdown; search bar below; no banner visible.
- `phase2/p2-docked.png` (d69b2d4, ~2 s after the dock): 1920x1080 desktop with the bar at scale 2 (26 px in a 960 px view), wallpaper, no windows. This is the scale-2 state the logs show before the fit.

## 2. F6: the UI scale follows the display

Code `1e9b6ed`, `c0a9e92`.

- Host: `UiScale.forDisplay` resolves the scale for the target display (the user's `ui_scale` wins); `UiScaleFile` writes `~/.config/omdroid/ui-scale` (1 or 2) atomically. `DockMonitor` writes it before the mode file on every dock change, `LauncherActivity` before every session start.
- Guest: `omarchy-watch.py` reads it every poll and fits the monitor with the same runtime `hl.monitor` rule as the size fit, plus `hl.env("GDK_SCALE", ...)`. The layers then no longer fit, and the existing remedy restarts only the shell.
- Switch: `OMDROID_SCALE_FOLLOW=0` in `session.env`. A missing or junk file changes nothing (only `1` and `2` parse).

## 3. Power and session entries

Contract: `launch-contract.md` section 10. Guest `omdroid-session stop|restart|shutdown|home` writes `<prefix>/tmp/omdroid-host/request`; `ProotService` watches it with a `FileObserver`, deletes it (the acknowledgement) and acts. `systemctl suspend|poweroff|reboot` and the four `omarchy-system-*` scripts are mapped onto it by wrappers linked into `/usr/local/bin`. Switches: `OMDROID_COMPLETE_POWER=0` (wrappers off), `OMDROID_COMPLETE_MENU=0` (menu block off), `OMDROID_COMPLETE=0` (everything).

## 4. Idle lock: the decision

Making the Omarchy lock work needs `/etc/pam.d/omarchy-lock-password` and a password the owner can type on the tablet. The guest user has none, and a lock without a way to unlock strands the session behind Hyprland's failsafe. Android already owns the screen timeout and the real lock, and the guest sees no input while another Android app is on top, so an idle lock in the guest would fire constantly. Decision: off. Lock = hand the screen back to Android; the idle service stays off through the stay-awake flag, which the hook creates once and records (`OMDROID_COMPLETE_IDLE=guest` removes only a flag it created).

## What changed (commits)

| sha | subject |
| --- | --- |
| `8d927ac` | report skeleton |
| `1e9b6ed` | F6: `ui-scale` file, watcher fit, 13 unit tests, watcher checks |
| `d69b2d4` | power and session requests, menu block, idle off |
| `c0a9e92` | watcher size fit carries the wanted scale |
| `084c213` | session request kill off the main thread |
| `690baf0` | `xdg-terminal-exec` shim, default editor, banner block |
| `28039e9` | `omdroid-session` request log |

Host gates: `:app:test` 193/0 at `d69b2d4` (the later commits change the service only; the phase 3 build chain re-runs it); `complete-scale-test.py` 12/12, `complete-menu-test.py` 10/10, `complete-hook-test.sh` all passed. `:app:lintDebug` not run.

## Device proof

(phase 3 results are written here when the job lands)

## Risks

- The request watcher and the kill path are device-only; a bug there leaves a session that cannot be ended from the menu (the notification Stop still works).
- The `systemctl` wrapper changes what every guest script sees for the three power verbs; every other verb still reaches the real binary.
- The banner block edits the user's `looknfeel.lua` like the mobile-UI block does (marked, removed whole).

## What I did not do

- Capture, nightlight, brightness, Wi-Fi and Bluetooth rows are not fixed or hidden (1.2 rows 6-9).
- Clipboard bridge (step 5): measurement queued, no code.
- No key-by-key test of the 187 bindings.
