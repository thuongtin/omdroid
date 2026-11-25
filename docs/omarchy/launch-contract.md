# Launch and geometry contract (host app <-> guest session)

Two agents work against this file in round 2: one owns the host (`app/**`, Kotlin), one owns the
guest (`rootfs/overlay/etc/phoshdroid/**`). Neither edits this file. If something here is
wrong or cannot be met, say so at the top of your report with the evidence and work to the
nearest thing that can.

## 1. Who knows the screen size

**The X root is the truth.** Xlorie sizes its root to the Android surface it is shown on, so the
only number that is always right is the root size at that moment.

- The host predicts the X size before the surface exists and exports it as `XLORIE_WIDTH` /
  `XLORIE_HEIGHT` (the X server's initial root) and `OMARCHY_OUTPUT_WIDTH` /
  `OMARCHY_OUTPUT_HEIGHT` (guest env). Both are HINTS. The host passes the two `OMARCHY_OUTPUT_*`
  variables only when both are greater than 0.
- The guest never trusts the hint over the root: cage's window is kept equal to the root
  (`fit-x11.py`), Hyprland follows its parent, the shell's layers follow the monitor.
- Parity is the guest's job: an odd root width or height is rounded DOWN to an even number for
  cage's window (odd sizes are normal: 2136 - 165 = 1971 on the tablet), so the logical size is
  integral at scale 2. The spare pixel row stays black. The host does not round anything.
- The host makes its prediction exact for the normal full-screen case, so that no resize happens
  at hand-over: X width = window width minus the left and right display-cutout insets; X height
  = window height minus the top and bottom display-cutout insets minus the bottom gap. The bottom
  gap is the Termux:X11 extra-key bar when it is shown, `round(37.5 * density * rows)` pixels
  (rows = 2 by default), else 0. There is no top gap any more: Termux:X11 runs with
  `hideCutout=false`, so Android itself keeps the window clear of a cutout in every rotation.

## 2. Ready marker

File: `$XDG_RUNTIME_DIR/omarchy-ready` in the guest = `<prefix>/tmp/omarchy-runtime/omarchy-ready`
on the host (`<prefix>` = `/data/data/com.phoshdroid.app/files/usr`).

- Written by the guest, atomically (write a temp name, then `mv`), when ALL of these hold:
  Hyprland's IPC answers, it has one enabled monitor whose size equals the X root, and the layers
  `omarchy-bar` and `omarchy-background` exist and fit the monitor's logical size.
- Content, one line: `ready <unix-seconds> <width>x<height> scale=<scale>` (monitor pixels).
- The guest removes a stale marker at session start, before cage starts. The host removes it
  too, before it starts the session.
- The marker means "the desktop was fully drawn once in this session". The guest does not
  remove it on a later resize.
- Host wait rule: hand over when the marker exists. Fallback for a guest image without the
  marker writer: hand over once a `hypr/<instance>` directory has existed for 25 s. Hard cap
  120 s. Give up at once if the session process has died.

## 3. Live size changes

Rotation, fold/unfold, multi-window and the extra-key bar can change the X root while the session
runs. Required end state, with no user action and no session restart: within 15 s of the root
changing, `docs/omarchy/tools/probe.sh` prints `VERDICT: PASS` and the windows that were open are
still open. The host does not kill or restart the session because the display size changed.

## 4. Scale

`OMARCHY_SCALE` is `1` or `2` (integers). The host picks it from the display density unless the
user chose one. Fractional scales are out of scope until the guest round reports which values
this Hyprland build accepts.

## 5. Session start, in order

1. Host: wipe `<prefix>/tmp/omarchy-runtime/` (it is `XDG_RUNTIME_DIR`: nothing in it is meant to
   survive a session) and stale `<prefix>/tmp/proot-*` entries; keep the logs in `<prefix>/tmp`.
2. Host: start the X server, then the proot guest with `/etc/phoshdroid/start.sh`, and alongside
   it the fake-root broker proot (section 7). No host-side Wayland compositor is started (weston
   is gone; cage inside the guest is the parent).
3. Guest `start.sh`: build the plugin index, remove a stale ready marker, start the resize helper
   and the ready/resize watcher, exec `dbus-run-session ... cage -- session-child.sh`.
4. Guest `session-child.sh`: wait (bounded, no fixed sleep) until cage's window equals the X root,
   then exec Hyprland. Hyprland's own config starts the shell.
5. Guest watcher: write the ready marker; afterwards keep the layers in step with the monitor.
6. Host: on the marker (or the fallback), bring `com.termux.x11.MainActivity` forward with the
   same bottom gap it used for the prediction (extras `phoshdroid_top_padding_px` = 0,
   `phoshdroid_bottom_padding_px` = gap). The X view sits at the top of the window.

## 6. Logs both sides can rely on

- Guest: `/tmp/omarchy-session.log` (session), `/tmp/fit-x11.log`, `/tmp/omarchy-watch.log`
  (watcher: one line per state change, with a timestamp). Guest `/tmp` = `<prefix>/tmp`.
- Host: logcat tag `Phoshdroid`, lines starting `launch:` carry the phase name and milliseconds
  since process start.

## 7. Fake root (`sudo`)

The desktop stays as it is: uid 1000 (`-i 1000:1000`), so files the session writes belong to
`omarchy` and git/ssh/ownership checks keep working. The image has no `sudo` package (setuid does
not work under proot) and `su`/`run0`/`pkexec` cannot help, but 70 of Omarchy's scripts in
`/usr/share/omarchy/bin` call `sudo` — `omarchy-pkg-add`, `omarchy-pkg-remove`,
`omarchy-refresh-pacman`, timezone, and the `sudo pacman|tee|sed|rm|cp|mkdir|env` uses inside them.

- **Host**: `ProotService` starts a SECOND proot as part of the session: the login command with
  exactly three differences — `-0` (fake root) instead of `-i 1000:1000`, `-w /root`, and
  `/usr/bin/python3 /etc/phoshdroid/omdroid-rootd.py` as the program. Same rootfs, same binds,
  same `--kill-on-exit`, so both proots see `<prefix>/tmp` as `/tmp`. It stops with the session.
  Logs: `session: root-broker started` and `session: root-broker exited <code>` under logcat tag
  `ProotService`; the broker's own output is mirrored to `<prefix>/tmp/root-broker.log`.
  A broker that is missing or dies changes nothing else: the desktop and the session lifecycle
  never depend on it.
- **Socket**: `/tmp/omdroid-root/sock` in the guest (directory 0700, socket 0600), one request per
  connection, concurrent connections allowed. One line per request in
  `/tmp/omdroid-root/rootd.log`: time, `argv[0]`, exit code.
- **Guest**: `/etc/phoshdroid/sudo` is linked to `/usr/local/bin/sudo` at image time, and again by
  `start.sh` every session so an updated install picks it up. It sends argv, cwd, a whitelisted
  environment and either the caller's terminal (a pty, so Ctrl+C/Z and window size behave) or
  plain pipes with stdin streamed. It never asks for a password.
- **Two more clients of the same broker** (same socket, same request format, so nothing above
  changes): `/etc/phoshdroid/fakeroot`, linked as `/usr/local/bin/fakeroot`, runs its command as
  the target user with the FULL environment (plus `FAKEROOTKEY`, which makepkg's `-F` re-entry
  checks) because that is what makepkg calls for its package step; and `/etc/phoshdroid/yay`,
  linked as `/usr/local/bin/yay`, which is not a broker client itself but installs `yay-bin` on
  first use through `makepkg` and `sudo`. Both links are made by the packager and remade by
  `start.sh`, and `/usr/local/bin` comes first in the session `PATH` so the fakeroot shim wins
  over the real package.
- **What it is**: fake root only. Everything still runs as the Android app's own uid inside its
  private storage, so `sudo` grants no privilege it did not already have. `systemctl` still does
  not work (there is no systemd in this guest).

## 8. Docking (monitor, keyboard, mouse)

A monitor appearing is a dock; it going away is an undock. Neither is a reason to restart the
session (section 3 keeps a live size change alive too), and neither is a reason to lose an open
window.

**Who decides.** The host: `app/src/main/kotlin/com/phoshdroid/app/launch/DockState.kt` is the
pure rule — an external, non-default display docks the device, presentation displays first, public
before private. Android's `UI_MODE_TYPE_DESK` is reported in the `dock:` log line but never docks
on its own (a charging stand sets it, and flipping the phone to the desktop layout with no monitor
attached would be a regression). Input devices are reported, never a trigger.

**The UI mode file.** The host owns `~/.config/omdroid/ui` in the guest
(`<rootfs>/home/omarchy/.config/omdroid/ui`) and writes `desktop` while docked, `mobile` when not,
at two moments: before a session starts (before `start.sh` runs `omdroid-ui.sh`) and on a dock
change while one runs. It writes nothing when the file already holds that mode.

**The pin.** `~/.config/omdroid/ui-pin`, in the same directory, holds the user's choice: `auto`
(the default when the file is missing or unreadable), `mobile` or `desktop`. While it names a mode
the host never writes `ui` at all, so a hand-chosen mode survives every dock and undock:

```bash
echo desktop > ~/.config/omdroid/ui-pin   # keep the stock desktop UI, even on the phone
echo mobile  > ~/.config/omdroid/ui-pin   # keep the phone UI, even on the monitor
echo auto    > ~/.config/omdroid/ui-pin   # follow the dock again
```

`omdroid-ui.sh` keeps reading only `ui`, so the guest needed no change for the pin.

**The live switch.** `omarchy-watch.py` polls `ui` (every 0.25 s). On a change it runs
`omdroid-ui.sh`, rebuilds the plugin index the shell reads at start, restarts only the shell (the
same rate-limited path a size change already used) and, when the monitor already equals the X root,
reloads Hyprland's config for the `looknfeel.lua` half. Windows survive; the session, the X server
and their PIDs are untouched. An older guest image applies a mode change at the next session start
instead — same file, one start later.

**Where the desktop is drawn.** Docked, the host starts `com.termux.x11.MainActivity` with
`ActivityOptions.setLaunchDisplayId(target)`. A private target display, a device without
`FEATURE_ACTIVITIES_ON_SECONDARY_DISPLAYS`, or any refusal falls back to the plain launch, and the
user then opens Omdroid from the monitor itself — the activity runs on the display it is opened on,
which is research route 1 and always works. If a monitor appears while a session is already
running, the host re-launches the same `singleTask` activity with that display id; no second X
activity can be created, and the X root follows the surface the view lands on.

**Keyboard, mouse, bar.** Docked: `showAdditionalKbd=false` (the extra-key bar is a phone
affordance, and its height comes straight out of the X root), and the X activity asks for Android
16.1's keyboard capture — `<uses-permission android:name="android.permission.CAPTURE_KEYBOARD"/>`
plus `LayoutParams.setKeyboardCaptureEnabled(true)` by reflection, because neither is in the
compileSdk 35 SDK — so Meta reaches Hyprland instead of opening the system's own shortcut. On a
platform without it the reflection logs once and Termux:X11's accessibility `KeyInterceptor` stays
the key path. Undocked: the bar and its gap come back.

**Surviving the unplug.** The `termux-x11` submodule manifest sets
`com.samsung.android.multidisplay.keep_process_alive=true`: the in-process X server and the proot
session live in our process, so a Samsung teardown on unplug would take the whole desktop with it.
Unplugged, Android migrates the window to the built-in display, the guest switches back to
`mobile`, and the same session is there when Omdroid is next opened. Not yet proven on a device.

**Logs.** `adb logcat -s Phoshdroid:* | grep dock:` — one line per change:
`dock: docked display=2 1920x1080@213 kbd=1 mouse=1` (a private target adds ` private`; `kbd` and
`mouse` are 1 when Android sees a physical keyboard/mouse), and `dock: undocked`. A dock change
that writes the mode file also logs `dock: ui desktop written (docked)`, and a launch that goes to
a monitor logs `launch: handover done display=2 on-target=true`. Guest side,
`/tmp/omarchy-watch.log` gets `ui mode mobile -> desktop` and
`ui switch: omdroid-ui rc=0; plugin-index rc=0; …`.
