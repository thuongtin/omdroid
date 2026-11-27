# R11 S5 (verify): the "Not verified yet" items, proved on the tablet

Branch `r11/verification` from `90d7494`. Report and tools only; no source edits.
Build under test: the R10 integration APK (sha256 `bef783d7a7aa1806bd72e118ff0f68b50ad670a22d42f980fe67e86977dfa52e`,
1,124,728,775 B), built from `f2584e7`. Every phase records the installed sha256 first.

Evidence labels: **measured** (command or script given, device), **read** (file:line), **estimated**.
A view of a screenshot is written as "viewed:" with one line of what was seen.

## STATUS TABLE

| # | Item | Status | Proof |
|---|---|---|---|
| V1 | AQ_TRACE commit rhythm (`r10-damage.md` check 5) | PARTIAL (phase 1 done; stall check awaits phase 6) | idle 0-rect 732/732, keypress rects 78, rhythm 60.0/s = the 60 Hz panel mode, control arm 100 % whole-surface; log: scratch `verify/p1-trace-trim.log`; see "V1" |
| V2 | Correctness vs forced repaint, 3 runs of toast / open-close / scroll / rotation | PENDING | |
| V3 | `onTrimMemory` levels and survival | PARTIAL (levels 5, 10, 15 PASS; 20-80 refused by Android for this process; phase 6 gets the text and the natural UI_HIDDEN) | see "V3" |
| V4 | Fresh-image path for the patched aquamarine | PENDING | |
| V5 | `sudo` interactive, Ctrl+C, `omarchy-pkg-add` | PENDING | |
| V6 | Session end and the error screen (H10-H15) | PENDING | |
| V7 | Pinch and three-finger touch | PENDING | |
| V8 | Owner-only checklist (written, not attempted) | PASS (written) | section "V8"; nothing here was run on any device |

## What changed

New tools only, under `docs/omarchy/tools/verify-*` (see "Tools"). No source file is edited.

## Tools

All in `docs/omarchy/tools/`, all new, none needs a source change. Every phase script runs under the
round's tablet lock and sources `verify-common.sh`, which pulls in the round's phase library (owner state
saved and put back on any exit, R10 build reinstalled and cold-started at the end). They need
`TABLET_SERIAL`, `R11` (the round scratch dir holding `device/phase-lib.sh`), `PHASE_OUT` and `TOOLS`
exported; no path or serial is hard-coded.

| File | What it is |
| --- | --- |
| `verify-common.sh` | shared helpers: installed-sha check and R10 reinstall, `arm_check` (what a session really runs: env switches + the mapped aquamarine library), `repaint_diff` (forced full repaint + exact diff + crop), uiautomator dump and tap, device/monitor/client one-liners |
| `verify-scrdiff.py` | exact screenshot diff (numpy): changed pixels, bbox, pixels outside the bar clock box, verdict ZERO / CLOCK_ONLY / CHANGED, and a before / after / diff crop to look at |
| `verify-ts.py`, `verify-trace.py` | timestamp a trace log inside the guest; summarise `commit damage N rect(s)` lines: counts of 0-rect / N-rect / whole-surface, commit-to-commit gap mean, median, p95, max, histogram, gaps over 100 ms |
| `verify-p1-trace-trim.sh` | V3 then V1 (two arms: shipped damage patch, and `AQ_WAYLAND_FULL_DAMAGE=1` as the positive control) |
| `verify-p2-repaint.sh`, `verify-scroll.sh` | V2: three runs each of toast, open/close, scrolling terminal stopped, rotation and back, plus two controls (a real change; `vfr=true` toast, the known stale case) |
| `verify-p3-session-end.sh` | V6: clean exit from inside, Hyprland killed after 30 s, a session that dies at launch (`session.env` with `exit 7`); each screen dumped, screenshotted, then Start again |
| `verify-p4-fresh-sudo.sh`, `verify-v5-*.sh` | V4 on a freshly extracted guest, then V5 on it (prompt with a typed answer, Ctrl+C during `sudo sleep 30` with a plain `sleep` as the injection control, `omarchy-pkg-add` and removal); the test guest is deleted at the end |
| `verify-p5-multitouch.sh`, `verify-mkuinput.py`, `verify-touchlog.py` | V7: N-finger `uinput` gestures (pinch, three-finger swipe), the touchlog overlay summary (ids, positions, simultaneous fingers, cancels), the workspace-swipe config and effect |


## Results

Build under test for every row: APK sha256 `bef783d7a7aa1806bd72e118ff0f68b50ad670a22d42f980fe67e86977dfa52e`
(the R10 integration build, `f2584e7`), read from the device at the start of each phase. The tablet
was Android 16, 4 KB pages, display mode 60.00 Hz (SurfaceFlinger `activeMode` vsyncRate 60.00 Hz
while Hyprland itself advertises 120 Hz through `AQ_WAYLAND_REFRESH_MHZ=120000`).

### V1, the AQ_TRACE commit rhythm (phase 1, 01:17-01:20 UTC; **measured**)

