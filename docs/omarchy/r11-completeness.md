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
| 2 | F6: the UI scale follows the display, live | **PASS** (device, phase 3, APK from `28039e9`) | Dock (overlay 1920x1080/160): scale 1.00 and `probe.sh` PASS 2 s after the setting, monitor 1920x1080 logical 1920x1080, layers `omarchy-background` 1920x1080, `omarchy-bar` 1920x26, Hyprland pid 16531 before and after. Undock: scale 2.00, 3200x1970, logical 1600x985, mobile layers (bar 1600x44, dock, launcher), probe PASS, same pid. Watcher log `ui-scale 2 -> 1`, `monitor fit 1920x1080 scale 1 rc=0; GDK_SCALE 1 rc=0` (also in the size fit after the reload, the `c0a9e92` fix), then `ui-scale 1 -> 2`. Control, d69b2d4 run: `OMDROID_SCALE_FOLLOW=0` leaves the docked monitor at `scale 2.00` (the F6 bug). My look at `p3-docked.png`: a 1920x1080 desktop UI at scale 1 (thin bar with workspaces 1-5, clock, indicators). |
| 3 | Power and session entries | **PASS on the `b5dd09d` build (phase 4); two follow-up fixes in test (phase 5)** | Menu (screenshot, d69b2d4): Back to Android, Logout, Restart, Shutdown; no Lock, Screensaver, Hibernate. Phase 3 (`28039e9`): `home` PASS; `restart`/`stop`/`shutdown` FAIL (the host took the request, but SIGTERM and SIGKILL on the proot process did not end the guest). Phase 4 (`b5dd09d`, the guest ends itself): `home` PASS at +4, +10 and +20 s (top `com.miui.home`, `probe.sh` PASS each time, Hyprland pid 29423 unchanged, icon tap returns the desktop, pid still unchanged). `restart` PASS (request 02:41:34.187, `session ended by request RESTART` 1.46 s later, new Hyprland pid 30728, `probe.sh` PASS 8 s after, total 20 s). `stop` PASS (`ended-screen exit=0`, guest Hyprland gone, Start again brought a new desktop in 17 s). `shutdown` PASS (app pid gone, 0 tasks). Two defects seen in phase 4, fixed in `1a6b634`: (1) `proot exited (139)` with `Segmentation fault` in the ended screen's log tail, which I first read as a SIGTERM effect; phase 7 and 8 showed it also after the exit dispatcher (section 6, "Exit code 139"), so the guest uses the dispatcher as the orderly path, not as the cure; (2) the fake-root broker (proot pid 29109 with its python child) survived a restart and a stop (it was still listed 15 s later, after `root-broker stopped` had been logged 3 s into each request); the guest now asks its python program to end and the host logs when SIGKILL does not work. Phase 5 re-runs three restarts, stop and shutdown with a process listing (pid, parent, state) after each. |
| 4 | Idle lock | **DECIDED** | Cause: `/etc/pam.d/omarchy-lock-password` is absent from the image (measured `ls`; read `lock/Service.qml:497,532`), so `omarchy-shell lock lock` answers `missing-pam` on stdout and `omarchy-system-lock` exits 0 without locking (measured, audit-1). Decision: Android owns locking; the guest idle service is held off with Omarchy's own stay-awake flag (measured on d69b2d4: `idle-cycle-cancel: stay-awake`), the Lock row is hidden. Section 4. |
| 5 | Clipboard Android <-> Omarchy | **GAP MEASURED, design only** | The X selections CLIPBOARD and PRIMARY on the display Xlorie serves have no owner (`owner=0x0`) before and after a guest `wl-copy`, while `wl-paste` in the guest returns the text (phase 3 D). Nothing carries the Wayland clipboard to the X display, so nothing reaches Android. Section 5. |
| 6 | Hyprland start-up warning banners | **PASS** (device, one start each side) | R10 cold start screenshot (`audit1/shots/aud-cold-1.png`) shows both banners at the top right ("does not have hyprland-guiutils installed", "started without start-hyprland"). The same capture point on the `28039e9` build (`phase3/shots/p3-cold2-1.png`) shows neither (only two stale Omdroid test toasts, see risks). Code `690baf0`: a marked block in `looknfeel.lua` setting `misc.disable_hyprland_guiutils_check` and `disable_watchdog_warning`; both option names read from the shipped binary with `strings`. |
| 7 | Session-end screen: blank launcher and ANR when a session ends from inside (found by S5 as V6) | **PASS** (device phases 7 and 8; control reproduced) | Control R10 `bef783d7`: both cases hang (main thread `futex_wait_queue` at +2 s and +8 s, "Omdroid isn't responding" on screen, no desktop after 60 s / 90 s). `9fe8e11` (`3c8ed4b9`): ended screen 14 ms after the exit, no ANR, Start again brings the desktop back in 15-21 s, exit 7 shows its text and log tail; no ANR in 21 session ends. `60d0b95` (`9dae471b`): the broker proot no longer outlives a guest exit (0 `libproot` 12-14 s after each of 13 exits from inside and 2 Hyprland kills). Section 6. Open: exit code 139, see below. |

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

