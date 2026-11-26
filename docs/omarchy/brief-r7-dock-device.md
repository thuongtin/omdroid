# Brief R7-DOCK-DEVICE: prove docking on the tablet (milestones M1-M3), fix what breaks

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. The adb serial is given in your launcher prompt; export it as
`TABLET_SERIAL` and never write it into any repo file.

Repo: `<repo>` (branch `main`, read `AGENTS.md`). Read whole,
first: `docs/omarchy/r7-dock-research.md` (§3, §5, §6 milestones), `docs/omarchy/r7-dock-report.md`
(what the code round built: `launch/DockState.kt`, `DockStatusReader`, `DockMonitor`,
`DisplayLaunch`, `UiMode.kt`, the `KeyboardCapture.java` in the `termux-x11` submodule, the
`omarchy-watch.py` live switch), `docs/omarchy/launch-contract.md` §8, and the device tools in
`docs/omarchy/tools/` (`probe.sh`, `coldstart.sh`, `sx.sh`, `hc.sh`, `shot.sh`, `screen.sh`,
`install.sh`, `gpush.sh`). Earlier device rounds show how they are used:
`docs/omarchy/r5-touch-device-report.md`, `docs/omarchy/r5-mobile-ui-device-report.md`.
Report, created in your FIRST calls and updated after every step:
`docs/omarchy/r7-dock-device-report.md` (STATUS TABLE T0-T8, PASS / FAIL / PENDING plus the
number or the log line). Scratch: `<scratch>/omarchy/r7/device/`.

## The goal (Phil)

"When I plug my phone into a monitor, keyboard or mouse, I can use Omarchy. When I unplug it and
go out and about I can use Android and optionally Omarchy." Phil's phone (Galaxy Z Fold8) already
runs Omdroid 0.0.15 well: he tests the phone himself. This round proves the dock flow on the
Xiaomi tablet first, with Android's simulated secondary display, so the build Phil gets for his
monitor test has already survived plug and unplug once.

## The build

Parent-built combined test APK (dock + sudo + yay + the broker uid fix):
`<mesh dir>/omdroid-0.0.15-test2.apk`,
sha256 `a239a8c5134f1d79ed0cbcd669d0b1049bc9cc5f8bf34aa9506c66a12fc407a0` (see the last section of
`docs/omarchy/r6-sudo-report.md` for how it was made). No sibling edits this checkout now; the
sibling rule below still protects its files. Install it with
`docs/omarchy/tools/install.sh` (update install: the guest stays). If you fix code (T7), build
your own: `rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug
--console=plain` in the FOREGROUND, and copy the APK to your scratch dir in the same command
(another agent may build in this checkout and `assembleDebug` clears the output dir).

## Steps

**T0. Baseline.** Tablet awake and unlocked (`dumpsys window | grep -i keyguard`; if locked, stop
and say so), stay-awake value read and recorded, then set to `2` for the round. Install the APK,
record the install sha. Cold start (`coldstart.sh 1`), `probe.sh -q` PASS. Undocked: the session
is in the `mobile` UI, `adb logcat -d | grep -E 'dock:|launch:'` shows the dock lines the code
writes when no monitor is present (quote them), touch device listed (`hc.sh j/devices`),
key-capture still enabled. Any regression against 0.0.15 here is a FAIL to fix first.

**T1. Find how a second display works on this tablet.** Simulated display:
`adb shell settings put global overlay_display_devices 1920x1080/160` (Developer options ->
Simulate secondary displays). Record: `dumpsys display` (the new display id, flags: PRIVATE?
PRESENTATION? `FLAG_TRUSTED`?), whether the platform has `FEATURE_ACTIVITIES_ON_SECONDARY_DISPLAYS`
(`pm list features`), and whether an activity can be started there at all
(`am start --display <id> -n com.android.settings/.Settings`, then send it back home). If HyperOS
needs it, try `settings put global force_desktop_mode_on_external_displays 1` and/or
`enable_freeform_support 1` (record every setting you change and restore it in T8). Write down
which combination lets an app run on the second display.

