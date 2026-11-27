# R11 S5 (verify): the "Not verified yet" items, proved on the tablet

Branch `r11/verification` from `90d7494`. Report and tools only; no source edits.
Build under test: the R10 integration APK (sha256 `bef783d7a7aa1806bd72e118ff0f68b50ad670a22d42f980fe67e86977dfa52e`,
1,124,728,775 B), built from `f2584e7`. Every phase records the installed sha256 first.

Evidence labels: **measured** (command or script given, device), **read** (file:line), **estimated**.
A view of a screenshot is written as "viewed:" with one line of what was seen.

## STATUS TABLE

| # | Item | Status | Proof |
|---|---|---|---|
| V1 | AQ_TRACE commit rhythm (`r10-damage.md` check 5) | PENDING | |
| V2 | Correctness vs forced repaint, 3 runs of toast / open-close / scroll / rotation | PENDING | |
| V3 | `onTrimMemory` levels and survival | PENDING | |
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

(one section per item, written the moment its proof exists)

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