Instrument: `/etc/phoshdroid/trace` present, so `HYPRLAND_TRACE=1 AQ_TRACE=1`; `tail -F hyprland.log`
piped through `verify-ts.py` for 12 s windows; `verify-trace.py` summarises. Arm B = the shipped build;
arm A = `AQ_WAYLAND_FULL_DAMAGE=1` in `session.env` (the control that must turn every commit into the
whole-surface form). Both arms checked from the process: `/proc/<Hyprland>/environ` carries `AQ_TRACE=1`
(and the A switch only in arm A) and `/proc/<Hyprland>/maps` names `/etc/phoshdroid/lib/libaquamarine.so.13`;
`j/devices` lists `touch: ["wl_touch"]`.

| Window | commits | zero-rect | N-rect | whole surface | rate | per-block interval (min / median / max) |
| --- | --- | --- | --- | --- | --- | --- |
| B idle, no window | 732 | **732** | 0 | 0 | 62.6/s | 16.53 / 16.67 / 16.80 ms |
| B idle, foot open | 701 | **701** | 0 | 0 | 62.7/s | 16.58 / 16.66 / 16.76 ms |
| B typing into foot (26 keys over 12 s) | 641 | 563 | **78** (1 rect each) | 0 | 57.4/s | 16.56 / 16.69 / 21.97 ms |
| A idle (control) | 716 | 0 | 0 | **716** | 61.5/s | 16.01 / 16.67 / 17.31 ms |
| A typing (control) | 662 | 0 | 0 | **662** | 56.8/s | 16.04 / 17.25 / 22.10 ms |

- **Idle carries no damage: PASS.** Every idle commit of arm B reads `commit damage 0 rect(s)`; the same
  windows of arm A read `commit damage 1 rect(s) (whole surface)` for every commit, so the instrument
  does see the difference. The whole log of arm B holds 3 whole-surface lines (start-up), arm A 3,615.
- **A keypress carries rectangles: PASS.** 78 commits with one rectangle each during typing, 563 empty ones between.
- **Rhythm: PASS at the panel's rate.** 30-31 commits per flush block, 59.5-60.5 per second per block
  (16.67 ms), equal in both arms. The brief's "16.7 ms or 8.3 ms by the panel rate" resolves to 16.7 ms here:
  the panel was in its 60 Hz mode (`dumpsys SurfaceFlinger`, `activeMode ... vsyncRate=60.00 Hz`), and 120 Hz
  is what Hyprland advertises, not what the loop runs at.
- **Instrument limit found: the trace log is block-buffered.** Hyprland flushes `hyprland.log` in about 8 KB
  blocks (31 commits, 512 ms at idle), so the read time of a line is its flush time and the per-commit gap
  (the first version of `verify-trace.py` printed a median of 0.0 ms and 23 gaps of 516 ms) says nothing
  about stalls. The script now works per flush block: the mean interval and the time the loop lost in
  that block (`excess_ms`).
