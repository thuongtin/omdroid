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
| V2 | Correctness vs forced repaint, 3 runs of toast / open-close / scroll / rotation | PASS | 24 forced-repaint comparisons: 21 identical, 3 differ only in the bar clock (viewed), 0 changed elsewhere; real-change control read CHANGED (5,388,233 px); the `vfr=true` control stayed clean (not a reproduction of the R10 remnant, see "V2"); scratch `verify/p2-repaint.log`, APK `bef783d7…` |
| V3 | `onTrimMemory` levels and survival | PARTIAL (levels 5, 10, 15 PASS; 20-80 refused by Android for this process; phase 6 gets the text and the natural UI_HIDDEN) | see "V3" |
| V4 | Fresh-image path for the patched aquamarine | PASS | fresh extraction 102,176 ms; `guest-overlay files=68 changed=0` (the image already carried every overlay file); Hyprland maps the overlay `libaquamarine.so.13`, inode = the guest file's, sha256 `35a9ffd4…` = repo; `j/devices` `touch: ["wl_touch"]` in the first session; scratch `verify/p4-fresh-sudo.log` |
| V5 | `sudo` interactive, Ctrl+C, `omarchy-pkg-add` | PASS | prompt answered `n` (rc 1, nothing installed), `sudo sleep 30` + Ctrl+C = rc 130 at 6.65 s with the terminal restored and the broker still answering, `omarchy-pkg-add sl` rc 0 then removed (`pacman -Q` rc 1); screenshots viewed; same fresh guest as V4 |
| V6 | Session end and the error screen (H10-H15) | FAIL on the R10 build (phase 3, reproduced in phase 7); re-verify on S4's APK | the service side works (`session ended exit=0 ui=shown`, exit 7 reported), the screen does not: blank or stuck on "Starting desktop...", ANR 5.0 s after the end, no Start button, an icon tap does not restart; main thread futex-blocked at +3 s and +7 s with no screen contact (phase 7 case A); V6.2 never ran; see "V6" |
| V7 | Pinch and three-finger touch | PARTIAL (phase 5 answered the first half; phase 8 queued for the Hyprland swipe) | pinch: both points reach a client, positions within 0.5 logical px, 0 cancels; three fingers: all three reach it, then HyperOS takes the gesture (split screen, then home) after ~160 ms; Hyprland swipe: not configured; scratch `verify/p5-multitouch.log` |
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

### V2, correctness against a forced full repaint (phase 2, 01:51-02:01 UTC; **measured**, crops and shots **viewed**)

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
  `workspace_swipe_touch = true` alone binds no gesture in this version. Phase 8 binds a two-finger and a four-finger
  workspace gesture at runtime (counts the system does not use), swipes each way from a cold start, and runs the two-finger
  swipe with nothing bound as the control.

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