Contract: `launch-contract.md` section 11. Guest `omdroid-session stop|restart|shutdown|home` writes `<prefix>/tmp/omdroid-host/request`; `ProotService` watches it with a `FileObserver`, deletes it (the acknowledgement) and acts. `systemctl suspend|poweroff|reboot` and the four `omarchy-system-*` scripts are mapped onto it by wrappers linked into `/usr/local/bin`. Switches: `OMDROID_COMPLETE_POWER=0` (wrappers off), `OMDROID_COMPLETE_MENU=0` (menu block off), `OMDROID_COMPLETE=0` (everything).

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

## 5. Clipboard: the measured gap and the design

**Measured** (phase 3 D, `28039e9`): `printf r11-clip | wl-copy` then `wl-paste` in the session returns `r11-clip`, while a small Xlib client on `DISPLAY=:0` reads `CLIPBOARD owner=0x0` and `PRIMARY owner=0x0` before and after. So the Wayland clipboard inside Hyprland is a closed world.

**Read, Termux:X11 side** (`termux-x11/app/src/main/cpp/lorie/clipboard.c`): Xlorie is the one that talks to Android. When any X client takes the CLIPBOARD selection (`SelectionSetOwner` callback, `lorieSelectionCallback`) it asks that client for TARGETS and the text and sends it to Android; when Android copies, Xlorie takes CLIPBOARD ownership itself and answers `ConvertSelection` requests (`lorieProcConvertSelection`). The preference `clipboardEnable` defaults to true (`preferences.xml:55`). So the Android half already exists; only the guest has no X client that owns or reads the selection. Under cage's x11 backend nothing turns a Wayland data offer into an X selection (consistent with the measurement; I did not read wlroots).