**T2. Dock (M1 + M2).** Start from a running undocked session with ONE `foot` window open (record
its pid and the Hyprland client count, the proot/X-server pids, `sx.sh` X root size). Add the
simulated display. Measure, with timestamps:
- logcat `dock: docked display=<id> ...`, `dock: ui desktop written`, `launch: handover ...
  on-target=...`;
- where the X activity is (`dumpsys activity activities | grep -E 'Display #|MainActivity'`);
- the X root size (must equal the simulated display, rounded as the contract says), cage window
  and Hyprland monitor size (`hc.sh j/monitors`);
- the guest: `/tmp/omarchy-watch.log` `ui mode mobile -> desktop`, shell restarted once, the
  `desktop` UI on screen (bar height, no Omamobile plugins in the scan file);
- the foot window still there (same pid), session pids unchanged (no session restart);
- a screenshot of the second display (`screencap -d <display id>`, or `dumpsys SurfaceFlinger
  --display-id` to find the id; record what worked) and one of the tablet screen. View both
  yourself and say in one line each what they show.
- the time from the `settings put` to the desktop UI being ready.

**T3. Undock (M2).** Remove the display (`settings put global overlay_display_devices ""`).
Measure the same list in reverse: `dock: undocked`, `ui mobile written`, the X activity back on
display 0 (or gone; then whether opening Omdroid brings the same session back), X root = tablet
size, mobile UI, foot window and pids unchanged.

**T4. Pin.** `echo desktop > ~/.config/omdroid/ui-pin` in the guest: undocked stays `desktop`; dock
and undock once: `ui` never written by the host (logcat says so). `echo auto` -> follows again.
Restore `auto`.

**T5. Repeat.** Dock and undock 5 times in a row (wait for each switch to finish): no crash, no
session restart, no stuck shell, no `FATAL`/`AndroidRuntime` in logcat, the watcher's rate limit
never leaves the wrong UI on screen. Record the switch times.

**T6. Input while docked.** With the desktop on the simulated display: a synthetic keyboard
(the uhid method from `docs/omarchy/r4-input-report.md`) — `SUPER+Return` opens a terminal on the
docked desktop, typing reaches it, `SUPER+W` closes it. Record which keyboard path delivered SUPER:
the Android keyboard-capture API (`KeyboardCapture` log line, API level of this tablet) or the
accessibility interceptor. Touch on a simulated display is not meaningful (the overlay is drawn on
the tablet screen): say so, do not test it.

**T7. Fix.** Every FAIL in T0-T6 gets a root cause and a fix in the files listed below, a unit test
when the logic is pure, the gate (`./gradlew :app:compileDebugKotlin :app:test :app:lintDebug
--console=plain` and `python3 docs/omarchy/tools/unit-count.py`, must stay `failed 0` and grow
from 98 when you add tests, lint 0 errors), a commit, a rebuilt APK and the failed step re-proven
on it. Commit each fix the moment its gate passes.

