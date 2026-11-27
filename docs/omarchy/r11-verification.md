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
| V2 | Correctness vs a forced full repaint, 3 runs of toast / open-close / scroll / rotation | **PASS (within the measured noise floor)** | redo `verify/p9-repaint2.log`: forcing step `damage_tracking` 0 then 2 proved (erases a painted 400x250 remnant, 54 damaged commits; the old bare `vfr=false` re-assert leaves it and produces 0 damaged commits of 183). 24 after-vs-forced comparisons: 15 ZERO, 2 clock only, 7 differing by 24 px of one level at x 3057-3082, y 88, which is the check's own repaint noise floor (same 22 px in `ctl3` with no event, in arm B and in the full-damage arm; the forced frame equals the pre-event frame in 9 of 9 returning cases); no stale content, no visible defect; see "V2, redo" |
| V3 | `onTrimMemory` levels and survival | PARTIAL (levels 5, 10, 15 PASS; 20-80 refused by Android for this process; phase 6 gets the text and the natural UI_HIDDEN) | see "V3" |
| V4 | Fresh-image path for the patched aquamarine | PASS | fresh extraction 102,176 ms; `guest-overlay files=68 changed=0` (the image already carried every overlay file); Hyprland maps the overlay `libaquamarine.so.13`, inode = the guest file's, sha256 `35a9ffd4…` = repo; `j/devices` `touch: ["wl_touch"]` in the first session; scratch `verify/p4-fresh-sudo.log` |
| V5 | `sudo` interactive, Ctrl+C, `omarchy-pkg-add` | PASS | prompt answered `n` (rc 1, nothing installed), `sudo sleep 30` + Ctrl+C = rc 130 at 6.65 s with the terminal restored and the broker still answering, `omarchy-pkg-add sl` rc 0 then removed (`pacman -Q` rc 1); screenshots viewed; same fresh guest as V4 |
| V6 | Session end and the error screen (H10-H15) | **PASS on S4's build `9dae471b`** (phase 11); **FAIL on the R10 build** (phase 3, reproduced in phase 7) | S4's build: the ended screen with the reason 0.02-0.03 s after `session ended` in all three clean exits, the exit-7 launch shows "(exit 7)", no ANR in any of the four logs, Start again restores the desktop in 18-19 s; Hyprland segfaulted at exit in 3 of 3 clean exits (log tail on screen) while the app's exit code read 0, 139, 0. R10 build: blank or stuck on "Starting desktop...", ANR 5.0 s after the end, no Start button, an icon tap does not restart; see "V6" and "V6, re-run" |
| V7 | Pinch and three-finger touch | **PARTIAL** | pinch PASS (both points reach a client, within 0.5 logical px, 0 cancels); a three-finger swipe is consumed by HyperOS (split screen, then home) with `enable_three_gesture=1`; a `hl.gesture` workspace bind for 2 or 4 fingers answered `ok` and moved nothing in 8 swipes **with the window asserted on the visible workspace and focused** (phase 13), so the Hyprland touch workspace swipe does not work on this stack; the `workspace_swipe_touch=true` variant is **untested, not cleared** (the option cannot be changed at runtime here); see "V7" |
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

### V2, attribution: phase 10's control failed in arm A, voided (phase 10, 09:26-09:5x UTC; **measured**, frames **viewed**)

Phase 10 was meant to say whether the 24 px come from the damage patch: arms B A A B, arm A = `AQ_WAYLAND_FULL_DAMAGE=1` (aquamarine
sends the whole surface every commit). Each arm's control paints the 400x250 remnant and expects to see it on screen before the event.

| Arm | control: clean frame vs painted frame | what the screen showed 1.5 s after the paint |
| --- | --- | --- |
| B1 (shipped) | **CHANGED**, 100,000 px, bbox 1400,900,1800,1150 (viewed: the magenta rectangle on the wallpaper) | the remnant, as intended |
| A1 | **ZERO**, nothing | the clean desktop, no rectangle (viewed) |
| A2 | **ZERO**, nothing | the clean desktop |

The draw itself worked in all three: the tool prints the window it fills, and in every arm that is the one root-sized top-level window
(geometry 0,0,3200,1970; A1 window 0x200004, A2 0x400004, B1 0x200004), and the session's own environment in the A arms carries
`AQ_WAYLAND_FULL_DAMAGE=1` (`p10-sliver.log` lines 35 and 62, read from `/proc/<pid>/environ` by `arm_check`). So the A arms are not
painting some other surface: a frame landed between the paint and the shot, ~1.5 s = ~90 commits at 60 Hz, and with the whole surface in
every commit each frame puts the X window's content back. **A pixel control cannot work in that arm**; A1's other three rows (`ctl2` ZERO,
`ctl3` ZERO, every `after-vs-forced` ZERO) are the same fact and prove nothing about the event.
**Phase 10 settles nothing about attribution, and its close events are not graded here.** The one observation worth carrying, marked
ungraded because it comes from the arm whose control failed: A1's close 2 shows the same 22 px, 1 level at x 3058-3083, y 88 (`before-vs-after` 22 px), so the residue
may be there in the whole-surface arm too, which would say the patch is not its cause. A2 (same failed control) shows it in all three of its closes
as well (`after-vs-forced` 22 px each; its `close3` before-vs-after is 4881 px, mostly the pointer and a 3 s-later frame taken while the session was
still settling, ungraded). This is the lead phase 12 tests properly.