- **Stalls over 100 ms: no stall at idle; UNDECIDED while typing.** With a window open and nothing typed,
  the largest excess is 3-4 ms in 22 blocks (B). While typing, 6 of 20 blocks of arm B and 2 of 23 blocks of
  arm A lose 100-137 ms each, and at the block resolution that is eight missed 16.7 ms frames spread
  over a block as readily as one stall. It is not a regression of the damage patch by itself (the control
  arm shows the same shape), but "no stall over 100 ms" cannot be called PASS from this data. Phase 6 repeats
  it with a real-time instrument (a foot client's `wl_callback.done` events with `WAYLAND_DEBUG=1`), a
  continuous flood instead of typing, two injected stalls (SIGSTOP on Hyprland for 200 and 400 ms) as the
  positive control, and the arm order B A A B.

### V3, `onTrimMemory` (phase 1, 01:17 UTC; **measured**, plus **read** for the refusals)

`am send-trim-memory com.phoshdroid.app <LEVEL>` in ascending order on a fresh cold start (app pid 12238,
Hyprland pid 12533):

| Level | App log (`ProotService.onTrimMemory`) | Session afterwards |
| --- | --- | --- |
| RUNNING_MODERATE | `memory: onTrimMemory TRIM_MEMORY_RUNNING_MODERATE (5)` | same app pid, same Hyprland pid, X display on top |
| RUNNING_LOW | `... TRIM_MEMORY_RUNNING_LOW (10)` | unchanged |
| RUNNING_CRITICAL | `... TRIM_MEMORY_RUNNING_CRITICAL (15)` | unchanged; after all three `probe.sh` PASS, app pid 12238, Hyprland pid 12533 |
| HIDDEN, BACKGROUND, MODERATE, COMPLETE | no log line: `am` answers `Exception occurred while executing 'send-trim-memory'` (the phase kept two lines of the stack) | unchanged |

The refusal is Android's, not the app's. `ActivityManagerService.setProcessMemoryTrimLevel`
(`services/core/java/com/android/server/am/ActivityManagerService.java@android-16.0.0_r1:3156-3177`, **read**)
throws `Unable to set a higher trim level than current level` when the process already holds a level at or above
the requested one, and `Unable to set a background trim level on a foreground process` for any level from
UI_HIDDEN up while the process state is at or above IMPORTANT_FOREGROUND. The app is `TOP` with a
foreground service (`curProcState=2`, `mHasForegroundServices=true`, read from `dumpsys activity processes`).
An odd value like 7 is not an `am` level name at all. Phase 6 re-runs every level keeping the whole answer,
tries the background levels with the app on the home screen, and records the one level Android sends by
itself there (UI_HIDDEN, 20).

## V8, the owner-only checklist (do NOT attempt from an agent)

Nothing below was attempted. Each block says what the owner does and what PASS looks like, so one
report from him can flip the README "Not verified yet" line. Replace `<adb serial>` with the device.

**1. Clean install (an uninstall wipes the owner guest, 3.4 GB of the owner's files).**
Back up what matters from `~/` first (`adb exec-out run-as com.phoshdroid.app tar -c -C files/usr/var/lib/proot-distro/installed-rootfs/omarchy/home omarchy | gzip > omarchy-home.tgz`).
Uninstall the app, install the release APK (`docs/omarchy/tools/install.sh <apk>` with `TABLET_SERIAL=<adb serial>`), grant the all-files access it asks for, open it.
PASS: the progress screen counts the extraction (about 105 s on the tablet), the desktop hands over by itself, `probe.sh -q` says `VERDICT: PASS`, `launch: rootfs-extracted` shows no `skippedLinks`, `ls /usr/bin/ld` and `ls /usr/share/terminfo/x/xterm-256color` work in a foot shell (the 1,832 hard-link members), and `omdroid-repair-links.sh` finds nothing to repair.

**2. The phone: DeX, unplug, density** (manual test in `r7-dock-device-report.md`, steps 1-12).
Install the build over the old one, plug a monitor with DeX on Extend, open a terminal, run `seq 300`, unplug, plug again; then pin the UI (`echo desktop > ~/.config/omdroid/ui-pin`); also fold and unfold with a session open.
PASS: on dock the desktop is on the monitor with no black band and the same terminal; on unplug the mobile UI is back on the phone within about 30 s with `before-dock` still in the terminal; SUPER alone opens nothing on Android; fold and unfold keep the app pid and `probe.sh -q` stays PASS; the log has `dock: docked display=N`, `dock: undocked`, `x-view margins ...`. Send `adb logcat -s Phoshdroid:* | grep -E 'dock:|x-view|handover'` and `cat /tmp/omarchy-watch.log` from a terminal.

**3. Real fingers** (the six items of `r5-touch-device-report.md`, "What Phil should try with his fingers").
A quick flick up on the dock and on the home pill, back from the very edge with a dialog open, two-finger scroll and pinch in a Qt or GTK app, a quick-settings slider, text selection in foot, the soft keyboard after tapping a text field.
PASS: each works at the first try without a pause; write down the one that did not, and which edge (left or right) failed for back. A system gesture that wins at the very edge is Android's, not ours (`dumpsys input` shows the spy window).

**4. The keyboard cover** (`r4-input-report.md`, K6, steps 2-14, about 10 minutes).
PASS: SUPER alone does nothing on Android, SUPER+Return opens foot, SUPER+W closes it with no stray `w`, SUPER+Esc opens the guest system menu and not Android's back, Alt+Tab cycles windows, the pad moves exactly one arrow, right click and two-finger scroll work. Record `adb shell dumpsys input | grep -iA4 'keyboard\|touchpad'` once with the cover attached: the device names and whether the pad is `SOURCE_TOUCHPAD` are what no instrument here could read.

**5. Screen off and on behind a PIN.**
With the desktop up and foot open holding some typed text, press the power button, wait 10 s, wake the screen, unlock with the PIN by hand.
PASS: the X display is back on top within 3 s of the unlock (not the launcher and not a black screen), `adb shell pidof com.phoshdroid.app` is unchanged, the foot window and its text are intact, and `probe.sh -q` PASS. While the keyguard is up `probe.sh -q` and `hc.sh j/clients` should already say PASS and one window: the session survives behind it. An agent must never type the PIN, and `KEYCODE_SLEEP` from adb is what leaves the tablet on the keyguard.

**6. Installing over an existing Phoshdroid** (same package id, so the APK replaces the old app).
Keep a Phoshdroid build with its pmOS guest installed, then `docs/omarchy/tools/install.sh <omdroid apk>`.
PASS: the install is accepted (an `INSTALL_FAILED_UPDATE_INCOMPATIBLE` means a different signing key: then the only way is an uninstall, which loses the old guest, and the README line should say so), the app opens, Omdroid extracts its own guest and reaches `probe.sh -q` PASS, and the old data is neither crashed on nor silently deleted. Note the free space before: the old guest and the new one live side by side.

## Risks

(filled in at the end)

## What I did not do

(filled in at the end)
