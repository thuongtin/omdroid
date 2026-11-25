# R7 dock build report (host code round, no device)

Status: IN PROGRESS. Worker: one session, no subagents, no adb, no APK build.
Round: brief `docs/omarchy/brief-r7-dock-build.md`; research `docs/omarchy/r7-dock-research.md`.
Scratch: `<scratch>/omarchy/r7/dock/`.

## STATUS TABLE

| Step | What | Status | Proof |
| --- | --- | --- | --- |
| D0 | premises re-checked | **PASS** | 6 premises; 3 change the design, all below. |
| D1 | a1 `DockState` + a3 geometry/scale, pure + tests | **PASS** | `unit tests 98 failed 0`; commit `d1bd409` |
| D2 | a2 + pin, a4, a5, a7 wired into the launcher | **PASS** | Build + 98 tests + lint green; submodule `ac0cf73` |
| D3 | b1 keep_process_alive in the termux-x11 submodule | PENDING | |
| D4 | c live UI switch in the guest (`omarchy-watch.py`) + dry run | PENDING | |
| D5 | launch contract + README "Docking" | PENDING | |
| D6 | full gate re-run + tree sha | PENDING | |
| D7 | report complete (manual test, risks, not verified) | PENDING | |

## Steps

### D0. Premises

Checked against this box, not the research text. Six claims matter; three change
the design or bound it.

| # | Premise | Checked how | Result |
| --- | --- | --- | --- |
| P1 | `WindowManager.LayoutParams.setKeyboardCaptureEnabled` exists, gated by `CAPTURE_KEYBOARD` | AOSP `WindowManager.java` @ `android-17.0.0_r1`; `frameworks/base/core/res/AndroidManifest.xml` @ same tag | **True**, and the getter is `hasKeyboardCapture()` (not `isKeyboardCaptureEnabled`). Permission is `protectionLevel="normal"`, `featureFlag="com.android.hardware.input.request_key_capture_api"`. |
| P2 | compileSdk 35 may not have that API | `strings` on `android/view/WindowManager$LayoutParams.class` and `android/Manifest$permission.class` in `~/Android/Sdk/platforms/android-{35,36}/android.jar` | **True for both 35 and 36**: neither jar has `setKeyboardCaptureEnabled` and neither has `CAPTURE_KEYBOARD`. The call must be **reflection**; the `<uses-permission>` line is still added (an unknown normal permission is ignored at install on older platforms). |
| P3 | `setLaunchDisplayId` is public | same jars + `ActivityOptions.java` @ `android-17.0.0_r1:1698` | **True**, present in both jars (API 26+), so no reflection for a4. |
| P4 | A running task can be moved to another display by an app | `ActivityOptions.java:1849-1870` (`setMovableTaskRequired`), `AppTask.moveTaskTo`; `frameworks/base/AndroidManifest.xml:10252` | **False for a third-party app.** `moveTaskTo` needs `REPOSITION_SELF_WINDOWS`, protection `signature\|role`, and neither `moveTaskTo` nor `setMovableTaskRequired` is in the 35/36 jars. The only lever is to re-launch with `setLaunchDisplayId` and let the system decide. |
| P5 | The submodule manifest asks Samsung not to keep the process alive, and `colorMode` is missing from `configChanges` | `termux-x11/app/src/main/AndroidManifest.xml` at HEAD `77caf12` | **Both true**: `com.samsung.android.multidisplay.keep_process_alive = "false"`, and `configChanges` has `touchscreen|density|screenSize|smallestScreenSize|screenLayout` but **not `colorMode`** — the one entry the display-move doc names as a restart trigger. |
| P6 | The extra-key bar follows a preference write without any submodule change | `MainActivity.java:164` registers a `SharedPreferences.OnSharedPreferenceChangeListener`; `setTerminalToolbarView()` (686) reads `prefs.showAdditionalKbd.get()`; `BooleanPreference.get()` reads the store live | **True**, same process, same default prefs file — so a7 is a host-side pref write, no submodule edit. |

Design changes that follow:

1. **`UI_MODE_TYPE_DESK` does not decide "docked" on its own.** The research's a1
   rule was `docked = external != null || modeType == DESK`. A plain charging
   stand sets `UI_MODE_TYPE_DESK` too, and flipping Phil's phone to the desktop
   UI with no monitor attached would be a visible regression. `DockState`
   therefore docks only on an external display and reports `deskMode` in the
   status/log for the device round to confirm. (His goal sentence is about a
   monitor; a keyboard alone must never do it either.)
