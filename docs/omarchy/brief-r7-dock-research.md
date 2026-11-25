# Brief R7-DOCK-RESEARCH: phone as a desktop (dock to a monitor = Omarchy, undock = Android)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. READ-ONLY research: no device (no adb at all), no gradle, no git
commands that change anything. You write exactly one file:
`<repo>/docs/omarchy/r7-dock-research.md`.
Scratch (clones, downloads): `<scratch>/omarchy/r7/research/`.
Write the first version of the file within your first ~25 calls and improve it after each
finding, so a cut-short run still leaves a useful file.

## The goal (Phil, the owner, verbatim)

"My dream here is that when I plug my phone into a desktop, I can use Omarchy with the keyboard
and mouse. So when I say plug it into the desktop, I mean if I plug my phone into a monitor,
keyboard or mouse, I can use omarchy. And then when I unplug it and go out and about I can use
android and optionally omarchy."

## What exists (read these in the repo `<repo>`)

Omdroid (read `AGENTS.md`, `README.md`) runs Omarchy in an Android app: Android surface ->
in-process Termux:X11 (`termux-x11/` submodule, `com.termux.x11.MainActivity`, X server in the
app process) -> cage -> nested Hyprland -> Omarchy shell, all in proot. Proven on a Xiaomi tablet
only. Already there:
- The X root follows the Android surface size; a live size change restarts only the shell
  (2-3 s): `launch/DisplayGeometry.kt`, `DisplayShiftMonitor.kt`, guest `fit-x11.py`,
  `omarchy-watch.py`, `docs/omarchy/launch-contract.md`. `launch/UiScale.kt` picks scale 1 or 2.
- Two UI modes, chosen at session start from `~/.config/omdroid/ui`: `mobile` (Omamobile phone
  shell, touch-sized) and `desktop` (stock Omarchy): `rootfs/overlay/etc/phoshdroid/omdroid-ui.sh`.
- Real touch (`touchMode = "3"` + a patched aquamarine), hardware keyboard pass-through via the
  key-interceptor accessibility service (`launch/KeyCapture.kt`, `docs/omarchy/r4-input-research.md`).
  A hardware MOUSE has never been tested (`r4-input-report.md` "Not proven").
- The session runs in a foreground service (`proot/ProotService.kt`).

The target device is Phil's phone, not the tablet: a Samsung Galaxy Z Fold8 (Samsung, foldable,
Android 17 / One UI, Snapdragon with an **Adreno 840** GPU). The tablet is a Snapdragon 8 Elite
(Adreno 830) on HyperOS. Samsung phones have **DeX** for external monitors.

## Questions to answer, each with sources (AOSP code at a named tag/branch, Samsung developer
docs, Termux:X11 source in the submodule, Mesa source at the revision the guest uses, issue
trackers), or marked as a guess

1. **External display on Android 16/17 for a third-party app.** What happens when a phone is
   connected to a monitor over USB-C DisplayPort (or a dock with HDMI): mirroring vs a second
   display; Android 16+ "desktop experience / connected displays"; how an app can put an
   Activity full screen on the external display (`ActivityOptions.setLaunchDisplayId`,
   `DisplayManager` listener, `Presentation`), what permissions or display flags allow it (trusted
   / public displays, `FLAG_...`), and whether the activity can be MOVED between displays at run
   time while keeping its process (what config changes fire, whether the Activity is recreated).
2. **Samsung DeX** on current One UI (the Fold8 generation): how a normal app runs in DeX
   (windowed, maximise, full screen, "launch in DeX"), what DeX does with the Meta/Super key and
   with mouse input, whether DeX can be turned off so the monitor becomes a plain second display,
   and Samsung's developer guidance for DeX-aware apps (manifest meta-data, `isDeXEnabled`-style
   checks, resizable activity, density on the monitor). Is there a way for the app to detect
   "docked" (external display + keyboard/mouse)?
3. **Termux:X11 and a second display.** In the submodule: how `MainActivity`/`LorieView` size the
   X screen, what they do on a display, density or configuration change (configChanges in the
   merged manifest, `onConfigurationChanged`), whether the X server survives the activity being
   recreated on another display (it lives in the app process; check), how the hardware MOUSE path
   works (`TouchInputHandler`, pointer capture, relative vs absolute, the cursor drawn by
   Hyprland), and anything that assumes the default display.
4. **The GPU.** Does the guest's Mesa (Turnip / freedreno over KGSL, revision in
   `<scratch>/omarchy/upstream/BlackFireAlex-omarchy-android-0f4cee8/manifest/components.lock`,
   source `lfdevs/mesa-for-android-container`) support **Adreno 840**? Find the chip id tables
   (`freedreno_devices.py` or equivalent) at that revision and upstream Mesa main. If not, what
   happens (software fallback? Hyprland refuses?) and what it would take.
5. **Omdroid changes needed**, concretely, for this flow:
   (a) dock: monitor + keyboard + mouse connected -> Omarchy full screen on the monitor, `desktop`
   UI, scale for the monitor's density, keyboard and mouse working, the phone screen free for
   Android (or blank);
   (b) undock -> Android is normal; the Omarchy session keeps running in the background
   (foreground service) and can be opened on the phone screen in `mobile` UI;
   (c) the UI mode switching LIVE with the display (today it is read at session start: say what
   a live switch needs: shell restart with the other plugin set, Hyprland config reload, scale).
   Name the files and functions to change, new components, the Android APIs, and the risks.
6. **Milestones**: an ordered plan of 4-6 milestones, each small enough for one agent round, with
   what it proves and the exact acceptance test (what to plug, what must appear, what to measure),
   and which ones need Phil's phone versus can be done on the tablet (does the Xiaomi Pad 8 Pro
   output video over USB-C? find out). Mark the first one that can start without the phone.

## Rules

- Every claim cites a source (file:line in a repo you read, a URL with the version/date, an AOSP
  path at a tag) or is marked as a guess. No device commands, no edits outside your file, do not
  post, push or comment anywhere. Never `pkill -f`.
- Keep the file to about 400 lines; a table per question is welcome.

Final reply, at most 8 lines: the feasibility verdict in one sentence, the biggest blocker, the
GPU answer, the first milestone, and the file path.