**Design** (not built, no X server on the build machine to test it against without touching the owner's desktop): one guest helper, `python3` plus `libX11` and `libXfixes` through `ctypes` (all present in the guest, like `fit-x11.py`), started by the `complete` hook:

1. Guest to Android: `wl-paste --watch` (or the plugin's own offer) feeds each new text into the helper, which takes CLIPBOARD on `:0` with its own window and answers `SelectionRequest` for `TARGETS`, `UTF8_STRING`, `STRING` and `TEXT`. Xlorie's callback then forwards it to Android.
2. Android to guest: `XFixesSelectionNotify` on CLIPBOARD for an owner that is not the helper's window means Xlorie took it; the helper sends `XConvertSelection(UTF8_STRING)`, reads the property and runs `wl-copy`.
3. Loop guard: ignore a change whose owner window or whose text equals what the helper last set itself. Text only, no INCR transfer (cap at about 1 MB), no images.
4. Switch `OMDROID_CLIPBOARD_BRIDGE=0`. Test plan: a host test with `Xvfb` or a nested X server and a stub `wl-copy`/`wl-paste`, then on the tablet `uiautomator`/`input text` into an Android field, `am broadcast` a clipboard set, and a `wl-paste` round trip in both directions; the positive control is the `owner=0x0` reading above turning into the helper's window id.

## 6. The session-end screen (the R10 blocker S5 found)

**Symptom (measured by S5, phase 3, `r11-verification.md` section V6, R10 build):** after the guest ends from inside (`hl.dsp.exit()`, exit 0) the host logs `proot exited (0)` and `launch: session ended exit=0 ui=shown`, then nothing: the launcher stays blank, Android raises "Omdroid isn't responding" 5.0 s later, no Start button, an icon tap restarts nothing for 90 s. A session that exits 7 at launch logs `ended-screen exit=7` but shows "Starting desktop...".

**Cause (read, not yet measured on a stack):** `ProotService.finishSession` calls `startActivity(launcher, session_ended)` and `stopSelf()` on the main thread. `onDestroy` then runs `stopSession()`, which ended in `stopBroker()` on the R10 build: `process.destroy(); process.waitFor()` with no bound, on the main thread (`git show f2584e7:.../ProotService.kt`, `stopBroker`). The fake-root broker proot is the process that did **not** die on SIGTERM or SIGKILL in phases 4 (it was listed 15 s after a stop and a restart, and for as long as the app process lived). So the main thread sits in `Process.waitFor` (futex wait) and never draws the ended screen. That fits every symptom: `ended-screen` is logged in the same main-thread turn that draws nothing yet; uiautomator returns no dump (main thread gone); the ANR arrives at the 5 s input limit; the exit-7 case logs its line and then the window is still the layout's default text ("Starting desktop..."), because the next frame is never drawn. S5's p7 stack capture never ran (its phase hung on `adb jdwp`), so the main-thread stack is not read; `/proc/<pid>/task/<pid>/wchan` is sampled in phase 7 instead.

**Why my own earlier runs did not hit it:** every session end in phases 4 was a REQUEST (`omdroid-session stop`), where the request thread had already stopped the broker, so `onDestroy` found no broker. A Hyprland exit from inside (a key binding, `hl.dsp.exit()`), or any guest crash, takes the other path.

**Fixes:**

1. `6e23362` `ProcessStop` (new, 5 unit tests): SIGTERM, bounded wait, SIGKILL, bounded wait, outcome logged (`ALREADY_DEAD|TERMINATED|KILLED|SURVIVED`); `stopAsync` returns at once and does the whole wait on a named daemon thread. `stopBroker()` and `stopSession()` use it, so nothing in `onDestroy` or the notification Stop waits on the main thread any more. The positive control in the test: the blocking form of the same fake process takes the full 120 ms of bounded waits while `stopAsync` must return in under 100 ms.
2. `9fe8e11` `FailedLaunch` (new, 5 unit tests): when the bootstrap that is waiting sees `SESSION_DIED` and the exit happened after this launch started, it shows the ended screen with the exit code (not the vaguer "did not start: session_died"). `finishSession` now records the exit code before it clears `active`, so a thread that sees the session dead always finds this exit.
3. The broker still outlives SIGKILL on the device (cause not found). It is now stopped on its own thread and a survivor is logged (`session: root-broker still alive after SIGKILL`), and the guest's own stop path asks the broker's python to end too.

### Phase 7 results (device, 08:34-08:46, **measured**, screenshots **viewed**)

Control = the R10 APK (`bef783d7...`); mine = `9fe8e11` (`3c8ed4b9...`). Log `phase7.log`, shots `phase7/shots/`. The session end from inside is S5's own method: `hl.dsp.exit()` over the Hyprland socket 35 s into the session.

| Case | Control R10 | `9fe8e11` |
| --- | --- | --- |
| A. exit from inside | launcher on top after 3 s; `session ended exit=0 ui=shown`, **no `ended-screen` line**; main thread `S futex_wait_queue` at +2 s and +8 s; screen: **"Omdroid isn't responding" (Wait / OK)** on a black screen (viewed); broker proot 31565 and its python 31573 still listed; icon tap: no desktop after 60 s | `ended-screen` 14 ms after `proot exited`; main thread `do_epoll_wait` (idle); no ANR; screen (viewed): "The desktop session stopped unexpectedly (exit 139)." with the log tail (ending in `session-child.sh: line 49: ... Segmentation fault`) and **Start again**; tapping it: desktop back after 17 s, `probe.sh` PASS |
| B. dies at launch (`session.env`: `exit 7`) | `ended-screen exit=7 651ms` logged, but the screen (viewed) is the layout's default "Starting desktop..." and uiautomator reads "Omdroid isn't responding"; no Start button; no desktop after 90 s | screen (viewed): "The desktop session stopped unexpectedly (exit 7)." with the log tail (`++ echo r11-forced-exit`, `++ exit 7`) and **Start again**; desktop back after 15 s |
| C. Logout (`omdroid-session stop`) | not run (the request channel is mine) | `session: request STOP`, broker `stopped (TERMINATED)`, `proot exited (0)`, `guest process ended by itself`, ended screen 14 ms later with Start again; `libproot` count 0 fifteen seconds later; desktop back after 21 s |
| D. Restart x3 | not run | new Hyprland pid each time, `probe.sh` PASS after 19 / 19 / 20 s, `libproot` count 2 after each (session + broker, no pile-up) |
| E. Hyprland SIGKILLed 35 s in | not run | ended screen, exit 0 ("The desktop session ended.": proot reports 0 for a killed Hyprland), Start again: desktop back after 21 s; broker proot **still alive** (`root-broker still alive after SIGKILL`) |
| F. Shutdown | not run | app process gone, 0 tasks, 0 `libproot`; no ANR in any case |

What this proves: the unbounded main-thread wait is the blocker (the control hangs in `futex_wait_queue` with a broker proot that does not die, and the fixed build, whose only change on that path is the wait, draws the ended screen at once). What it does not prove: I did not capture the main-thread Java stack, so the cause of the futex wait is the strongest reading of the source and the wchan sample, not a stack.

Two things phase 7 showed that are not fixed by `9fe8e11` (fix `60d0b95`, phase 8 queued):

- **Exit code 139 on exits from inside:** 3 of the 5 dispatcher exits of the fixed build ended `proot exited (139)` (A, restart 1 and 3); the control gave 0 on 2 of 2 (mine and S5's). A Hyprland segfault at exit that my overlay may cause, or that the control sample missed. Phase 8 runs 3-4 exits per arm: R10, default, `OMDROID_COMPLETE=0`, `OMDROID_COMPLETE_BANNERS=0`. Until then: a Logout/Restart request shows no code to the user (the host reports 0 for a requested end); only an exit from inside shows "stopped unexpectedly (exit 139)".
- **Broker leak on guest-exit paths:** in A, B and E the host's SIGTERM and SIGKILL did not end the broker proot while its python child lived (`session: root-broker still alive after SIGKILL`, the pair still in `ps`); the guest-side `pkill` on request paths ends it. `60d0b95` signals the descendants too, logs `/proc` facts when a process survives, and phase 8 counts `libproot` after each path.

### Phase 8 results (device, 09:22-09:41, build `60d0b95` = `9dae471b`, **measured**)

Exit from inside (`hl.dsp.exit()` over the socket, 15 s after the desktop is up), then Start again; `proot exit` is the code the host logged, `libproot` the count of proot processes 12 s after the exit (0 = no leaked broker).

| Arm | Exits | proot exit codes | libproot after 12 s | Notes |
| --- | --- | --- | --- | --- |
| R10 control | 3 | 139, (none, none) | 1, 1, 0 | the R10 launcher hangs after the first exit, so only the first exit is a clean sample; its broker proot stays listed |
| `60d0b95` default | 4 | 139, 0, 0, 0 | 0, 0, 0, 0 | `root-broker stopped (TERMINATED)` each time; desktop back in 19-21 s |
| `60d0b95`, `OMDROID_COMPLETE=0` | 3 | 0, 0, 0 | 0, 0, 0 | |
| `60d0b95`, `OMDROID_COMPLETE_BANNERS=0` | 3 | 0, 0, 0 | 0, 0, 0 | |
| `60d0b95`, Hyprland SIGKILLed, twice | 2 | 137, 0 | 0, 0 | broker `exited 0` within 0.1 s; desktop back in 18-19 s |

- **Broker leak: fixed and measured.** Before (`9fe8e11`, phase 7) the broker survived all three guest-exit paths; with `60d0b95` it ended on every one of 9 exits and 2 kills in this phase (0 `libproot` afterwards). Whether SIGKILL on the broker proot alone works is still unexplained (phase 7 says no, and the fix signals its python child as well), and nothing in phase 8 isolates which of the two signals did it.
- **Exit code 139 (a Hyprland segfault at exit): not caused, not cured, not settled.** It happens on the R10 control (1 clean sample out of 1 in this phase, 0 of 2 in phase 7 and in S5's run), and on my build in 4 of 9 exits from inside (phases 7 and 8 pooled: 139 in A, restart 1, restart 3, default cycle 1). With `OMDROID_COMPLETE=0` or `OMDROID_COMPLETE_BANNERS=0` it did not occur in 6 exits. If my build crashed at the pooled 4/9 rate, 0 of 6 would happen with probability 0.56^6 = 3%, which points at the banner block (`misc.disable_hyprland_guiutils_check`, `misc.disable_watchdog_warning`) and is NOT proof (small samples, runs on different days of the same build, the control also crashed once). A needed follow-up: 10 exits per arm, default against `BANNERS=0` on the same build. What users see: a Logout, Restart or Shutdown request reports exit 0 whatever Hyprland does; an exit from inside (a key binding) shows "stopped unexpectedly (exit 139)" with the log tail, and Start again works.

## Device proof

| Phase | APK | What it proved |
| --- | --- | --- |
| audit-1 | R10 `bef783d7` | the audit (section 1): tools, menu, toggles, power, lock, idle |
| phase 2 | `d69b2d4` `8e71f124` | menu block (screenshot); idle held by stay-awake; F6 bug reproduced and fixed by `c0a9e92`; `restart` taken but not ended |
| phase 3 | `28039e9` `db8977f9` | F6 both directions PASS; terminal shim and nano editor PASS (floating terminal class `org.omarchy.terminal`; `omarchy-launch-config-editor` opens nano on `monitors.lua`, screenshot); banners gone; `home` PASS; `restart`/`stop`/`shutdown` not ending the guest; clipboard gap measured |
| phase 4 | `b5dd09d` `dbab89d4` | guest-driven end for restart, stop and shutdown PASS; `home` round trip PASS three samples; broker survival and the SIGTERM segfault found |
| phase 5 | `1a6b634` (queued) | exit dispatcher and broker end; three restarts in a row with process listings; test residue removed from the owner's notification history |

Items from phase 3 that phase 4 settled or narrowed:

- The 22.3 s first start after an install (bar missing for about 40 s) did not recur: phase 4 starts took 13.4 s and 12.7 s (and 13.4 s at the end), the phase 3 second start 12.6 s. One bad sample out of seven starts of these builds, cause not found.
- `probe.sh` showing no layers 4 s after `home` did not recur: three samples at +4, +10, +20 s all PASS. Treated as a one-off sampling coincidence, not explained.

## Risks

- The request watcher and the kill path are device-only; a bug there leaves a session that cannot be ended from the menu (the notification Stop still works).
- The `systemctl` wrapper changes what every guest script sees for the three power verbs; every other verb still reaches the real binary.
- The banner block edits the user's `looknfeel.lua` like the mobile-UI block does (marked, removed whole).
- Test residue in the owner's guest: the d69b2d4 run's two critical "Omdroid could not shutdown/stop" notifications are persistent (one file each under `~/.local/state/omarchy/notifications/`) and reappear at every shell start; the phase 3 and phase 4 screenshots still show them (`notifications clear` empties the history only, not the restored popups). The notice is now normal-urgency (`b5dd09d`), and phase 5 dismisses the live popups and deletes only the files that carry "Omdroid could not", at its start and its end.
- `proot` ends with exit code 139 when Hyprland is signalled (SIGTERM segfaults the patched build); that is the fallback path only now.

## What I did not do

- Capture, nightlight, brightness, Wi-Fi and Bluetooth rows are not fixed or hidden (1.2 rows 6-9).
- Clipboard bridge (step 5): measured and designed, not built.
- The Hyprland exit crash (exit 139) is not settled: needs 10 exits per arm, default against `OMDROID_COMPLETE_BANNERS=0`, on one build. Until then the banner block ships on, because the two start-up warnings it removes appear in every session.
- No main-thread Java stack of the R10 hang: S5's JDWP capture hung the tablet lock and was stopped; the cause is read from the source and the wchan samples.
- `:app:lintDebug` was not run (CI runs it).
- No key-by-key test of the 187 bindings.
