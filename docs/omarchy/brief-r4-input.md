# Brief R4-INPUT: the tablet's keyboard cover and touchpad drive Omarchy (build + device)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`.

Repo: `<repo>` (branch `main`, read `AGENTS.md`).
Tools: `docs/omarchy/tools/` (run them from that directory); every tool needs
`export TABLET_SERIAL=<adb serial>` first. Never write that serial into a repo file.
**Read first, whole: `docs/omarchy/r4-input-research.md`** (the source study this brief is built
on; it cites file:line for everything below). Also `docs/omarchy/r4-touch-report.md` (the round
that just finished on the same device: its touch change is already in the tree).
Your report, created in your FIRST calls and updated after EVERY item:
`docs/omarchy/r4-input-report.md`, starting with a STATUS TABLE (rows K0-K6, `PENDING` until
proven, then `PASS`/`FAIL`/`BLOCKED` plus the numbers). Write each row in the same call that
produced its numbers.

## THIS RUN: PHASE A ONLY (code, no device)

The tablet is PIN-locked and another agent (the touch round) owns it until it reports. In this run
do **K1, K2 and K3 only**, plus the gate after each, and nothing on the device:
- no adb call of any kind, no `./install.sh`, no tool from `docs/omarchy/tools/` that talks to the
  device, no `assembleDebug` (the APK files under `app/build/outputs/apk/debug/` belong to the touch
  agent: do not overwrite or delete them);
- `LauncherActivity.kt` already carries the touch round's `touchMode = "2"` (commit `f0dba29`):
  keep it exactly;
- report rows K0 and K4-K6 stay `PENDING (phase B)`; K1-K3 get their proof (gate output, the
  unit-count line, the merged-manifest label line);
- the parent sends phase B (K0, K4-K6) as a new prompt once the tablet is free.
Final reply for this run, at most 6 lines: K1-K3 with their proof, the unit-count line, files changed.

## Goal

Phil wants the keyboard cover and touchpad attached to his tablet (Android lists
`Xiaomi Focus Pen Pro Keyboard`, `Xiaomi Focus Pen Pro Mouse`, `Xiaomi Keyboard`, `Xiaomi Mouse`)
to work in the Omarchy desktop as on a Linux PC. Omarchy's main modifier is SUPER (Meta).
Today (research §1): letters reach the guest as Unicode text, not key codes; Android 16 consumes
Meta (opens the app drawer), Meta+Tab, Alt+Tab and Meta+Esc before the app sees them, so SUPER+W
arrives as a plain `w`; the only way past that is Termux:X11's `KeyInterceptor` accessibility
service, which can never switch on in this app because its code hard-codes the component
`com.termux.x11/.utils.KeyInterceptor` (`KeyInterceptor.java:33`, parent verified).

## Decisions already taken by the parent (do not re-open them)