Two facts from the valid arm B do carry:
- the remnant survives 3 s in B1 (`ctl2` ZERO) and the forcing step erases it, so the B-side instrument works;
- B1's and B2's `ctl3` (clean frame vs the frame after the forcing step) are each **CHANGED, 22 px, max_diff 1, at 3058-3083, y 88**: the forcing step alone
  produces that 1-level difference at that row, with no window close and no event. So it is a difference between the damage-limited render and the
  full repaint at that pixel row, not something a window close leaves behind.
- Arm B's six closes (B1 and B2, three each): `after-vs-forced` 22 px, max_diff 1, at 3058-3083, y 88 every time. `before-vs-forced`:
  ZERO, ZERO, ZERO (B1 close 3, B2 closes 2 and 3) and 2037 px in the two runs where the pointer moved. Phase 9's nine B-arm closes show the
  same thing at 24 px (x 3057-3082). So the residue is the same 22-24 px in every shipped-arm close, and the pointer is the only other
  difference between the frames.
- phase 10's arm A "2322 px" event difference was mostly the pointer: 2037 px at x 320-608, rows 383-453, max_diff 235 (a white
  arrow against a dark one), plus the 22 px row-88 difference and the clock; pixel diff and both frames viewed. The pointer moves between shots, so
  phase 12 parks it at a fixed spot before every frame.

