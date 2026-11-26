# Brief R4-TOUCH: taps on the Omarchy bar do nothing (device round)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`.

Repo: `<repo>` (branch `main`, read `AGENTS.md`).
Tools: `docs/omarchy/tools/` (run them from that directory). Every tool needs
`export TABLET_SERIAL=<adb serial>` first. Never write that serial into any repo file.
Your report, created in your FIRST calls and updated after EVERY item:
`docs/omarchy/r4-touch-report.md`, starting with a STATUS TABLE (rows T0-T4, `PENDING` until
proven, then `PASS`/`FAIL`/`BLOCKED` plus the numbers). Write a row in the same call that produced
its numbers.

## The bug (reported by Phil, the owner, using the tablet)

On the Omarchy bar at the top of the screen, taps do nothing: the workspace numbers do not switch
workspace, the Omarchy button at the top left does not open the menu, and the tray icons at the
top right do not react. Nobody has measured where the taps are lost.

Facts you can rely on:
- The bar is the layer surface `omarchy-bar`, 1600x26 logical at scale 2 = screen rows 0-51 (the
  X view starts at row 0; rows 1971-2135 are Android's extra-key bar). Item centres in screen
  pixels, read by the parent from a screenshot, all at y = 26: Omarchy button x = 45; workspaces
  1-5 at x = 87, 128, 170, 211, 253; right side: network icon 3052, volume icon 3105, display
  icon 3160.
- Termux:X11 runs with `touchMode = "3"` (set in `LauncherActivity.kt`, the
  `getDefaultSharedPreferences(this).edit()` block). In
  `termux-x11/app/src/main/java/com/termux/x11/input/TouchInputHandler.java` that is
  `InputMode.TOUCH`, which installs `NullInputStrategy`: touches are sent to the X server as
  touch events, not turned into pointer clicks. `"2"` is simulated touch (taps become pointer
  clicks), `"1"` is trackpad.
- Chain: Android -> Xlorie X server (in the app) -> cage (wlroots 0.20, x11 backend) -> Hyprland
  0.56.1 (nested, aquamarine wayland backend, Lua config) -> Quickshell (Omarchy shell).
- A sibling agent is researching the same chain from source, read-only. Its notes appear at
  `docs/omarchy/r4-touch-research.md`; read them when they exist. They are hypotheses; your
  device numbers decide.
- Upstream guest files, read-only on this machine: `<scratch>/omarchy/upstream/`
  (`usr/share/omarchy/shell/` is the shell QML, `usr/share/omarchy/default/hypr/` the Hyprland
  config, `usr/share/omarchy/bin/` the commands). Grep there for Lua dispatcher syntax
  (`hl.dsp.focus`, workspace switching) instead of guessing it.

## Hard rules

- Device: ONLY `<tablet serial>`. Another device (a phone) may be attached: never touch it.
- **The tablet has a PIN lock.** Never type or tap anything while the keyguard shows (that would
  be a PIN guess). Check with
  `adb -s $TABLET_SERIAL shell dumpsys window | grep isKeyguardShowing`.
- Phil may be using the tablet. Do what the brief needs and nothing else on it.
- NEVER `adb install`, `adb uninstall`, `pm clear`, or delete under `files/usr`. Install only with
  `./install.sh` (it drives the on-device installer). NEVER run the packager
  (`rootfs/package-omarchy-rootfs.sh`).
- Gradle only in the FOREGROUND (never as a background job: a background Gradle daemon was stuck
  for 9 minutes in a 4 GiB memory cap earlier today). To build an APK:
  `rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug -Dorg.gradle.jvmargs="-Xmx8g -Dfile.encoding=UTF-8" --console=plain`
  (about 30 s), then `./install.sh` (about 4 minutes, give it a 600 s timeout).
- Files you may change: `rootfs/overlay/etc/phoshdroid/**`, `rootfs/package-omarchy-rootfs.sh`
  and the `syncGuestOverlay` list in `app/build.gradle.kts` (a new overlay file must be added to
  BOTH, see AGENTS.md); in `LauncherActivity.kt` only the Termux:X11 preferences block;
  `termux-x11/app/src/main/java/com/termux/x11/input/**` and
  `termux-x11/app/src/main/java/com/termux/x11/LorieView.java`; `docs/omarchy/tools/**`; your
  report. A guest payload file (Hyprland config, shell QML) is never edited in place: if the fix
  needs one changed, ship the change as an overlay file the packager installs, and copy the
  original to `<scratch>/omarchy/r4/orig/` first. A sibling owns keyboard and
  mouse pass-through: do not change keyboard or external-mouse handling.
- No git command that changes anything (the parent commits).
- Never `pkill -f` / `pgrep -f | kill` on this machine. One change per boot; say which change
  produced which numbers.
- Do not spend calls on `sleep N; tail`.
- If a terminal command is BLOCKED waiting for approval, do not retry or rephrase it; note it and
  go on.
- Scratch: `<scratch>/omarchy/r4/touch/`.

## Items, in this order

### T0. Unlock, stay awake, install the release
1. If the keyguard shows, wait for Phil to unlock it with at most four calls of
   `timeout 380 bash -c 'while adb -s $TABLET_SERIAL shell dumpsys window | grep -q "isKeyguardShowing=true"; do sleep 10; done' || echo STILL-LOCKED`.
   Still locked after four: mark T0 `BLOCKED (locked)`, write the report and end your turn.
2. Record `adb -s $TABLET_SERIAL shell settings get global stay_on_while_plugged_in` in the report,
   then `adb -s $TABLET_SERIAL shell svc power stayon usb` so the screen does not lock again. At the
   end, and before you stop for any reason, restore it (`svc power stayon false` when the
   recorded value was 0) and put the read-back in the report.
3. Install the published release:
   `./install.sh <repo>/app/build/outputs/apk/debug/omdroid-0.0.14-alpha.apk`
   (sha256 `ee8cdaf9…b59f`; expect `INSTALL: PASS`). Then `./coldstart.sh 2 --tag r4-base`
   (600 s timeout). Record per run: handover, desktop, and from logcat
   (`adb -s $TABLET_SERIAL logcat -d -s Phoshdroid:*`) every `launch: decision`, `launch: guest-overlay`
   and `launch: ready` line. If the install fails, say so and work on the installed build.

### T1. Reproduce, with numbers
X display on top, probe PASS. For each of the nine bar targets, and for each input kind below,
record whether the expected thing happened:
- signals: a workspace number -> `./hc.sh j/activeworkspace` shows that id; the Omarchy button ->
  `./hc.sh j/layers` gains a layer (record its namespace; close it with `./sx.sh 'omarchy-menu close'`);
  a tray icon -> any new layer or popup in `j/layers`, or nothing (record which).
  Go back to workspace 1 between taps.
- input kinds: touch tap `adb -s $TABLET_SERIAL shell input touchscreen tap X Y`; long touch
  `adb -s $TABLET_SERIAL shell input touchscreen swipe X Y X Y 150`; mouse click
  `adb -s $TABLET_SERIAL shell input mouse tap X Y`. Also try the touch tap at y = 45 for two targets
  (rule out the top screen edge).
- control: open two foot windows (`./hc.sh '/dispatch hl.dsp.exec_cmd("foot")'` twice), touch-tap
  the one that is not focused, record `./hc.sh j/activewindow` before and after, and
  `./hc.sh j/cursorpos` before and after a touch tap.
Put the result in one table (target x kind). This is the baseline; keep it.

### T2. Find where the touch is lost
Stop as soon as the cause sits in one place a fix can cover. Suggested order, cheapest first:
1. `./hc.sh j/devices`: does Hyprland have a touch device, a pointer, a keyboard? Names?
2. Does the bar's client receive touch? Find how the shell is started
   (`usr/share/omarchy/bin/omarchy-launch-shell` upstream), restart only the shell with
   `WAYLAND_DEBUG=1` and its stderr in a file under `/tmp` (from inside the session with
   `./sx.sh`), do ONE touch tap on workspace 2, then restart the shell normally. Count
   `wl_touch` and `wl_pointer` events in that file, and the seat capabilities the shell was
   offered. Remove the trace file afterwards (it can be large).
3. If nothing reaches the shell: the same question one level up (Hyprland's own log, its touch
   handling for layer surfaces, whether cage offers Hyprland a touch device).
4. If touch reaches the shell but nothing happens: read the bar's QML (`Ui/BarIconButton.qml`,
   `Ui/BarWidget.qml`, `plugins/bar/`) for what a click requires (hover, `containsMouse`,
   accepted buttons, TapHandler vs MouseArea).