- **Pointer capture stays OFF by default** (`pointerCapture = false`): absolute pointer, one
  cursor (the app already hides Android's pointer icon over the view, research §1.3). Capture is
  not part of this round.
- **`pauseKeyInterceptingWithEsc` stays `false`**: Esc must reach the guest (vim, menus). The
  way back to Android is the system navigation gesture (swipe up from the bottom edge) and the
  power button; prove it in K5.
- `filterOutWinkey` stays `false`. `touchMode` belongs to the touch round: do not change it.
- The accessibility service is enabled by OUR app code, not by Termux:X11's
  `enableAccessibilityServiceAutomatically` path, so the logic can be unit-tested (see K2).
- The service's user-visible label is **`Omdroid keyboard capture`**.

## Hard rules

- Device: ONLY `<tablet serial>`. Another device may be attached: never touch it. **The tablet has a
  PIN lock**: never type or tap while `adb -s $TABLET_SERIAL shell dumpsys window | grep isKeyguardShowing`
  says true. If locked, wait with at most four calls of
  `timeout 380 bash -c 'while adb -s $TABLET_SERIAL shell dumpsys window | grep -q "isKeyguardShowing=true"; do sleep 10; done' || echo STILL-LOCKED`,
  then mark the device rows BLOCKED and finish the code rows.
- Stay awake: record `settings get global stay_on_while_plugged_in`, set `svc power stayon usb`,
  restore the recorded value at the end (and before you stop for any reason); read-back in the report.
- NEVER `adb install`/`uninstall`, `pm clear`, or delete under `files/usr`. Install only with
  `./install.sh <apk>` (on-device installer; 600 s timeout). Never run the packager.
- Gradle only in the FOREGROUND. Build:
  `rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug -Dorg.gradle.jvmargs="-Xmx8g -Dfile.encoding=UTF-8" --console=plain`.
  Gate after every code item: `./gradlew :app:compileDebugKotlin :app:test --console=plain`
  then `python3 docs/omarchy/tools/unit-count.py`. Never leave the tree red.
- Files you may change: `termux-x11/app/src/main/java/com/termux/x11/utils/KeyInterceptor.java`,
  `termux-x11/app/src/main/res/xml/accessibility_service_config.xml`,
  `app/src/main/AndroidManifest.xml`, `app/src/main/res/values/strings.xml`, the Termux:X11
  preferences block in `LauncherActivity.kt` plus ONE call site for K2 in `LauncherActivity.kt`,
  new files under `app/src/main/kotlin/com/phoshdroid/app/launch/` and their tests,
  `docs/omarchy/tools/**`, your report. Anything else: stop, say in the report what you would
  change and why.
- No git command that changes anything; the parent commits (including the submodule).
- Never `pkill -f` / `pgrep -f | kill`. No `sleep N; tail` calls.
- If a command is BLOCKED waiting for approval, do not retry or rephrase it; note it, go on.
- Scratch: `<scratch>/omarchy/r4/input/`.

## Items, in this order

### K0. Baseline (device)
Unlock/stay-awake as above. Record the installed version (`dumpsys package com.phoshdroid.app |
grep -E 'versionName|lastUpdateTime'`), `settings get secure enabled_accessibility_services`,
`./hc.sh j/devices` (keyboards and mice Hyprland sees, their names). Then with the X display on
top, the current behaviour for: `input keyboard text hello` into a foot window started with the
round-trip script from `docs/omarchy/brief-r3-device.md` item D9 (result read back from the guest);
`input keycombination KEYCODE_META_LEFT KEYCODE_2` (does `j/activeworkspace` change? what is on
top in Android afterwards?); `input mouse tap` on a bar workspace (x 128, y 26). These are
injected events: research §3.1 explains what they can and cannot prove. Record, do not judge.

### K1. KeyInterceptor names (code, submodule)
Research §2.1: build the component from the live package
(`new ComponentName(ctx, KeyInterceptor.class).flattenToString()`), use the same package name in
the `WRITE_SECURE_SETTINGS` dialog text, and fix `accessibility_service_config.xml`'s
`settingsActivity` (it points at a class that does not exist in this APK; remove the attribute).
In `app/src/main/AndroidManifest.xml` redeclare the service
(`com.termux.x11.utils.KeyInterceptor`) with `android:label="@string/key_capture_label"` and
`tools:replace="android:label"`; string `key_capture_label` = `Omdroid keyboard capture`. Check
the merged manifest (`app/build/intermediates/merged_manifest/debug/.../AndroidManifest.xml`
after `:app:processDebugMainManifest`) shows the new label once.

### K2. Our app enables the service (code)
New `launch/KeyCapture.kt`: a pure
`fun withService(current: String?, component: String): String` that returns the
`enabled_accessibility_services` value with `component` added once (colon-separated; empty or
null current -> just the component; never removes or reorders other entries; no duplicate), plus a
thin Android edge `fun enable(context: Context): Result` that, only when
`WRITE_SECURE_SETTINGS` is granted (`checkSelfPermission`), writes the merged list and
`accessibility_enabled=1`, and otherwise returns a value saying which gate is missing. Unit tests
for `withService`: empty, null, already present, other services kept, order kept. Call it from
`LauncherActivity.bootstrap()` before the hand-over, on `Dispatchers.IO`, log
`launch: key-capture <result>`; it must never fail the launch.

### K3. Preferences (code)
In the Termux:X11 block of `LauncherActivity.kt` set, with a one-line why each:
`preferScancodes = true`, `showIMEWhileExternalConnected = false`, `pointerCapture = false`,
`pauseKeyInterceptingWithEsc = false`, `filterOutWinkey = false`,
`enableAccessibilityServiceAutomatically = false` (our code enables it, K2),
`hardwareKbdScancodesWorkaround = false` and `enforceCharBasedInput = true` (research §2.2 calls
these two the likely regression: if K4's typing test fails with them, set them back to the
defaults `true`/`false`, rebuild, and report both results).

### K4. Build, grant, prove on the device
1. Build, gate, `./install.sh <apk>`.
2. Grants: `adb -s $TABLET_SERIAL shell pm grant com.phoshdroid.app android.permission.WRITE_SECURE_SETTINGS`;
   then try the restricted-settings gate from adb (research §2.3: `appops set ... allow` for the op
   that gates it; find the exact op name on this device with
   `adb -s $TABLET_SERIAL shell appops get com.phoshdroid.app`). Cold start (`./coldstart.sh 1 --tag k4`).
   Record the `launch: key-capture` line, `settings get secure enabled_accessibility_services`,
   and whether `dumpsys accessibility` shows the service BOUND. If it does not bind because of
   the restricted-settings gate, add `install.sh`-style instructions for Phil to the report
   (Settings -> Apps -> Omdroid -> three dots -> Allow restricted settings) and continue with
   the tests that do not need it, marking the rest BLOCKED.
3. Add the `pm grant` line to `docs/omarchy/tools/install.sh` after a successful install.

### K5. Keyboard and pointer tests (device)
Use a synthetic HID or uinput keyboard and mouse (research §3.1 and its Appendix: copy-paste
device descriptions), because `input` injection skips the accessibility filter (research §3.1)
and cannot prove SUPER. For each check: the command, the guest-side evidence, PASS/FAIL.
- Typing round trip: `Hello, World! 123` typed into the foot read-back script arrives exactly.
- SUPER+2 switches to workspace 2 (`j/activeworkspace`), and Android's app drawer does NOT open
  (`dumpsys activity activities | grep topResumedActivity` stays on the X display).
- SUPER+Return opens a terminal (`j/clients` count +1). SUPER+W closes it.
- Alt+Tab and SUPER+Tab: Android recents do not open (top activity unchanged).
- Esc reaches the guest (round-trip script reading a raw key, or a menu closed by Esc).
- Mouse: move, left click on a bar workspace switches it, right click, wheel scroll in foot
  (scrollback moves: read it with a script that prints 200 numbered lines first).
- The way back: the swipe-up-from-bottom navigation gesture
  (`input touchscreen swipe 1600 2130 1600 1500 200`) brings Android's home or recents forward.
- After K5, `./probe.sh` PASS.
If no synthetic-device route works on this device, record each attempt and its error, fall back
to `input` for what it can show, and say plainly which checks remain unproven.

### K6. Phil's checklist and clean-up
Write the manual checklist from research §3.3 into the report, adjusted to what you found (each
step: what to press on the real keyboard cover, what must happen). Close the windows you opened,
remove synthetic devices, restore stay-awake, put the read-back in the report.
Final sections: "What changed" (files), "Proven", "Not proven", "Phil must do once", "Files changed".

Final reply, at most 12 lines: one line per K-row with its decisive number, whether SUPER reaches
Hyprland, which grant (if any) Phil still has to make, the stay-awake read-back, the report path.


---

## PHASE B (added by the parent): K0, K4, K5, K6 on the device

The tablet is free and unlocked now. Phase A is committed (`24178f7`, submodule `77caf12`).

- **Do not build.** Two other agents are editing the tree right now (`rootfs/**`,
  `app/build.gradle.kts`, `docs/omarchy/r5-*`). The parent built the APK for you from commit
  `a34ce45` (touch fix + your keyboard work, nothing else):
  `<scratch>/omarchy/r4/input/omdroid-keys-a34ce45.apk`,
  sha256 `e8ec1ed0b975bdcd191c03477b93b7dcf226f463a7f9d4982a227b3aa0bfc0b2`.
  Install it with `./install.sh <that path>` (it now tries `pm install` from `/data/local/tmp`
  first; expect `INSTALL: PASS` and the same sha256).
- K4 step 1 is replaced by that install; step 3 (`pm grant` line in `install.sh`) stands.
- If the K5 typing test fails with `hardwareKbdScancodesWorkaround = false` /
  `enforceCharBasedInput = true`, do not rebuild: record the failure exactly (what was typed, what
  arrived) and the parent will build the alternative.
- Files you may change in this phase: `docs/omarchy/tools/**` and your report only.
- Taps now act as clicks (`touchMode = "2"`): a tap at a bar item clicks it.
- Everything else in the brief stands (keyguard rule, stay-awake record and restore, report rows,
  no `pkill -f`).
