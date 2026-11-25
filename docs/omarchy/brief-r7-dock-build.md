# Brief R7-DOCK-BUILD: dock to a monitor = Omarchy desktop, undock = Android (code round, no device)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. No device in this round: Phil tests the build by hand afterwards.

Repo: `<repo>` (branch `main`, read `AGENTS.md` and
`docs/omarchy/launch-contract.md`). Read whole, first: `docs/omarchy/r7-dock-research.md` (the
research this round implements: §5 a1-a7, b1-b3, c, the risks, the milestones). Report, created
in your FIRST calls and updated after every step: `docs/omarchy/r7-dock-report.md` (STATUS TABLE
D0-D7). Scratch: `<scratch>/omarchy/r7/dock/`.

## The goal (Phil)

"When I plug my phone into a monitor, keyboard or mouse, I can use Omarchy. When I unplug it and
go out and about I can use Android and optionally Omarchy." So: a monitor appears -> the Omarchy
session shows full screen on the monitor in the `desktop` UI, scaled for that monitor, keyboard
(SUPER included) and mouse working, the phone screen stays Android; the monitor goes -> the
session keeps running, Android is normal, opening Omdroid shows the same session on the phone in
the `mobile` UI. The UI mode switches live (shell restart only, windows survive), never by
restarting the session.

## Scope of this round (implement, unit-test, build; device proof is Phil's)

- **a1 dock detection** as a pure, unit-tested decision (`launch/DockState.kt` or similar: input
  = the list of displays with id/flags/size/density plus input devices present; output = docked or
  not, the target display id) with a thin Android edge (`DisplayManager.DisplayListener`) that
  logs one line per change: `dock: docked display=<id> <w>x<h>@<dpi>` / `dock: undocked`.
- **a2 / b2 the UI mode follows the dock**: the host writes `<rootfs>/home/omarchy/.config/omdroid/ui`
  (`desktop` docked, `mobile` undocked) only when the user has not pinned a mode. Design the pin:
  e.g. a second file `~/.config/omdroid/ui-pin` or a value `auto`; the default is `auto`; write the
  rule down in the launch contract. Never overwrite a mode the user chose by hand.
- **a3 geometry and scale from the TARGET display** (`DisplayGeometry`, `UiScale`): take the
  metrics of the display the X activity will be on, not the launcher's window. Unit tests with a
  4K monitor, a 1080p monitor, the phone.
- **a4 launch on the monitor**: `ActivityOptions.makeBasic().setLaunchDisplayId(id)` for the
  `com.termux.x11.MainActivity` intent when docked, `try/catch (SecurityException)` falling back
  to today's launch, never a second `MainActivity` instance (`singleTask`). Handle the session
  already running when the monitor appears: move/reopen the X activity on the monitor (say how
  in the report: Android may move it, or the launcher re-launches it with the display id).
- **a5 keyboard capture when docked**: `<uses-permission android:name="android.permission.CAPTURE_KEYBOARD"/>`
  and `setKeyboardCaptureEnabled(true)` on the X activity window on API levels that have it
  (36.1+; guard by SDK and catch every failure), keeping today's accessibility key interceptor as
  the fallback. Verify the API name, class and level in the Android SDK the project compiles
  against (`compileSdk` 35 may not have it: if so use reflection, and say so).
- **a7** hide the extra-key bar while docked (`showAdditionalKbd=false`; restore when undocked).
- **b1** `com.samsung.android.multidisplay.keep_process_alive = true` (the submodule manifest
  sets `false`: change it in the `termux-x11` submodule on branch `phoshdroid-integration`,
  committed there, and bump the submodule pointer in the main repo).