2. **A private external display still docks but is not launched onto.** The
   status carries `launchDisplayId = null` for a `FLAG_PRIVATE` display, and a4
   then takes today's plain launch — which is research route 1 ("the user opens
   Omdroid from the monitor's taskbar"). The research's §7 risk (the desktop
   session's display may be SystemUI-private) is therefore handled without an
   exception, and the log line marks it `private`.
3. **The pin is a second file**, `~/.config/omdroid/ui-pin`, holding `auto`
   (default when missing), `mobile` or `desktop`. `ui` stays the effective mode
   the guest reads. This is the brief's first option and it keeps
   `omdroid-ui.sh` unchanged: it already reads `ui` and defaults to `mobile`.

Also re-read in code for this round: `LauncherActivity` (all of it),
`DisplayShiftMonitor`, `SessionPrep`, `PhoshdroidApp`, `MainActivity`'s
preference/focus/toolbar paths, `LoriePreferences.Prefs`, `omdroid-ui.sh`,
`omarchy-watch.py`, `omarchy-plugin-index.sh`, `start.sh` (read only — the
sibling agent owns it), `docs/omarchy/launch-contract.md`.

### D1. a1 + a3, pure and tested

`app/src/main/kotlin/com/phoshdroid/app/launch/DockState.kt`

- `DisplayInfo(id, isDefault, isPrivate, isPresentation, width, height, densityDpi)`.
- `InputPresence(keyboard, mouse)` — physical alphabetic keyboard / physical
  mouse. Reported in the log line; **never decides `docked`** (a keyboard on the
  phone must not flip the UI).
- `DockState.decide(displays, inputs, deskMode)` → `DockStatus(docked,
  displayId, display, launchDisplayId, keyboard, mouse, deskMode)`.
  External = not the default display. Order: presentation first, then public
  before private, then lowest id — deterministic for a simulated display, a
  USB-C monitor and DeX alike.
- `DockState.logLine(status)` → `dock: docked display=2 1920x1080@213 kbd=1
  mouse=1`, `… private` for a private target, `dock: undocked`. The brief's
  format plus the two input flags (Phil's grep `dock:` still matches, and the
  flags are the evidence that Android saw his keyboard and mouse).

`app/src/main/kotlin/com/phoshdroid/app/launch/UiMode.kt` — the pin rule (D0
point 3) as pure code plus a small atomic writer:

- `UiMode.write(pin, current, docked)` returns the mode to write or null:
  a pin of `mobile`/`desktop` → null (never overwrite a hand choice); `auto`
  → `desktop` when docked, `mobile` when not, and null when `ui` already says it.
- `UiModeFile(rootfs).apply(docked)` → `UiModeOutcome(effective, written,
  reason)` where reason is `pinned`, `unchanged`, `docked` or `undocked`.
  Temp-file + rename, directory created on demand, one trailing newline.

`DisplayGeometry.forDisplay(displayWidth, displayHeight, densityDpi, rows,
shown, insets)` — the same prediction from the **target display's** real metrics
and density (density = dpi/160). `UiScale` needed no code change: its KDoc now
states that both numbers are the target display's.

Tests (`DockStateTest` 10, `UiModeTest` 13, `+3` in `DisplayGeometryTest`,
`+3` in `UiScaleTest`): 4K monitor, 1080p monitor, phone, private monitor,
public-vs-private, two monitors, keyboard-only, desk-mode-only, empty list; and
the pin/unchanged/write matrix with a real temp tree.

Gate: `./gradlew :app:compileDebugKotlin :app:test :app:lintDebug
--console=plain` → **BUILD SUCCESSFUL**; `unit-count.py` → **`unit tests 98
failed 0`** (from 69); lint 0 errors. Commit `d1bd409`.

### D2. The launcher side: a2 + pin, a4, a5, a7

**The Android edge** — `app/src/main/kotlin/com/phoshdroid/app/launch/DockStatusReader.kt`
reads displays (`isDefault`, `FLAG_PRIVATE`, presentation category, `getRealMetrics`,
`createDisplayContext` density so a DeX density override wins), physical inputs
(`isExternal && !isVirtual`, alphabetic keyboard — the same rule
`TouchInputHandler` uses for its own external-keyboard detection, so gpio-keys
volume buttons never count) and `UI_MODE_TYPE_DESK`, then calls the pure
`DockState.decide`.

**The process-level monitor** — `app/src/main/kotlin/com/phoshdroid/app/DockMonitor.kt`,
registered from `PhoshdroidApp` beside `DisplayShiftMonitor`. One
`DisplayManager.DisplayListener` for the application's lifetime (the launcher's
own lifecycle callbacks never fire while the X activity is on top), 400 ms
debounce for the added+changed+changed burst a plug produces, and a signature
filter so a refresh-rate or HDR change does not count as a dock change. Per
change it:

