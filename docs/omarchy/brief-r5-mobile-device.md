# Brief R5-MOBILE-DEVICE: the Omamobile mobile UI on the tablet: prove it, look at it, fix it

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. You can see images: view every screenshot you take and judge it.

Repo: `<repo>` (branch `main`, read `AGENTS.md` first).
Read whole: `docs/omarchy/r5-mobile-ui-report.md` (what was built, the switch, the stubs, and the
section "What the device phase must check", which is your checklist), then skim
`docs/omarchy/r5-omamobile-research.md` §1 and §4.
Report, created in your FIRST calls and updated after every step:
`docs/omarchy/r5-mobile-ui-device-report.md` (STATUS TABLE rows M0-M10, `PENDING` until proven).
Scratch: `<scratch>/omarchy/r5/device/` (screenshots, logs).

## The device

- The tablet (Xiaomi Pad, Android 16, HyperOS). `export TABLET_SERIAL=<tablet serial>` in your shell;
  **never write that serial into a repo file**. Tools: `docs/omarchy/tools/` (every one needs
  `TABLET_SERIAL`): `install.sh <apk>` (tries `pm install` from `/data/local/tmp`, prints
  `INSTALL: PASS` + sha256), `coldstart.sh`, `probe.sh -q` (`VERDICT: PASS`), `hc.sh`
  (hyprctl, e.g. `./hc.sh j/devices`, `./hc.sh j/layers`, `./hc.sh j/clients`), `sx.sh` (run a
  command inside the session), `gx.sh` (run in the guest), `gpush.sh` (copy a file into the
  guest), `shot.sh` (screenshot), `bartest.py`, `xtap.py`, `focustest.py`. Read a tool's head
  before its first use.
- You own the tablet for this whole run; nobody else will install anything.
- The screen must be unlocked. If `dumpsys window` shows `isKeyguardShowing=true`, never enter or
  guess a PIN: write `BLOCKED (keyguard)` and wait with bounded checks (at most 4 x 380 s).
- Record `settings get global stay_on_while_plugged_in` first, set it to `2` while you work,
  and restore the recorded value at the end (read it back).
- Input: finger taps arrive as mouse clicks (Termux:X11 simulated touch, `touchMode = "2"`);
  `adb shell input touchscreen tap X Y` at Android pixels clicks there (proven: 9/9 bar targets).
  Android pixels = X root pixels (3200x1971 root above a 165 px key bar); Hyprland's logical
  size is 1600x985 (scale 2). Find out what `input touchscreen swipe` and a long-press-drag
  become under simulated touch (a drag, a pointer move, a scroll?) and record it: the dock
  swipe-up, the switcher flick and the back gesture depend on it.

## The build

`<scratch>/omarchy/r5/device/omdroid-mobile-2a64277.apk`, sha256
`ebd4991dc60fe69c695d2bb9cb935b6b912f0d91605a8101f15c9d2ef95bf065`, built from commit
`2a64277` (tap fix + keyboard capture + the mobile UI). The guest's `/etc/phoshdroid` scripts
and the `omamobile/` tree are synced from the APK into the installed guest on every start
(`GuestOverlay`), so no repack is needed. Do not build APKs yourself.

## Steps

**M0.** Unlock check, stay-awake record, install the APK (`INSTALL: PASS`, sha matches), cold
start (`coldstart.sh`), `probe.sh -q` PASS. Screenshot the first desktop and look at it.

**M1-M9.** The nine checks of the report's "What the device phase must check", in order, each
with its evidence (numbers, log lines, screenshot path plus your one-line verdict of what the
image shows). Finding the shell's log is part of M2 (`sx.sh`, `gx.sh`; Quickshell keeps logs under
the runtime dir or prints to the session log).

**M10. Look and fix.** Phil asked for "a more mobile friendly UI". After M1-M9, judge the result
as a touch UI on a 13-inch landscape tablet at 1600x985 logical: can every control be hit with a
finger, is the type readable, does the bar layout make sense without a phone camera cutout, does
anything overlap, clip or sit off-screen. For each defect: fix it, re-test it, screenshot it.
Rules for fixes:
- Fix in the files you own: `rootfs/overlay/etc/phoshdroid/omdroid-ui.sh` and
  `rootfs/overlay/etc/phoshdroid/omamobile/**`. Prefer Omdroid-side files and config (the theme
  values, `shell.json` entries written by `omdroid-ui.sh`) over edits to the vendored upstream
  QML; every upstream file you do change gets a line in `omamobile/SOURCE.md`.
- Iterate on the device without rebuilding: `gpush.sh` the changed file into the guest and
  restart only what is needed (the shell, or a cold start for `omdroid-ui.sh` changes). The
  committed file and the pushed file must be the same bytes (sha256 both) before you call a fix
  proven.
- `bash -n` every shell file you change. `AGENTS.md`: no apostrophes in shell comments of
  `start.sh` (you do not own `start.sh`; do not edit it).