**Phase 12 was written to replace the arm-A control** with something that can exist there (`verify-xcorrupt.py paint-read`: paint, then read the rectangle back out of cage's window with XGetImage ms later, plus the commit trace showing `whole_surface` on every commit, a steady control with no event, and the cursor parked before every shot). **Cancelled by the parent's ruling at 10:00 UTC: V2 is PASS within the noise floor, so the attribution it would have settled is no longer open.** Its tools stay in the tree (`verify-p12-attrib.sh`, `7f689a7`) and its commit was not reverted.

### V2, redo with a proven forcing step (phase 9, 09:10-09:22 UTC; **measured**, crops and shots **viewed**)

APK `bef783d7…`. Script `verify-p9-repaint2.sh`, log `<scratch>/verify/p9-repaint2.log`. A first run of the same phase
(08:25-08:34, kept as `old-r2/`) proved the step but threw it away, because its pass test did not allow the clock to turn over between two
shots, so its scenarios ran unforced; the fix (a clock-only difference counts as nothing but the clock) is in `f9b89c6` and the run below is the
second one. The clock box is x 110-175, y 20-70 of the mobile bar.

**Part 1, the forcing step (session with `AQ_TRACE=1`).** A remnant is painted straight into cage's X window with core X drawing
(`verify-xcorrupt.py`, 400x250 magenta at 1400,900; nothing in Hyprland or cage knows), so it behaves like a stale pixel.

| Step | Screen | Commit trace (`commit damage` lines in the window) |
| --- | --- | --- |
| control 1: clean frame vs painted frame | **CHANGED**, 100,426 px in cycle 1 (100,000 = the 400x250 rectangle, 426 = the clock turning over), 100,000 in the repeat and in session 2 (viewed, cycle 1: the magenta box lower right in the after panel, the diff panel marks the same box and the clock digits) | |
| control 2: bare `hl.config({ debug = { vfr = false } })`, 2.5 s | painted frame vs after: **ZERO**, the remnant stays | 183 zero-rect, **0 with rects**, 0 whole-surface |
| candidate A: `damage_tracking = 0` for 1.5 s, then `= 2` | after vs the clean frame: **ZERO** (or the clock only), the remnant is **gone** | 190 zero-rect, **54 with rects**, `debug:damage_tracking` read back `int: 2` |

Cycle 1 and a repeat ran in session 1 (repeat: 160 zero-rect, 54 with rects, clean frame ZERO), and the whole control cycle ran a third time at the start of
session 2 without the trace (remnant stays under the bare step, gone after A, `int: 2`). Candidates B (`vfr` true then false) and D (monitor re-apply)
were not needed. So the step the R10 method used repaints nothing, and A repaints the screen.

**Part 2, the scenarios (no trace, A as the forcing step), per event: the after-event frame, the forced frame, and the frame taken before the event.**
After-vs-forced, the primary check, 24 comparisons:

| Scenario (runs 1-3) | after vs forced | before vs forced (where the screen returns to the earlier state) |
| --- | --- | --- |
| toast fade | ZERO, ZERO, ZERO | n/a, the screen does not return to the earlier state: toast 1 left a new unread badge "1" beside the clock and the pointer had moved (viewed, 4,071 px); toasts 2 and 3 differ by 202 and 268 px (counts only, crops not viewed) |
| window open (foot) | ZERO, ZERO, CLOCK_ONLY | n/a |
| window close | **CHANGED**, **CHANGED**, **CHANGED** (24 px each, below) | CLOCK_ONLY, ZERO, CLOCK_ONLY |
| scrolling terminal stopped | ZERO, ZERO, CLOCK_ONLY | n/a |
| the scrolling window closed | **CHANGED** x3 (same 24 px) | ZERO, ZERO, CLOCK_ONLY |
| rotation to portrait, foot open | ZERO, ZERO, ZERO | n/a |
| foot closed, portrait | ZERO, ZERO, ZERO | n/a |
| rotation back to landscape | ZERO, ZERO, **CHANGED** (same 24 px) | CLOCK_ONLY x3 |

- **Totals: 24 comparisons: 15 ZERO, 2 CLOCK_ONLY, 7 CHANGED.** In every one of the 7: `changed=24 max_diff=1 bbox=3057,88,3083,89 outside_clock=24`
  (close-1 shows 390 changed = the clock's 366 plus the same 24). The forced frame equals the frame before the event in 9 of 9 returning cases (clock aside):
  a full repaint reproduces the earlier picture exactly. Nothing else is stale: no window remnant after a close or a rotation, no toast remnant in the after-vs-forced diffs (ZERO in all 3 runs; crops not viewed).
- **What the 24 pixels are.** Row y=88 is the first wallpaper row under the 88 px bar (bar colour `(26,27,37)` on rows 86-87). At x 3057-3082 the after-close frame has
  R=132 where the full repaint and the frame before the window opened have R=131 (`close-2`: A `(132,55,143)`, F and P `(131,55,143)`), one level of one channel,
  24 pixels. Viewed (`close-2` crop, 2x): the before and after panels are indistinguishable (bar right end with the wifi-off icon, wallpaper below), the diff panel is one short magenta line, broken once, at the bar's lower edge. It is not
  an old picture left on screen (the older frame equals the repaint); it is a freshly drawn pixel that differs by a rounding step from the repaint's.
- **Verdict: PASS, within the measured noise floor** (parent's ruling, 10:00 UTC). The rule stays as written: "0 changed pixels outside the clock in every comparison".
  The measured residue: 7 of 24 comparisons differ by 24 px at one level, x 3057-3082, y 88. That residue is the check's own repaint noise floor, not a product defect, on three
  grounds: (i) it appears with **no event at all** — the frames taken before and after a bare forcing repaint differ by the same 22 px at the same row, one level, in both shipped-arm
  controls (`ctl3` in B1 and B2, phase 10) and after phase 9's forcing step; (ii) it appears in the **full-damage arm** too (`AQ_WAYLAND_FULL_DAMAGE=1`, every commit whole-surface: A2's
  three closes show the same 22 px), so it is not the damage patch; (iii) the forced frame equals the frame taken before the event in **9 of 9** cases where the screen returns to its
  earlier state. Nothing else in the 24 comparisons differs, no stale window, toast or wallpaper content was seen anywhere, and no visible defect exists at 1 level of 1 channel on 24
  pixels. A check that fails on its own repaint noise floor is not a product defect; the rule is not relaxed, and any future use of it should expect this floor at that row.
- **Side facts from the same run.** After each rotation the desktop probe passed 6 to 14 s later (rotate, rotate back, per run: 14 and 6, 7 and 7, 14 and 14 s; each count includes a fixed 6 s wait, polling every 2 s). In the first, unforced run 3 of 6 probes at a fixed 10 s read `no omarchy-bar layer (shell not up)` (log `old-r2/p9-first.log`). So the shell bar is not back at 10 s after a rotation, and takes up to ~14 s; consistent with AGENTS.md (a live size change restarts the shell), though not the 2-3 s blink it describes. The app pid stayed the same through all six rotations.
  Viewed: the toast at the top right of the landscape desktop ("R11 V2 redo toast 1 / this toast fades out") with the search bar and key bar below, and the portrait desktop (`rot-1-portrait-open-F`) with the terminal prompt, bar clock 09:18 with badge "3", and the key bar intact.

### V2, correctness against a forced full repaint (phase 2, 01:51-02:01 UTC): WITHDRAWN, the forcing step repainted nothing

**Parent's finding (S1, `r11-memory.md` "Correctness: what the diffs above do and do not prove"), accepted:** `hl.config({ debug = { vfr = false } })` with `vfr` already false changes no value, so Hyprland damages nothing; with the trace on, eight such re-asserts produced 0 damaged commits out of 233 (kgsl) and 256 (software). Everything below compared two frames that were both taken after the event, so a stale remnant would sit in both and read as 0. What the data in this section still shows: the three CLOCK_ONLY diffs are real clock turnovers between the two shots (the bar clock repaints by itself), and the real-change control proves the diff sees change. It does not show that the damage path leaves no remnant. The redo is phase 9 (below, once it has run). The same flaw is in R10 run 5 (13 checks) and in the `damage-and-frame-pacing.md` method text.

Original write-up, kept for the record:

Per scenario: settle 3 s, screenshot, `hc.sh '/eval hl.config({ debug = { vfr = false } })'` (re-asserts the
value and repaints everything), settle 3 s, screenshot, exact pixel diff (`verify-scrdiff.py`; verdict ZERO,
CLOCK_ONLY when every changed pixel lies in the clock box at x 130-180, y 20-70 of the mobile bar, else CHANGED).
Hyprland reported `debug:vfr` false and `debug:damage_tracking` 2 at the start. App pid 29409 throughout.

| Scenario | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| toast fade (`notify-send -t 2500`, judged 10 s later) | CLOCK_ONLY (364 px, bbox 141,29-160,58) | ZERO | CLOCK_ONLY (366 px, same bbox) |
| window open (foot) | ZERO | ZERO | ZERO |
| window close | ZERO | ZERO | ZERO |
| scrolling terminal stopped (`seq 1 60` loop) | ZERO | ZERO | ZERO |
| the scrolling window closed | ZERO | ZERO | ZERO |
| rotation to portrait, foot open | ZERO | ZERO | ZERO |
| the foot closed, portrait | ZERO | ZERO | ZERO |
| rotation back to landscape | CLOCK_ONLY (343 px, bbox 141,28-160,58) | ZERO | ZERO |

- **Totals: 24 comparisons, 21 ZERO, 3 CLOCK_ONLY, 0 CHANGED.** All three non-zero diffs were viewed as a
  before | after | diff crop at 4x (`<scratch>/verify/p2-repaint/crops/`): the clock turned over a minute between the two
  shots (01:53 to 01:54, 01:54 to 01:55, 01:58 to 01:59); the magenta pixels are the last digit and nothing else.
- Viewed: `toast-1-showing` shows the test toast at the top right (so the scenario really drew one),
  `open-2-after` a foot prompt full width with the bar and the key bar intact, `scroll-2-running` the numbers 11-60
  filling the terminal, `rot-2-portrait-open-after` the portrait desktop (2136x3200 root) with the bar, a
  full-width foot window and nothing cut off. Every rotation: `probe.sh` VERDICT PASS within 12 s, same app pid.
- **Control a (a real change must read CHANGED): PASS.** Opening foot between two shots: `changed=5388233 changed_gt8=5008098`.
- **Control b (`debug.vfr=true`, then a toast fade, the case that left a remnant in R10 before committed damage): three
  ZERO.** I could not reproduce a remnant, so this control does not show that the instrument sees a stale-pixel
  remnant in particular, only that it sees every real change. It also did not read `vfr` back after setting it to true
  (the check ran `hl.config` and trusted it), so "VFR on and clean" is not claimed.
- **Finding for the parent (not this stream's change): two sticky notifications on the owner's desktop.** Every screenshot of
  the phase shows `Omdroid could not shutdown` and `Omdroid could not stop` ("This Omdroid build does not answer session
  requests. Update the app."), present from the first shot to the last, rotations included. The string exists only in the
  S4 worktree's `rootfs/overlay/etc/phoshdroid/complete/bin/omdroid-session` (line 63); the guest has no `complete/` directory
  now. They are most likely S4's own test notifications, restored from the shell's notification history at each start.
  They do not change any diff above (static pixels). The owner will see them until the history is cleared
  (`qs ipc -p /usr/share/omarchy/shell call notifications clear`); I left them in place.

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

### V4, the fresh-image path for the patched aquamarine (phase 4, 02:01-02:05 UTC; **measured**)

The owner guest was parked (`omarchy-r11-keep`, phase library), the APK extracted a fresh guest from its own
`rootfs.bin`, and the first session ran on it. APK `bef783d7…`, repo `lib/libaquamarine.so.13` sha256 `35a9ffd4c565364900a13c53fee935898c5885bd2508c527228b752d316d1562`.

| Check | Result |
| --- | --- |
| extraction | `launch: rootfs-extracted 102176ms`; `am start` to hand-over 126 s (R10 run 2: 104.1 s for the extraction alone, so the same) |
| the image already carries the overlay | `launch: guest-overlay files=68 changed=0 102272ms`: the sync found nothing to rewrite, so the packager's `lib/` and `etc/phoshdroid` copy put every file in the image byte-equal to the APK |
| the first session | one `session-started` since the park; `probe.sh` VERDICT PASS; X display on top; 38 stale `proot-*` sockets in the prefix tmp were wiped at the start (from the earlier phases' killed sessions) |
| the library that is mapped | `/proc/<Hyprland>/maps`: `.../omarchy/etc/phoshdroid/lib/libaquamarine.so.13`, inode **1302760** = `stat` of the guest overlay file (1302760); its sha256 = the repo's; the stock copy in `/opt/omarchy-android/aquamarine/lib/` is `8a2a2cbe…` and is not the mapped one |
| the touch device | `hc.sh j/devices`: `mice ['wl_pointer'] keyboards ['wl_keyboard'] touch ['wl_touch']` |
| the screen | viewed: the mobile desktop with the sunset wallpaper, the 26 px bar with the clock, the "Search apps..." dock and the key bar; no banner, no foreign dialog. The fresh guest has none of the two sticky notifications seen on the owner's (they live in the owner's shell history) |

The test guest was deleted at the end of the phase, after the owner guest was moved back (`installed-rootfs`: `omarchy`, `omarchy-upgraded-20261126`).
This settles the README line "The fresh-image path for the patched aquamarine ... not repacked".

### V5, `sudo` beyond `sudo id` (phase 4, same fresh guest; **measured**, screenshots **viewed**)

Typed into a foot shell with `adb shell input text` and `input keycombination`; each case ends in a file the guest writes.
`sudo id` / `sudo -u omarchy id` / `sudo false` first: root, `uid=1000(omarchy)`, `false-rc=1`.

| Case | What ran | Result |
| --- | --- | --- |
| interactive prompt | `sudo pacman -Syy --noconfirm` (rc 0), then `sudo pacman -S sl`, answer `n` + Enter | viewed at the prompt: `Packages (1) sl-5.05-6 ... :: Proceed with installation? [Y/n]` with the cursor waiting; after `n`: the letter shown once; after Enter: `[Y/n] n` and the shell prompt back; `pacman rc=1`, `sl` not installed |
| Ctrl+C control | a plain `sleep 30` and the same Ctrl+C injection | viewed: `^C` and the prompt back. (The marker file is absent because bash abandons a `;` list whose child died of SIGINT, so absence is not a failure; the next command ran at once, which a live `sleep 30` would have blocked) |
| Ctrl+C during `sudo sleep 30` | injection about 6 s in | `sudo sleep rc=130 t0=...095.64 t1=...102.30`: it ended on the key, 23 s early; viewed: `^C`, prompt back; `stty -a` afterwards has `isig icanon echo` all on; a typed `echo typed-ok > /tmp/v5-typed.txt` ran (`typed-ok` read back); `sudo id` afterwards still root (the broker lived) |
| `omarchy-pkg-add` | `omarchy-pkg-add sl` | rc 0, `pacman -Q` `sl 5.05-6` (viewed: key check, `installing sl`, post-transaction hooks) |
| removal | `sudo pacman -Rns --noconfirm sl` (the last step of `omarchy-pkg-remove`, whose own front end is an fzf picker) | rc 0, `removing sl`, `pacman -Q sl` rc 1 |

Not run (not asked): R6 steps 8-10 (ownership of a `sudo touch`, the broker log, killing the broker). The yay path was R6b's.
Observation, not a failure: every pacman transaction on the fresh guest prints `warning: directory permissions differ on /usr/ filesystem: 700 package: 755` (also `/usr/bin/`, `/usr/share/`, `/usr/share/licenses/`): directories extracted by the app come out 0700. It is harmless to these transactions; it is the extractor's mode handling, not this stream's to change, so it is a note for the parent.

### V6, re-run on S4's build (phase 11, 10:05-10:10 UTC; **measured**, screenshots **viewed**)

Build under test: `complete/apk/omdroid-complete-60d0b95.apk`, sha256 `9dae471b3c72…44877`, installed over the R10 build (`INSTALL: PASS`,
`lastUpdateTime=2026-11-27 10:06:15`); the R10 build was reinstalled by the phase's exit trap at 10:10:57. Script `verify-p11-v6-s4.sh`, log
`<scratch>/verify/p11-v6-s4.log`. The exit is the session's own `hl.dsp.exit()` dispatch, as S4's path.

| Item | Measurement | Screen |
| --- | --- | --- |
| clean exit, run 1 | `proot exited (0)` 10:07:00.708; `launch: session ended exit=0` 10:07:00.727 -> `launch: ended-screen exit=0` 10:07:00.748 = **0.02 s** | at +2 s the ended screen: logo, "Omdroid", **"The desktop session ended."**, the session log tail, a **Start again** button (viewed) |
| Start again, run 1 | tapped at (1600,1794); desktop back after **19 s**, probe PASS, new Hyprland pid 11875, app pid unchanged (10479) | the desktop (viewed) |
| clean exit, run 2 | `proot exited (139)` 10:08:07.515; ended-screen **0.03 s** | **"The desktop session stopped unexpectedly (exit 139)."**, log tail, Start again (viewed) |
| Start again, run 2 | desktop back after **18 s**, probe PASS, Hyprland pid 12900 | the desktop |
| clean exit, run 3 | `proot exited (0)` 10:09:13.785; ended-screen **0.02 s** | **"The desktop session ended."**, log tail, Start again (viewed) |
| Start again, run 3 | desktop back after **19 s**, probe PASS, Hyprland pid 13647 | the desktop |
| launch that dies (session.env `exit 7`) | `proot exited (7)` 10:09:50.828 and `proot retry exited (7)` 10:09:51.065 (one retry, as `SessionExit` says); ended-screen **0.00 s** | **"The desktop session stopped unexpectedly (exit 7)."** with the shell trace tail ending `+ exit 7` (viewed) |
| Start again after the failed launch | desktop back after **18 s**, probe PASS | the desktop (viewed) |

- **No ANR, four times.** `logcat -d` in each of the four dumps holds no `ANR in com.phoshdroid.app`; none of the four screenshots shows
  "isn't responding"; `dumpsys activity exit-info` lists only `reason=10 (USER REQUESTED) subreason=21 (FORCE STOP)` and
  `reason=16 (PACKAGE UPDATED)`, which are this phase's own force-stops and the APK installs.
- **The reason text is on the screen**, not only in the log: the headline names the exit code when it is non-zero (139, 7) and says the session
  ended when it is 0, followed by the last lines of the guest session log; `Start again` is a real node in the UI dump in all four cases, which
  is why the tap hit it at (1600,1794) rather than falling back to the icon path.
- **The segfault S4 reported, as this run saw it.** Every one of the three clean-exit frames carries
  `child line 49: <pid> Segmentation fault -- "HYPRLAND" --config "HYPRLAND_CONFIG"` as the last line of the log tail on screen (the script
  name before "child" is cut off by the screen's line wrapping) (pids 10888,
  11875, 12900: the session's own Hyprland each time), so Hyprland died by SIGSEGV on **3 of 3** clean exits here, while the exit code the app
  received read 0, 139, 0. So the segfault is the normal shape of a session exit on this build, the ended screen is correct regardless of it, and
  **the exit code is not a reliable detector of the segfault** (1 of 3 read 139). S4's "4 of 9" was counted from exit codes, so it undercounts
  rather than overstates. Not investigated further: which part of Hyprland's shutdown path faults.
- **Against the R10 build (phase 3):** that build logged `launch: ended-screen exit=7 665ms` and then showed "Starting desktop…", a blank
  launcher afterwards, an ANR 5.0 s after the end and no Start button, with the main thread futex-blocked at +3 s and +7 s (phase 7). None of
  that reproduces here: the same three scenarios and the exit-7 launch all show their screen within 0.03 s and recover.

### Finding: Hyprland dies by SIGSEGV at every clean exit on `9dae471b`, and the exit code the app gets does not see it

Measured in phase 11 (three clean exits from inside, then the exit-7 launch), on S4's build `9dae471b`:

| run | the session's Hyprland pid | last line of the log tail on the ended screen | exit code ProotService got | ended-screen headline |
| --- | --- | --- | --- | --- |
| 1 | 10888 | `child line 49: 10888 Segmentation fault -- "HYPRLAND" --config "HYPRLAND_CONFIG"` | 0 | "The desktop session ended." |
| 2 | 11875 | `child line 49: 11875 Segmentation fault -- "HYPRLAND" --config "HYPRLAND_CONFIG"` | 139 | "The desktop session stopped unexpectedly (exit 139)." |
| 3 | 12900 | `child line 49: 12900 Segmentation fault -- "HYPRLAND" --config "HYPRLAND_CONFIG"` | 0 | "The desktop session ended." |

- **The segfault is the normal shape of an exit on this build: 3 of 3 clean exits.** The session's own Hyprland was killed by SIGSEGV every
  time (the shell reports it at `child line 49` of the session script, and the error page shows that tail on screen, viewed in all three frames).
  It is not an occasional failure and it does not affect what the user sees: the ended screen, the reason, the absence of an ANR and Start again
  are all correct in the same runs (V6 PASS above stands).
- **The app's exit code is not a detector for it.** Two of the three segfaulting exits reported `0`; only run 2 reported `139`. The exit code is
  the session supervisor's, not Hyprland's, so a segfault can surface as a clean exit. Any count of segfaults taken from exit codes undercounts:
  S4's "4 of 9" is a floor, not the rate.
- **Therefore the earlier "banners off: 0 of 6" reading cannot be used as evidence that the completion banners cause the segfault.** That reading
  (S4's phase 8: `OMDROID_COMPLETE_BANNERS=0` 3 cycles, `OMDROID_COMPLETE=0` 3 cycles, all `proot exit=0`, against `mine-default` 4 cycles with one
  `139`) counts non-zero exit codes, and on this build a segfaulting exit reads `0` most of the time (2 of 3 here). Those six cycles may all have
  segfaulted. Testing the banners needs the segfault read from the guest's own session log (the `Segmentation fault` line above), not from the exit
  code; until then the banners are neither implicated nor cleared.
- **Not investigated:** which part of Hyprland's shutdown path faults. Nothing in this round's gates depends on it; a coredump or `catchsegv` read is
  the next step if the rate matters later.

### V6, session end and the error screen (phase 3, 02:25-02:32 UTC; **measured**, screenshots **viewed**)

**Verdict: FAIL on the screen, PASS on the service.** Three ways to end a session, each from a cold start
(app pid 15773, then 17766 after a force-stop):

| Case | What the host did (logcat, tag `Phoshdroid` / `ProotService`) | What the screen did (viewed) |
| --- | --- | --- |
| V6.1 clean end: `hl.dsp.exit()` in the session | `ProotService: proot exited (0)`, `launch: session ended exit=0 ui=shown` at 02:26:09.9. **No `launch: ended-screen` line followed.** | Launcher activity on top 1 s later, but the screenshot (02:26:14) is a **blank dark screen**: no text, no button. uiautomator returned an empty dump (0 bytes). |
| V6.1 recovery: launcher icon (`am start`) | nothing logged for 90 s | still the launcher activity, `probe.sh` says `no compositor window on the X root (cage is not running)`, `Hyprland: NO-IPC`: the desktop never came back |
| V6.2 Hyprland killed 35 s in | **did not run**: the session was already gone, so `pkill` hit nothing | the app was already wedged; its screenshot shows Android's **"Omdroid isn't responding"** dialog (Wait / OK) |
| V6.3 session dies at launch (`session.env`: `exit 7`), after a force-stop | `proot exited (7)`, `proot retry exited (7)` (one retry inside the 30 s window, as `SessionExit` says), `launch: session ended exit=7 ui=shown`, `launch: ended-screen exit=7 665ms` | 4 s later the screen shows the logo, "Omdroid" and **"Starting desktop..."**: not the error text, not the log tail, no Start button. uiautomator again 0 bytes. |
| V6.3 recovery after putting `session.env` back | tap path as above | still the "Starting desktop..." splash after 90 s, no desktop |

- **The ANR is the strongest fact.** `dumpsys activity exit-info` lists for pid 15773 (the V6 process) a trace
  `anr_2026-11-27_02-26-14-976.gz`: 5.0 s after the session ended at 02:26:09.9 (the 5 s input-dispatch limit).
  `/data/anr/anr_2026-11-27_02-26-14-976` exists (2.2 MB) but the shell cannot read it. So the app's
  main thread stopped serving input from the moment the session ended and never recovered, and that is why there
  is no `ended-screen` line (it is logged on the main thread, in `onNewIntent`) and no Start button.
- **Not claimed:** the cause. The main thread is blocked somewhere between `ProotService.finishSession`
  (`startActivity` of the launcher with `session_ended`) and `LauncherActivity.onNewIntent` →
  `showSessionEnded` (`LauncherActivity.kt:923`), or the X display activity's teardown (the in-process X server
  loses its only client at that moment). I did not stop at a guess: phase 7 repeats all three cases without touching
  the screen first and captures the main thread's `/proc` state and every thread's Java stack through JDWP.
- **Reproduced without touching the screen (phase 7 case A, 03:01-03:03 UTC; **measured**).** The counter-check repeated the clean
  end from a force-stopped cold start and read only `/proc` for the first 8 s (no screenshot, no uiautomator, no input). At
  +3 s and again at +7 s after `proot exited (0)`: top activity `.LauncherActivity`, Hyprland gone, and the app's **main
  thread in `state=S wchan=futex_wait_queue` (syscall 98, futex)**, not parked in the looper's `epoll_wait` as an idle
  main thread is; `X11Server` threads in `do_epoll_wait`, three `Thread-10` and three `DefaultDispatch` threads in
  `futex_wait_queue`. A main thread blocked on a futex for 4+ s with the launcher on top is the ANR's mechanism: it is waiting
  for a lock, a `Thread.join`/`waitFor`, or a condition, and cannot run `onNewIntent`. So the earlier harness caveat is
  answered: the screenshot and the dump did not cause the hang. What is still missing is the Java stack of that main
  thread (which lock, held by whom): phase 7 was to read it through JDWP and hung before it got there (see "Incident").
  The owner of the fix is S4 (`LauncherActivity`, `ProotService`); `jdb -attach` on a forwarded `jdwp:<pid>` with
  `timeout`, or `kill -3` plus a readable trace on a debuggable build, gives the stack. V6 is re-verified on S4's APK, not this one.
- **Harness caveat, stated against myself:** phase 3 took a screenshot and a uiautomator dump within 5 s of the
  end. Neither sends input, but the ANR timing alone cannot rule out that the dump contributed. Phase 7 reads
  `/proc` and the log only for the first 8 s and touches the screen last. If the ANR appears there too, it is the product.
- The H11 unit-tested parts hold on the device: the service clears `active`, reports the exit code, drops the notification
  and retries once only inside 30 s. What the unit tests could not see is the Android side, which is what failed.

### V7, pinch and three-finger touch (phase 5, 02:32-02:36 UTC; **measured**, screenshots **viewed**, settings **read**)

Instrument: Android's `uinput` with a synthetic type-B multi-touch screen (`verify-mkuinput.py`: N fingers moving in
straight lines, 30 steps of 16 ms), and `touchlog` (R5 build, sha256 `68a58e97…`), a layer surface that prints every
`wl_touch` event with surface-local coordinates. Calibration: a tap at screen (1600, 1000) logs (799.5, 499.5), expected
(800, 500) (the constant -0.5 logical px of the X11 hop, R5 finding): the mapping is right. Hyprland: `touch: ["wl_touch"]`.

| Gesture | Points that reached the client | Result |
| --- | --- | --- |
| pinch out (two fingers 1500 and 1700 moving apart by 400 px each) | ids 0 and 1, 31 motion events each, both down within 1 ms (`max_simultaneous=2`), id 0 (749.5 -> 549.5), id 1 (849.5 -> 1049.5), 0 cancels | **PASS**: both points, full path, positions within 0.5 logical px of the commanded ones |
| pinch in (the reverse) | ids 0 and 1, 31 motion events each, 549.5 -> 749.5 and 1049.5 -> 849.5, 0 cancels | **PASS** |
| three fingers sideways (800 px) | ids 0, 1, 2 down together (`max_simultaneous=3`) but only 9-10 motion events each (a third of the path, ending at +120 logical px of 400) and only one `up` (id 0, after 0.16 s); ids 1 and 2 never got an `up` until touchlog exited | **HyperOS took it, see below** |

- **Why three fingers stop: the system gesture.** `adb shell settings list system` (**read**): `enable_three_gesture=1`,
  `three_gesture_horizontal_ltr=split_ltr`, `three_gesture_horizontal_rtl=split_rtl`, `three_gesture_down=screen_shot`,
  `three_gesture_long_press=partial_screen_shot`. The first synthetic swipe really entered **split screen**:
  the screenshot after it (viewed) shows the Android home screen on the left half and Omdroid on the right half (a 1584 px
  wide window; the touchlog surface was configured at 792x985 instead of 1600x985, which also shifted every later
  coordinate), and the second swipe went to the Android home screen (`top=com.miui.home/.launcher.Launcher`, viewed). Any
  three-finger gesture in the guest is eaten by HyperOS on this tablet unless the owner turns off Settings > Additional
  settings > Gesture shortcuts > three-finger gestures, which I did not touch.
- **Observation, not proven as a bug:** the system cancelled a three-finger gesture after 0.16 s and the guest saw an
  `up` for one finger of three. Two touch points stayed "down" in the client until the client exited. Whether they stay
  down in the compositor after that is not measured (the next touchlog run started in a different window size and its ids
  do not match its commands). A real finger doing a system gesture would leave the same state if the cancel path of
  Termux:X11 ends only one pointer.
- **Hyprland's own touch workspace swipe: not configured.** `gestures:workspace_swipe_touch` reads false (set false);
  `gestures:workspace_swipe` and `workspace_swipe_fingers` do not exist in this Hyprland (0.56.1, `no such option`);
  `input:touchdevice:enabled` is true. The Omarchy config `/usr/share/omarchy/config/hypr/input.lua` carries the gesture
  API only as comments (`-- hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })`, lines 53-57),
  so nothing is bound.
- **Invalid, not counted:** the V7.3 ("enable `workspace_swipe_touch`") and V7.4 (runtime `hl.gesture` bind, three fingers)
  swipes ran while Omdroid was in split screen or the Android home screen was on top, so they say nothing about Hyprland.
  `workspace_swipe_touch = true` alone binds no gesture in this version.
- **Phase 8, the runtime `hl.gesture` follow-up (10:38-10:42 UTC, R10 build, four cold-start arms; **measured**, screenshots **viewed**).**
  Arms: nothing bound (control), 2 fingers bound, 4 fingers bound; each swiped right then left. The bind
  `hl.gesture({ fingers = N, direction = "horizontal", action = "workspace" })` (the vendor config's own example shape, `input.lua`
  lines 53-57) answered `ok` in both bound arms. **Result: after every one of the six swipes the state was identical to before it** —
  `ws=2`, monitor `WAYLAND-1 3200x1970@120.00 scale=2.0`, top `com.termux.x11.MainActivity`. No workspace change, no gesture visible,
  in the bound arms or the control.
  - **Limit of this run as built:** the frames taken after the swipes show an empty desktop with no window (viewed, `c2-right-after`
    and `g2-right-after`: wallpaper, search bar, key bar, nothing else), while the arm starts foot and then focuses workspace 2 explicitly,
    so foot was either never started or left behind on another workspace. The swipes therefore landed on an empty workspace, which is not the
    arrangement a workspace gesture is aimed at. Injection itself is proven from phase 5 (the same helper delivered a two-finger pinch, 31
    motion events per finger, into a client), so the failure is not "nothing was ever injected".
  - **What it showed, and what phase 13 then settled:** a runtime bind plus a swipe with that finger count changed nothing, and the bound
    arm was indistinguishable from the unbound control, but phase 8's frames carried no window on the visible workspace, so the reading was
    left open. Phase 13 (below) repeats it with the window asserted there.
- **Phase 13, the closing experiment (10:46-10:48 UTC, one session, R10 build; **measured**, frames **viewed**).** Before every swipe the
  arrangement was asserted three ways and the arm aborted loudly if any failed: a `foot` client whose `workspace.id` equals the active
  workspace id (`j/clients`, `j/activeworkspace`), `j/activewindow` class `foot`, and the frame taken just before the swipe differing from a
  clean-desktop frame by more than 100,000 px. All four arms passed: `ws=1`, `activeclass=foot`, the window covering **5,809,706-5,809,863 px**
  of the frame (a maximised single window filling the area under the bar, viewed in `ctl-pre`: terminal with prompt, clock 10:47, key bar).
  - Eight swipes: control (nothing bound), 2 fingers bound, 4 fingers bound (both binds answered `ok`), and a fourth arm meant to add
    `gestures:workspace_swipe_touch=true`. **Every one of the eight: `ws=1` before and after, monitor `WAYLAND-1 3200x1970@120.00 scale=2.0`,
    top `com.termux.x11.MainActivity`, same frame** (viewed `g2-right-after`: the same terminal, same workspace).
  - **The flag arm is void:** `gestures:workspace_swipe_touch` reads `bool: false` and neither `setoption gestures:workspace_swipe_touch 1` nor
    `keyword gestures:workspace_swipe_touch true` changed it (read-back stayed `bool: false`), so it ran as a second 2-finger arm and moved
    nothing. It was put back to `bool: false`, its original value (read at the start, logged).
  - **RESULT: the touch workspace swipe does not work on this stack with the window focused on the visible workspace and a runtime `hl.gesture`
    bind of two or four fingers.** The `workspace_swipe_touch=true` variant is **untested, not cleared**: the option cannot be changed at runtime
    on this build, so testing it needs a config edit plus a session restart, which this round did not do. No further arms were run.

### Incident: phase 7 held the tablet lock for five hours (my script, **measured**)

`verify-p7-v6-recheck.sh` called `adb jdwp | tr` to list debuggable pids. `adb jdwp` streams pids and never exits, so the phase
sat on that line from 03:03 to 08:04 UTC with the tablet lock held; every phase queued behind it (mine and the other streams')
waited out `flock -w 10800`. The parent stopped it by exact PID; its EXIT trap restored the owner state (cold start 14.0 s,
`probe.sh` PASS, installed APK `bef783d7…`, no parked or test guest left). Fixes, all committed (`aa2c547`):
`timeout 3` on `adb jdwp`; `chain.sh` now runs every phase as `flock -w 7200 <lock> timeout -k 30 1500 bash <phase>`, so no phase
of mine can hold the lock past 25 minutes (the phase's own EXIT trap still restores the owner state on that SIGTERM); the other
phases were audited for streaming commands (`logcat` is always `-d`, every `tail -F` is under `timeout`). Phases 6 and 8
had also timed out in the queue behind it without running; both were re-queued after the fix. Phases 4 and 5 had already run
(logs and results above); the parent's note listed them as lost, they were not.

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