1. logs exactly one line, `dock: docked display=… …` / `dock: undocked`;
2. writes the guest's `ui` file through `UiModeFile` (pin rule honoured) and logs
   `dock: ui desktop written (docked)` / `dock: ui mobile kept (pinned)`;
3. writes `showAdditionalKbd`/`additionalKbdVisible` (a7). This is enough without
   a submodule change: `MainActivity` registers a
   `SharedPreferences.OnSharedPreferenceChangeListener` on the same default prefs
   file and `setTerminalToolbarView()` reads `showAdditionalKbd` live, so the bar
   appears and disappears in place;
4. when a session is already running **and** a monitor has just appeared,
   re-launches the X activity with `setLaunchDisplayId`. On undock it does not
   re-launch — Android migrates the removed display's windows to the default
   display and a re-launch would steal focus from whatever Phil is doing on the
   phone.

**a4 — how a running session reaches the monitor.** There is no supported API to
move a running task between displays for a third-party app (D0/P4:
`AppTask.moveTaskTo` needs `REPOSITION_SELF_WINDOWS`, `signature|role`, and is not
in the 35/36 jars). The route is a re-launch of the same `singleTask` activity
with `ActivityOptions.makeBasic().setLaunchDisplayId(id)` and
`FLAG_ACTIVITY_NEW_TASK`; the system then either moves the existing task or brings
it to the front on its current display, and no second instance can exist because
the manifest pins `singleTask`. Which of the two happens on One UI 8 is a device
fact (see "Not verified"); if it only comes to the front on the phone, opening
Omdroid from the monitor's own app drawer is the guaranteed route (research
route 1), and the session is on that display from the start.

`app/src/main/kotlin/com/phoshdroid/app/launch/DisplayLaunch.kt` is that call:
`options(displayId)` plus `start(context, intent, displayId)`, which catches
`SecurityException` (private display) and `IllegalArgumentException` (display
gone) and falls back to today's plain `startActivity`.

**Launcher wiring** (`LauncherActivity.kt`):

- `computeGeometry()`: docked, the prediction is the **target display's** real
  size at its own density with no extra-key gap (`DisplayGeometry.forDisplay`);
  undocked, unchanged.
- `bootstrap()`: reads the dock state once before the preference block, logs the
  `dock:` line, writes `showAdditionalKbd = !docked`, and passes
  `UiScale.resolve(choice, targetDensityDpi(dock), min(winWidth, winHeight))`, so a
  1080p monitor at 160 dpi resolves scale 1 even from a 420 dpi phone.
- `UiModeFile(rootfsDir).apply(docked)` right before `ProotService.start`, i.e.
  before `start.sh` runs `omdroid-ui.sh`; log line
  `launch: ui desktop docked 12345ms`.
- `forwardToMainActivity()` launches through `DisplayLaunch`, and its log line
  now carries `display=2 on-target=true`.

**a5 — keyboard capture.** Manifest: `<uses-permission
android:name="android.permission.CAPTURE_KEYBOARD"/>` (normal, install-time) and
the Samsung `com.samsung.android.dex.launchwidth/launchheight = 0` meta-data on
the X activity so DeX opens it full screen. Activity side, in the `termux-x11`
submodule (`ac0cf73`): `utils/KeyboardCapture.java` looks
`WindowManager.LayoutParams.setKeyboardCaptureEnabled(boolean)` up by reflection
and `MainActivity.onWindowFocusChanged` applies it when the LorieView's display is
not `DEFAULT_DISPLAY` (or DeX is on) and the window has focus, handing it back as
soon as focus leaves. compileSdk 35 has neither the method nor the constant (D0/P2),
so an older platform answers `NoSuchMethodException` and logs once; the
accessibility `KeyInterceptor` our launcher enables is untouched and stays the
fallback.

Gates: `:app:compileDebugKotlin :app:test :app:lintDebug` → **BUILD SUCCESSFUL**;
`unit tests 98 failed 0`; lint 0 errors. `KeyboardCapture.class` present in both
the debug and release javac outputs, so the submodule Java really compiled into
the APK.

### D3 submodule manifest
PENDING

### D4 guest live switch
PENDING

### D5 docs
PENDING

### D6 gate
PENDING

## Manual test for Phil

PENDING

## Risks still open

PENDING

## Not verified

PENDING