- **Commit each proven fix right away**, with exactly its paths:
  `git add <paths> && git commit -m "fix(rootfs): <what>"`. Never `git add -A` or `git add .`:
  another agent has uncommitted files in this tree (`rootfs/patches/`, `rootfs/build-aquamarine.sh`,
  `docs/omarchy/r5-touch-patch-report.md`), never stage, edit or delete them.
- A defect that needs real touch (multi-finger, edge swipe Android steals) is recorded, not
  worked around with hacks; real touch is being built separately.
- Cap the fix loop at about 6 rounds; list what remains.

**Finish.** Leave the session in `mobile` mode with no test windows open, restore stay-awake,
`probe.sh -q` PASS, screenshot the final desktop and the quick-settings sheet as the two images
Phil will see first: name them `docs/screenshots/mobile-desktop.jpg` and
`docs/screenshots/mobile-quicksettings.jpg` (JPEG, quality 85, full resolution), and commit them
with the report.

## Report sections

STATUS TABLE (M0-M10: PASS / FAIL / BLOCKED + the decisive number or verdict), one section per
row with commands and output, "Screenshots viewed" (every path with its one-line verdict),
"Fixes" (each with its commit sha), "Input under simulated touch" (what tap, swipe, long press,
drag become), "What still needs real touch", "Not verified".

## Hard rules

- Never touch `app/**`, `termux-x11/**`, `rootfs/patches/**`, `rootfs/build-aquamarine.sh`,
  `rootfs/package-omarchy-rootfs.sh`, `app/build.gradle.kts`, `start.sh`, or the other agent's
  report. No gradle. No `git push`, no release, no GitHub writes.
- Never `pkill -f`; kill only PIDs you started, by exact PID. No `sleep N; tail` polling loops
  longer than one bounded wait.
- If a command waits on an approval, do not retry or rephrase it; note it and go on.

Final reply, at most 10 lines: M0-M10 with the decisive fact each, the fixes with shas, what
taps/swipes become, what still needs real touch, the two screenshot paths.


---

## CONTINUATION (added by the parent after your first turn hit the call cap)

Your first turn landed M0-M5 and commit `5030297` (Switcher fix); M6 was measured but not
written. Carry on from there in this turn, in this order, and write each row the moment its fact
exists:

1. **Write M6 into the report now** from what you measured (summon, pill hold-swipe, card tap,
   flick close 2 -> 1; dock swipe-up did not open it; cards show icon + title). Also fill the
   "Input under simulated touch" section from your first reply. Commit the report.
2. **Install the new APK first, before any cold start.** A cold start re-syncs every
   `/etc/phoshdroid` file from the APK, so the old APK (`2a64277`) would put the crashing
   `Switcher.qml` back. The parent built one from `5030297`:
   `<scratch>/omarchy/r5/device/omdroid-mobile-5030297.apk`, sha256
   `a0f1cb6b3676fcdfd5a14639823c164227c01b552473f64d0bf240bfc7a3b37a` (its `Switcher.qml` sha256
   starts `afcee6cc`, same as the repo). `install.sh` it, cold start, `probe.sh -q`.
   From now on, after every fix you push with `gpush.sh`, remember that a cold start reverts it
   until the APK carries it: either re-push after the cold start, or (allowed in this turn only)
   rebuild yourself in the foreground with
   `rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug --console=plain`
   (600 s timeout; never in the background) and install that. The final M7-M10 proof must run on
   an APK that contains every committed fix (state its sha256).
3. **M7, M8, M9** as the brief says.
4. **M10 fixes, in this order** (your own findings), each proven on the device and committed:
   a. the pill's QML long-press fires `voice start` before a hold-then-drag can begin, and voice is
      not ported here: remove or disable that long-press in Omdroid (so the hold starts the drag);
   b. the 14 of 19 drawer apps with no icon (`Icon=basecamp`, PNGs only under
      `~/.local/share/applications/icons/`): find how the stock Omarchy launcher resolves them and
      make the drawer resolve them the same way (an Omdroid-side fix is preferred, e.g. a path
      or icon-theme entry written by `omdroid-ui.sh`, over editing upstream QML);
   c. truncated quick-settings tile labels at 16 px type: fewer columns or a wider sheet on a
      landscape screen this wide, whichever reads better (look at both);
   d. the dock swipe-up that did not open the switcher: one look at why; fix if it is ours,
      record it if it needs real touch.
   Then your own look at the whole UI as the brief's M10 asks.
5. **Finish** exactly as the brief says (mobile mode, no test windows, stay-awake restored to
   `0` and read back, `probe.sh -q` PASS after a cold start, the two screenshots in
   `docs/screenshots/`, report committed).

Facts the parent checked for you: the stock Omarchy shell has no `ScreencopyView` anywhere
(`grep -rl ScreencopyView usr/share/omarchy/shell` in the bundle: 0 files), so the dmabuf v3/v4
crash is Omamobile's switcher only. `omarchy-watch.py` giving up after 3 restarts is the parent's
file: record it as a finding, do not edit it. Quick one-finger flicks (no hold) doing nothing is a
host input-mode limit the real-touch work addresses: record, do not work around it.