- **c live UI switch in the guest**: `omarchy-watch.py` watches `~/.config/omdroid/ui`; on a
  change it runs `omdroid-ui.sh`, rebuilds the plugin index (`omarchy-plugin-index.sh`) and
  restarts only the shell (its existing rate-limited `act()` path); the Hyprland looknfeel half
  needs a config reload: research §5c notes `hyprctl reload` re-applies the start-time output mode,
  so reload only when the monitor size is unchanged or let the size logic fix it afterwards (say
  what you did and why). Test it with a dry run against a scratch copy of the guest like round 5
  did (`docs/omarchy/r5-mobile-ui-report.md` U5): mobile -> desktop -> mobile with the watcher's
  switch function called directly, no Hyprland needed.

## Steps

**D0.** Premises: re-check the research claims you build on (APIs, levels, the manifest line, the
Termux:X11 code paths for display changes: `MainActivity` / `LorieView` configChanges, what
happens on a display move). Write the ones that change the design into the report.
**D1.** a1 + a3 pure code and tests. Gate below. Commit.
**D2.** a2 (+ pin rule) + a4 + a5 + a7 wired into `LauncherActivity` / the X activity setup. Gate. Commit.
**D3.** b1 in the submodule (commit there, then the pointer). Commit.
**D4.** c in the guest (`omarchy-watch.py`, `omdroid-ui.sh` only if needed) + dry run. `bash -n`,
`python3 -m py_compile`. Commit.
**D5.** Launch contract + README (a short "Docking" section: what happens on plug and unplug, the
pin, what is untested). Commit.
**D6.** Do NOT build an APK (the parent builds one combined test APK after another agent's round).
Instead run the full gate once more and write the exact sha of the tree.
**D7.** Report: STATUS TABLE, a section per step, "Manual test for Phil" (8-12 steps covering:
Developer options -> Simulate secondary displays on the tablet or phone; a real monitor over
USB-C; keyboard incl. SUPER; mouse click and wheel; unplug with a terminal window open; replug;
pinning a mode; what each log line must say: `adb logcat -s Phoshdroid:* | grep dock:` and the
guest's `omarchy-watch` log), "Risks still open" (from the research), "Not verified".

Gate after each code step: `./gradlew :app:compileDebugKotlin :app:test :app:lintDebug
--console=plain` (foreground) and `python3 docs/omarchy/tools/unit-count.py` (must grow from
`unit tests 69 failed 0`; lint 0 errors).

## Hard rules

- **A sibling agent is working in this same checkout right now** (yay/makepkg round): it owns
  `rootfs/overlay/etc/phoshdroid/{sudo,fakeroot,yay,omdroid_root.py,omdroid-rootd.py,start.sh}`,
  `rootfs/package-omarchy-rootfs.sh`, the `syncGuestOverlay` block of `app/build.gradle.kts`,
  `docs/omarchy/tools/rootd-selftest.py`, `docs/omarchy/r6b-yay-report.md`, and the sudo/yay
  paragraph of `README.md`. Never edit those. If your change truly needs one, describe it in your
  report instead.
- Files you may change: `app/src/main/**` and `app/src/test/**` (Kotlin, manifest, resources),
  `termux-x11/**` (branch `phoshdroid-integration` only), `rootfs/overlay/etc/phoshdroid/{omarchy-watch.py,omdroid-ui.sh}`,
  `docs/omarchy/launch-contract.md`, `README.md` (a new "Docking" section only), your report,
  `docs/omarchy/tools/**` (new files only).
- **Commit each finished step at once** with exactly its paths (`git add <paths> && git commit`);
  never `git add -A`, never `git stash`, never `git checkout` of files you did not change. No
  push, tag or release. If `git commit` says "nothing to commit" for a change you made, check
  `git log -1 -p` before redoing anything (the sibling may have swept it).
- No adb, no device tools, no `assembleDebug`. Never `pkill -f`. No `sleep N; tail` poll loops.
- If a command waits on an approval, do not retry or rephrase it; note it and go on.
- If your call budget runs low, write the report state and commit before anything else.

Final reply, at most 10 lines: D0-D7 with the decisive fact each, the pin rule, how a running
session reaches the monitor, the unit-count line, the commits, what Phil must test.