Write the finding as a paragraph with the log lines that prove it.

### T3. Fix and prove
Fix it at the layer the evidence points to, the smallest change that works. If direct touch
cannot be made to work on the bar without patching a compiled component (Hyprland, Quickshell,
cage), the fallback is Termux:X11's simulated touch (`touchMode = "2"`): then also measure what
it costs (two-finger gestures, drag in a window, the pointer position after a tap) and say so.
Iterate guest-side changes with `./gpush.sh` first; a host change needs a build + install.
PASS needs, on the final build or guest: all nine bar targets react to a touch tap; the control
(focus change by tap) still passes; a mouse click on the bar still works; `./probe.sh` PASS;
and, if Kotlin changed, `./gradlew :app:test --console=plain` green with
`python3 docs/omarchy/tools/unit-count.py` printed. If you changed a guest file, show the device
copy and the repo copy have the same sha256, and if the file reaches the device through the APK
(`launch: guest-overlay updated ...`), show that line.

### T4. Report and clean up
Close the windows you opened, restore stay-awake (T0.2) and put the read-back in the report.
Final sections: "Cause" (one paragraph + proof), "Change" (files, what and why), "Cost" (what
the fix changes for the user), "Not verified", "Files changed".

Final reply, at most 10 lines: one line per T-row with its decisive number, the cause in one
sentence, the files changed, the stay-awake read-back, and anything you could not do.
