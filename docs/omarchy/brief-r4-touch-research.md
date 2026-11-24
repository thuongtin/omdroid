# Brief R4-TOUCH-RESEARCH: where can a tap on the Omarchy bar get lost? (read-only)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. You have NO device: no adb, no gradle, no git commands that change
anything. You write exactly one file: `docs/omarchy/r4-touch-research.md` (repo
`<repo>`). Scratch: `<scratch>/omarchy/r4/research-touch/`.

## The bug

Phil reports that on the tablet, taps on the Omarchy bar do nothing: the workspace numbers do
not switch workspace, the Omarchy button (top left) does not open the menu, the tray icons (top
right) do not react. A sibling agent is measuring this on the device right now and will read
your file as it grows. Your job: from source, say for every hop of the touch path whether it
carries a tap to the bar, what is known to drop it, and how to tell on the device.

## The chain (each hop is a question)

1. Android `MotionEvent` -> Termux:X11, which runs IN the app (submodule `termux-x11/`, local
   source). `touchMode = "3"` is set by `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt`;
   in `termux-x11/app/src/main/java/com/termux/x11/input/TouchInputHandler.java` that is
   `InputMode.TOUCH` with `NullInputStrategy`. What does the app send to the X server for a
   tap in this mode (XI2 touch events? pointer events? both?) and from which file/line? Note
   `AGENTS.md`: `moveCursorToScreenPoint` is disabled on Direct-Touch on purpose and identical
   `XI_TouchUpdate` events are de-duplicated; find both in the source.
2. Xlorie X server (`termux-x11/app/src/main/cpp/`) -> X clients: how a touch is delivered (XI2
   touch events to a client that selected them on its window; pointer emulation for clients
   that did not).
3. cage (wlroots 0.20, `WLR_BACKENDS=x11`) as an X client: does the wlroots 0.20 x11 backend
   select XI2 touch events and create a touch device; how does cage expose touch to its client
   (wl_seat touch capability, `wl_touch`) and does cage forward touch to a fullscreen client at
   all? Cite the upstream source at the versions in use. cage, wlroots and libliftoff are NOT in
   the guest's package database: `rootfs/package-omarchy-rootfs.sh` downloads them, so read their
   exact versions from that script. Everything else (Qt 6.11.2, quickshell 0.3.1, libinput,
   Xwayland) is listed in `/tmp/omarchy-members.txt`, the guest image's member list, under
   `./var/lib/pacman/local/`.
4. Hyprland 0.56.1 nested (aquamarine wayland backend; the patch the payload carries is in
   `<scratch>/omarchy/upstream/BlackFireAlex-omarchy-android-0f4cee8/patches/`):
   does aquamarine's wayland backend create a touch device from the parent's `wl_touch`, and how
   does Hyprland 0.56 route a touch-down that lands on a layer-shell surface (the bar is a
   layer surface on the `top` layer)? Check Hyprland's `input:touchdevice` options and anything
   in the Omarchy Hyprland config that disables touch
   (`<scratch>/omarchy/upstream/usr/share/omarchy/default/hypr/`, e.g. `toggles.lua`,
   `disabled-input-device.lua`, `input.lua`).
5. Quickshell (Qt 6) and the Omarchy bar QML
   (`<scratch>/omarchy/upstream/usr/share/omarchy/shell/`: `Ui/BarIconButton.qml`,
   `Ui/BarWidget.qml`, `Ui/BarIndicator.qml`, `plugins/bar/`, `plugins/menu/BarWidget.qml`):
   does Qt synthesize mouse events from `wl_touch` for these items; does a click here depend on
   hover (`containsMouse`, `hoverEnabled`, HoverHandler) or on a specific button, which a touch
   cannot provide?

## Deliverable

`docs/omarchy/r4-touch-research.md`. Write its first version within your first ~20 calls (the
sibling is waiting for it) and improve it after. Sections:
- **Ranked hypotheses**: each with the evidence (file:line, or a URL pinned to the version), the
  cheapest device test that confirms or refutes it (an exact command the sibling can run, e.g.
  `hyprctl -j devices`, a WAYLAND_DEBUG trace of only the shell, a tap with
  `input mouse tap` versus `input touchscreen tap`), and the fix it implies (with the file it
  touches).
- **Per hop**: a short answer for hops 1-5 above.
- **The simulated-touch fallback**: what `touchMode = "2"` sends for a tap, a drag and a
  two-finger gesture, read from the source, so the cost of switching is known.

Rules: a claim needs a source you read (file:line or a fetched URL). Mark anything else as a
guess. Do not edit any other file.

Final reply, at most 6 lines: the top hypothesis and its decisive evidence, the cheapest test,
and the file path.
