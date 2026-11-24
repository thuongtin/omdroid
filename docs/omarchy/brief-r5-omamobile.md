# Brief R5-OMAMOBILE: can Omamobile's phone shell make Omdroid's UI touch-friendly? (read-only)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. You have NO device: no adb, no gradle, no git command that changes
anything in the Omdroid repo. You write exactly one file:
`<repo>/docs/omarchy/r5-omamobile-research.md`.
Scratch (clone things here): `<scratch>/omarchy/r5/research/`.
Write the first version of the file within your first ~25 calls and improve it after each
finding: a run cut short must still leave a useful file.

## The question (Phil, the owner)

"https://github.com/derekross/omamobile — can we use this to make a more mobile friendly UI?"

**Omamobile** (MIT, ~630 stars, active today) runs Omarchy natively on Pixel phones: mainline
kernel, Arch Linux ARM, Hyprland on DRM, Omarchy's own packages. Its UI part is
`packages/omamobile-shell` ("the phone profile for Omarchy's shell": QML plugins
`omamobile.home`, `omamobile.quicksettings`, `omamobile.keyboard`, `omamobile.launcher`,
`omamobile.bar`, `omamobile.back`, `omamobile.call`, `omamobile.voice`, `omamobile.fingerprint`,
`omamobile.access`, widgets), `packages/omamobile-omarchy` (patches to Omarchy for touch
devices; depends on `omarchy>=4.0.6`, systemd, zram-generator, sudo), `packages/omamobile-apps`,
`packages/omamobile-settings`, `packages/omamobile-owl-widgets`. `omamobile-shell` depends on
`omarchy omamobile-apps omamobile-omarchy>=0.1.11 omamobile-owl-widgets>=0.1.2 bash squeekboard
bluez wf-recorder python python-dbus python-gobject ...`. Most of the rest of the repo is phone
hardware bring-up (modem, camera, GNSS, kernels) and is irrelevant here. Clone it:
`git clone --depth 1 https://github.com/derekross/omamobile <scratch>/omarchy/r5/research/omamobile`
and read its `AGENTS.md`, `packages/omamobile-shell/README.md`, `docs/ROADMAP.md`.

**Omdroid** (the repo above, read its `AGENTS.md` and `README.md`) runs Omarchy inside an Android
app on a Xiaomi Pad 8 Pro tablet (3200x2136 panel, landscape, scale 2): Android -> in-app X
server (Termux:X11) -> cage (wlroots 0.20, x11 backend) -> Hyprland 0.56.1 nested (aquamarine
Wayland backend) -> Omarchy's Quickshell shell (quickshell 0.3.1, Qt 6.11.2), all in proot with
**no systemd**. The guest's Omarchy is the upstream Omarchy-Android bundle, extracted read-only at
`<scratch>/omarchy/upstream/` (`usr/share/omarchy/` = Omarchy itself incl.
`shell/`, `home/omarchy/.config/` = the user config). The shell loads plugins from an index that
Omdroid builds at session start: `rootfs/overlay/etc/phoshdroid/omarchy-plugin-index.sh` (read it:
it decides how a third-party plugin could be added). Guest files reach the device through the
overlay (`rootfs/overlay/etc/phoshdroid/`, installed by `rootfs/package-omarchy-rootfs.sh` and
synced from the APK by `app/build.gradle.kts` `syncGuestOverlay`).