**T8. Hand-off and cleanup.** Restore every setting you changed (overlay displays empty, desktop
mode / freeform settings to their recorded values, stay-awake to its recorded value, read back),
`screen.sh reset` if you used it, session left running undocked in `mobile` UI, `probe.sh -q` PASS.
Copy the final APK to `<scratch>/omarchy/r7/device/omdroid-dock-final.apk` with its
sha256 and commit. Then complete the report:
- "Manual test for Phil (Galaxy Z Fold8 + real monitor)": 10-14 steps — install, plug the monitor
  (DeX on and DeX off if One UI allows it), what must appear, keyboard incl. SUPER, mouse left
  click / right click / wheel, a terminal window open while unplugging, replug, the pin, and the
  exact log lines to grep (`adb logcat -s Phoshdroid:*`, the guest's `/tmp/omarchy-watch.log`).
- "Risks still open" and "Not verified" (what only the phone and a real monitor can prove:
  Samsung DeX, `keep_process_alive`, a real mouse, monitor density, the window moving vs
  re-launching).
Also fill the D7 sections of `docs/omarchy/r7-dock-report.md` (they read PENDING) by pointing to
your report's sections, so neither file is left with PENDING placeholders.

## Hard rules

- **A sibling agent works in this checkout now** (yay/makepkg round). It owns
  `rootfs/overlay/etc/phoshdroid/{sudo,fakeroot,yay,omdroid_root.py,omdroid-rootd.py,start.sh}`,
  `rootfs/package-omarchy-rootfs.sh`, the `syncGuestOverlay` block of `app/build.gradle.kts`,
  `docs/omarchy/tools/rootd-selftest.py`, `docs/omarchy/r6b-yay-report.md` and the sudo/yay
  paragraphs of `README.md`. Never edit, stage or revert those, even when `git status` shows them
  modified. Its in-flight files end up in any APK you build; that is expected.
- Files you may change: `app/src/main/**`, `app/src/test/**`, `termux-x11/**` (branch
  `phoshdroid-integration`, commit there, then the pointer), `rootfs/overlay/etc/phoshdroid/{omarchy-watch.py,omdroid-ui.sh,fit-x11.py,session-child.sh}`,
  `docs/omarchy/launch-contract.md` §8, README's "Docking" section, your report,
  `docs/omarchy/r7-dock-report.md`, `docs/omarchy/tools/**` (new tools; existing ones only to fix a
  bug, said in the report). Comments added to any shell script must contain no apostrophe.
- **Commit each finished step at once** with exactly its paths (`git add <paths> && git commit`);
  never `git add -A`, never `git stash`. No push, tag or release.
- Only the tablet. Never touch any other adb device. Never `pkill -f`; kill only PIDs you started.
  No `sleep N; tail` poll loops longer than needed for one switch.
- If a command waits on an approval, do not retry or rephrase it; note it and go on.
- If your call budget runs low, write the report state, restore the tablet settings (T8 list) and
  commit before anything else.

Final reply, at most 10 lines: T0-T8 with the decisive number or log line each, how the X activity
reached the second display (moved or re-launched), the switch times, the fixes with commits, the
final APK path and sha256, and what Phil must test on the phone.

## AMENDMENT (parent, before launch) — read this before T0

- **Two adb devices are attached**: the tablet (serial in your launcher prompt) and Phil's phone
  over wireless adb. Never run any command against the phone, not even a read. Every adb call
  goes through `-s $TABLET_SERIAL` or the tools in `docs/omarchy/tools/` (they require it).
- **Install `<mesh dir>/omdroid-0.0.15-test2.apk`** (sha256 `a239a8c5…12fc407a0`,
  see "The build" above). It also carries the sudo broker fix; after the cold start in T0 run
  `sudo id` in the guest once (`sx.sh 'sudo id'`) and record the line: Phil saw
  `omdroid-rootd: peer is not this app` on the previous build, this one must print `uid=0(root)`.
  If it does not, quote `/tmp/omdroid-root/rootd.log` and `/tmp/root-broker.log`, record FAIL, and
  carry on with the dock steps (sudo is not this round's fix).
- **Gradle is impaired on this machine right now**: `~/.gradle/caches` is an empty root-owned mount
  (Phil's disk move in another session, not yours to repair; do not touch it, `/mnt/data` or
  `gradle.properties`, which Phil's session changed to a 4 GB heap). If T7 needs a build, run gradle
  with `GRADLE_USER_HOME=<scratch>/omarchy/r7/gradle-home` (it downloads its own
  cache once) and the heap the project file sets. If `assembleDebug` runs out of memory there, do
  not raise the heap: for guest-only fixes (files under `rootfs/overlay/etc/phoshdroid/`) patch the
  test APK the way the last section of `docs/omarchy/r6-sudo-report.md` describes (replace the
  changed `assets/guest-overlay/...` entries, `zipalign -P 16 -f 4`, `apksigner` with
  `~/.config/.android/debug.keystore`, alias `androiddebugkey`, pass `android`), or simply
  `gpush.sh` the file for the re-test and say so; for Kotlin fixes commit them with unit tests and
  mark the device re-proof PENDING with the reason.
- The scratch directory `<scratch>/omarchy/r7/` was pruned by a cleanup; create
  `r7/device/` yourself.