**Two facts measured today that decide a lot:**
1. **The nested Hyprland has no touch device.** aquamarine's Wayland backend never binds
   `wl_touch` (`hyprctl -j devices` on the tablet: `touch: []`; see
   `docs/omarchy/r4-touch-research.md` and `docs/omarchy/r4-touch-report.md`). The fix being
   tested now turns a finger tap into a pointer click at the finger (Termux:X11 "simulated
   touch"): one finger = left click, long press = drag, two fingers = scroll or right click.
   So, today, anything that needs real touch events (Hyprland touch gestures, edge swipes,
   `wl_touch` in QML, multi-finger gestures, squeekboard's touch input) gets pointer events or
   nothing.
2. Android already provides an on-screen keyboard and the Termux:X11 extra-key bar; a hardware
   keyboard pass-through is being built (`docs/omarchy/r4-input-research.md`).

## What to answer

1. **Inventory of the UI pieces.** For each `omamobile-shell` plugin and widget, and for
   `omamobile-settings`, `omamobile-owl-widgets`, `omamobile-apps`: what it does for the user
   (one line), and what it needs at runtime — real touch / gestures (cite the QML: `TapHandler`,
   `DragHandler`, `PointHandler`, `MultiPointTouchArea`, `MouseArea`, Hyprland gesture binds),
   systemd / logind / D-Bus services (ModemManager, BlueZ, NetworkManager, iio-sensor-proxy,
   feedbackd ...), phone hardware, other omamobile packages, a specific Omarchy shell API version.
   Table: piece | what it does | needs | works in Omdroid today? (yes / with pointer emulation /
   no, why).
2. **Version fit.** Which Omarchy (shell) version is in Omdroid's guest (find it in the bundle:
   a version file, the bundle manifest
   `<scratch>/omarchy/upstream/BlackFireAlex-omarchy-android-0f4cee8/manifest/`, the
   shell's plugin API), which one `omamobile-shell` targets (`packages/omamobile-omarchy` patch
   families 4.0.6 / 4.5), and whether the plugin manifests and the QML imports
   (`qs.Commons`, `qs.Ui`, `Quickshell.*`) match what the guest's shell provides. Diff the
   relevant APIs; name the mismatches concretely.
3. **How it would get in.** The exact mechanism: plugin files into which guest path, how the
   plugin index script would list them, the Hyprland config the phone profile changes (gestures,
   layouts, `monitor` rules for portrait, scale), what `omamobile-omarchy`'s patches change in
   Omarchy and whether Omdroid would need them, and the packaging route (an overlay directory in
   the APK vs pacman packages built for aarch64 — no build in this round, just the route).
   Mind proot: no systemd units, no sudo, no hardware.
4. **The touch question, settled.** For each piece that needs real touch: does pointer emulation
   make it usable (taps, long press, drags) or is it dead (edge swipes from outside the screen,
   multi-finger gestures, a squeekboard that needs `wl_touch`)? Then the real fix: what adding
   `wl_touch` to aquamarine's Wayland backend would take (read aquamarine's `src/backend/Wayland.cpp`
   at the version in the guest, 0.14.0, and how it handles `wl_pointer`; does Hyprland's input
   side already accept touch devices from a backend — cite `Compositor.cpp`/`InputManager` touch
   paths; does upstream aquamarine or Hyprland have an issue or PR for nested touch; does cage
   forward touch to its client) — size it in files and rough lines, and say what it would make
   possible.
5. **Recommendation.** Ranked options with effort and what Phil would see on the tablet, e.g.
   (a) a touch-friendly Omarchy without Omamobile (bigger bar and hit targets via Omarchy's own
   settings and scale, a launcher, Hyprland config) — measure what Omarchy already offers;
   (b) cherry-pick specific omamobile plugins that work with pointer emulation; (c) the whole
   phone profile after the aquamarine touch patch. For each: the first concrete step, the files,
   and the risk. Say plainly which option you would do first and why. Note anything in Omamobile's
   licence or attribution that a port must keep.

## Rules

- Every claim cites what you read (file:line in the omamobile clone, the bundle, or the Omdroid
  tree; or a URL pinned to a commit). Anything else is marked as a guess.
- Do not edit any file except your deliverable. Do not post, comment, push or open issues anywhere.
- Never `pkill -f`. Keep the clone shallow; do not download release bundles.

Final reply, at most 8 lines: the recommendation in one sentence, the decisive fit or misfit
(version and touch), the first step, and the file path.
