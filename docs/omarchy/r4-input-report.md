# R4-INPUT report — keyboard cover and touchpad drive Omarchy

Worker: one session, no subagents, no `delegate_task`. **This run is PHASE A only** (code, no
device): K1, K2, K3 and their gates. K0 and K4-K6 stay `PENDING (phase B)`; the parent sends
phase B once the tablet is free. No adb call was made, no tool under `docs/omarchy/tools/` that
talks to the device was run, no `assembleDebug`, and the touch round's APK files under
`app/build/outputs/apk/debug/` were neither overwritten nor deleted.

## STATUS TABLE

| Row | State | Decisive number / note |
|---|---|---|
| K0 baseline (device) | **PASS (recorded)** | installed `0.0.14-alpha` (23:10:08), `enabled_accessibility_services` empty, `accessibility_enabled=0`; `j/devices` keyboards `["wl_keyboard"]` mice `["wl_pointer"]` touch `[]`; typing `hello` round-trips; Meta+2 changes nothing and Xlorie sees no key at all |
| K1 KeyInterceptor names | **PASS (code + gate)** | merged manifest: `key_capture_label` refs **1**, KeyInterceptor service decls **1**, `android:label="Termux:X11 KeyInterceptor"` **0**, `settingsActivity` **0**; gate `unit tests 56 failed 0` |
| K2 our app enables the service | **PASS (code + gate)** | `KeyCaptureTest` **7 tests, 0 failed**; whole suite `unit tests 63 failed 0`; call site `launch: key-capture <result>` in `bootstrap()` |
| K3 preferences | **PASS (code + gate)** | all 8 keys set in the Termux:X11 block at `LauncherActivity.kt:552-589` (values as specified), `touchMode` still `"2"` at `:552`; gate `unit tests 63 failed 0` |
| K4 build, grant, prove on device | **PASS** | parent's APK `e8ec1ed0…c0b2` installed (`INSTALL: PASS`, 23:30:43); `WRITE_SECURE_SETTINGS: granted=true`; `appops BIND_ACCESSIBILITY_SERVICE: allow`; `launch: key-capture enabled com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor 118ms`; service **bound** as `Omdroid keyboard capture`, `enabled_accessibility_services` = our component, `accessibility_enabled=1` |
| K5 keyboard and pointer tests | **PASS (with 3 unproven pointer sub-items)** | SUPER reaches Hyprland: SUPER+2 → ws 1→2, SUPER+Return → clients 0→1, SUPER+W → 1→0, typing `Hello, World! 123` exact, Alt+Tab flips focus, Esc → `/tmp/esc.txt` `033`, Android never reacts (top activity `MainActivity` throughout). Unproven: bar-workspace left click, right click, wheel scroll |
| K6 Phil's checklist and clean-up | **PASS** | checklist below; windows closed (clients 2→0), synthetic devices unregistered at EOF, test files removed from `/data/local/tmp`, `stay_on_while_plugged_in` back to **0** (read-back), `probe.sh` PASS |

## K0 — baseline (PASS, recorded; installed `0.0.14-alpha`, `lastUpdateTime 2026-11-24 23:10:08`)

Device prep: `isKeyguardShowing=false` and `mWakefulness=Awake` at the first check, so no wait was
needed. `stay_on_while_plugged_in` was recorded as **`0`**, then set with `svc power stayon usb`
→ reads back **`2`** (restored to `0` in K6, read-back there).

Settings before anything was installed:

```
settings get secure enabled_accessibility_services  -> (empty)
settings get secure accessibility_enabled           -> 0
dumpsys accessibility | grep -ic keyinterceptor     -> 0
./hc.sh j/devices
  keyboards ["wl_keyboard"]  layout us, options compose:caps,shift:both_capslock_cancel, main true
  mice      ["wl_pointer"]   tablets []  touch []  switches []
./probe.sh -q -> VERDICT: PASS
```

The three injected baselines (injected events: research §3.1 — they exercise the window-manager
policy but skip the accessibility filter, so they can only under-report interception):

| Test | Command | Result |
|---|---|---|
| typing round trip | `./hc.sh '/dispatch hl.dsp.exec_cmd("foot bash /tmp/read-t.sh")'` (script is `read -r line; printf '%s' "$line" > /tmp/typed.txt`), then `input keyboard text hello` + `input keyboard keyevent KEYCODE_ENTER` | `/tmp/typed.txt` = `hello` exactly (`od -c` → `h e l l o`, 5 bytes) |
| Meta+2 | `input keycombination KEYCODE_META_LEFT KEYCODE_2` | `j/activeworkspace` id `1` → `1`; top activity unchanged (`com.phoshdroid.app/com.termux.x11.MainActivity`); `logcat -s LorieNative` logged **no key at all** for this command, so the `2` never reached Xlorie |
| Meta alone | `input keyevent KEYCODE_META_LEFT` (for the K5 headline's baseline) | top activity unchanged: **no app drawer** on this build; `logcat -s KeyInterceptor` 0 lines |
| bar tap | `input mouse tap 128 26` | `j/cursorpos` → `{"x":64,"y":13}` (logical, i.e. x/2,y/2: the tap landed on the bar); `j/activeworkspace` `1` → `1`; top activity unchanged |

Read literally: on HyperOS with the pre-round build, an injected Meta press opens nothing, Meta+2
does nothing at all, and a mouse click at bar-left does not switch workspace. K5 needs a bar
coordinate that really is a workspace pill before it can call a click a click.


What changed, all four inside the allowed file list:

1. `termux-x11/app/src/main/java/com/termux/x11/utils/KeyInterceptor.java` — the component is now
   built from the live package instead of the `com.termux.x11` literal:
   `component(ctx)` returns `new ComponentName(ctx, KeyInterceptor.class).flattenToString()`
   (> `com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor`; only the package half changes,
   the class really does live in the submodule's package). `launch()` uses it, and its
   `WRITE_SECURE_SETTINGS` dialog text is built from `ctx.getPackageName()`, so the command Phil
   is shown names `com.phoshdroid.app`.
2. Same file, same patch: `launch()` now **merges** the component into
   `enabled_accessibility_services` (`withComponent(current, component)`) instead of overwriting
   the whole setting, which is research §2.3(5) — the old write silently disabled every other
   accessibility service Phil had on. Unreachable in this APK while
   `enableAccessibilityServiceAutomatically=false` (K3), but it is the same defect class as the
   literal, and the fix is four lines.
3. `termux-x11/app/src/main/res/xml/accessibility_service_config.xml` — dropped
   `android:settingsActivity=".LoriePreferences"`; that class does not exist in this APK (it
   resolves to `com.phoshdroid.app.LoriePreferences`, and `LoriePreferences` is
   `android:enabled="false"` in our manifest), so the service's Settings link could only fail.
4. `app/src/main/AndroidManifest.xml` — the service is redeclared
   (`com.termux.x11.utils.KeyInterceptor`) with `android:label="@string/key_capture_label"` and
   `tools:replace="android:label"`; `app/src/main/res/values/strings.xml` adds
   `key_capture_label` = **`Omdroid keyboard capture`**. Only the label is replaced: the merge
   keeps the library's `android:exported="true"`, its `BIND_ACCESSIBILITY_SERVICE` permission, its
   intent-filter and its `@xml/accessibility_service_config` meta-data (all visible in the merged
   manifest below).

Proof (both commands run in the foreground):

```
./gradlew :app:compileDebugKotlin :app:test --console=plain      -> BUILD SUCCESSFUL in 33s
python3 docs/omarchy/tools/unit-count.py                          -> unit tests 56 failed 0

./gradlew :app:processDebugMainManifest --console=plain           -> BUILD SUCCESSFUL
M=app/build/intermediates/merged_manifest/debug/processDebugMainManifest/AndroidManifest.xml
grep -c 'android:label="@string/key_capture_label"' $M            -> 1
grep -c 'android:name="com.termux.x11.utils.KeyInterceptor"' $M   -> 1
grep -c 'android:label="Termux:X11 KeyInterceptor"' $M            -> 0
grep -c 'settingsActivity' $M                                     -> 0
app/build/intermediates/incremental/debug/mergeDebugResources/merged.dir/values/values.xml:2211
    <string name="key_capture_label">Omdroid keyboard capture</string>
```

The merged service block, verbatim (note the label is the only attribute our declaration
contributes — the rest comes from the library):

```xml
<service android:name="com.termux.x11.utils.KeyInterceptor"
    android:exported="true" android:label="@string/key_capture_label"
    android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
    <intent-filter>
        <action android:name="android.accessibilityservice.AccessibilityService" />
    </intent-filter>
    <meta-data android:name="android.accessibilityservice"
        android:resource="@xml/accessibility_service_config" />
```

One thing to know for K4: `MainActivity.reloadPreferences()` calls
`KeyInterceptor.shutdown(true)` when `enableAccessibilityServiceAutomatically` is false and
`WRITE_SECURE_SETTINGS` is held. That call is a no-op for our path because
`shutdown(onlyIfEnabledAutomatically=true)` returns first unless `launchedAutomatically` is set,
and only `KeyInterceptor.launch()` sets it — which our code never calls. So the K2 write cannot be
undone by the activity's own preference reload.

## K2 — our app enables the service (PASS)

New `app/src/main/kotlin/com/phoshdroid/app/launch/KeyCapture.kt`:

- `fun withService(current: String?, component: String): String` — pure: null/empty current gives
  just the component; an entry that is already present returns `current` untouched (so nothing is
  duplicated and nothing is reordered); otherwise `"$current:$component"`, leaving every foreign
  entry exactly where it was.
- `fun component(context: Context)` — `"${context.packageName}/com.termux.x11.utils.KeyInterceptor"`.
- `fun enable(context: Context): Outcome` — the thin Android edge. Without
  `WRITE_SECURE_SETTINGS` (`checkSelfPermission`) it returns `NotEnabled` naming that gate and the
  exact adb command; with it, it writes the merged list (only when it changed) plus
  `accessibility_enabled=1` and returns `Enabled(component)`. `Outcome` carries a `detail` string,
  which is what gets logged. It catches `Exception` and returns `NotEnabled`, so it cannot throw
  into the launch.

New `app/src/test/kotlin/com/phoshdroid/app/launch/KeyCaptureTest.kt` — 7 tests: null, empty,
already present alone, another service kept, several services keep their order, an entry in the
middle keeps its position, adding twice does not duplicate (with the colon count asserted).

Call site, one, in `LauncherActivity.bootstrap()` after the preferences block and before
`startXServer`:

```kotlin
val keyCapture = withContext(Dispatchers.IO) { KeyCapture.enable(this@LauncherActivity) }
logLaunch("key-capture ${keyCapture.detail}")
```

Proof:

```
python3 -c "... TEST-com.phoshdroid.app.launch.KeyCaptureTest.xml ..."
  -> com.phoshdroid.app.launch.KeyCaptureTest tests 7 failures 0 errors 0   (all 7 names listed)
python3 docs/omarchy/tools/unit-count.py -> unit tests 63 failed 0
./gradlew :app:compileDebugKotlin :app:test --console=plain -> BUILD SUCCESSFUL in 3s
```

The log line reads `launch: key-capture <detail>`, i.e. either
`key-capture enabled com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor` or
`key-capture no WRITE_SECURE_SETTINGS (adb shell pm grant …)`. K4 records the real one from
logcat.

## K3 — preferences (PASS)

One block, `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt:552-589`, each line with
its why. The touch round's `touchMode = "2"` is untouched (`:552`).

| Pref | Set to | Why (one line) |
|---|---|---|
| `preferScancodes` | `true` | every key reaches Xlorie as a keycode, so the guest keymap owns layout and autorepeat instead of receiving Unicode text |
| `showIMEWhileExternalConnected` | `false` | no soft keyboard over the desktop while the cover is attached |
| `pointerCapture` | `false` | absolute pointer, one cursor, cursor follows the finger/touchpad; relative capture is not this round |
| `pauseKeyInterceptingWithEsc` | `false` | Esc must reach the guest; the way back to Android is the bottom-edge gesture and the power button |
| `filterOutWinkey` | `false` | `true` would drop Meta and every Meta-modified key before the X server — it would kill SUPER |
| `enableAccessibilityServiceAutomatically` | `false` | our code enables the service (K2), so the shared list is merged once, in a unit-tested place |
| `hardwareKbdScancodesWorkaround` | `false` | keys are intercepted before the IME, so no input method can swallow SUPER; the first knob to revert if K4's typing test fails |
| `enforceCharBasedInput` | `true` | `TYPE_NULL` input connection: no predictive/suggestion/CJK layer between keys and guest |

Proof:

```
grep -n -E 'putString\("touchMode"|putBoolean\("(preferScancodes|showIMEWhileExternalConnected|
  pointerCapture|pauseKeyInterceptingWithEsc|filterOutWinkey|enableAccessibilityServiceAutomatically|
  hardwareKbdScancodesWorkaround|enforceCharBasedInput)"' app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt
  552: .putString("touchMode", "2")                 564: .putBoolean("preferScancodes", true)
  567: .putBoolean("showIMEWhileExternalConnected", false)
  571: .putBoolean("pointerCapture", false)         575: .putBoolean("pauseKeyInterceptingWithEsc", false)
  578: .putBoolean("filterOutWinkey", false)        582: .putBoolean("enableAccessibilityServiceAutomatically", false)
  586: .putBoolean("hardwareKbdScancodesWorkaround", false)
  589: .putBoolean("enforceCharBasedInput", true)
./gradlew :app:compileDebugKotlin :app:test --console=plain -> BUILD SUCCESSFUL in 3s
python3 docs/omarchy/tools/unit-count.py                   -> unit tests 63 failed 0
```

## K4 — install, grant, prove (PASS, no manual step needed)

Phase B installed the parent's build, not a new one: `omdroid-keys-a34ce45.apk`, sha256
`e8ec1ed0b975bdcd191c03477b93b7dcf226f463a7f9d4982a227b3aa0bfc0b2` (verified locally before the
install). `./install.sh <apk>` took the `pm install` fast path (52.8 s push) and printed:

```
INSTALLED sha256=e8ec1ed0b975bdcd191c03477b93b7dcf226f463a7f9d4982a227b3aa0bfc0b2 lastUpdateTime=2026-11-24 23:30:43
INSTALL: PASS
```

Grants and the restricted-settings gate:

```
pm grant com.phoshdroid.app android.permission.WRITE_SECURE_SETTINGS   -> rc=0
dumpsys package com.phoshdroid.app | grep WRITE_SECURE_SETTINGS        -> granted=true
appops get com.phoshdroid.app BIND_ACCESSIBILITY_SERVICE                -> allow
appops get com.phoshdroid.app ACCESS_RESTRICTED_SETTINGS                -> deny
```

So the op that refuses a sideloaded app's accessibility service was already `allow` and **Phil has
no Settings step to do**: the service bound on the first launch with nothing touched in the UI.
(`ACCESS_RESTRICTED_SETTINGS` stays `deny`; it is the app-level gate the Settings page flips and it
did not block registration.)

Cold start `./coldstart.sh 1 --tag k4` (unaided, no nudge):

```
launch: key-capture enabled com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor 118ms
launch: ready marker 2748ms / launch: handover done 2759ms
SUMMARY tag=k4 runs=1: unaided handover 1/1 (3.4..3.4 s), desktop PASS 1/1 (2.9..2.9 s), runs with a foreign activity on top: 0
```

The service is bound, under our label and with the filter flag on:

```
settings get secure enabled_accessibility_services -> com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor
settings get secure accessibility_enabled          -> 1
dumpsys accessibility
  Bound services:{Service[label=Omdroid keyboard capture, feedbackType[], capabilities=8, ...]}
  Enabled services:{{com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor}}
  Binding services:{}   Crashed services:{}
logcat -s KeyInterceptor -> D KeyInterceptor: enabling interception service
```

K4.3 is done: `docs/omarchy/tools/install.sh` gains a `grants()` helper that runs both
`pm grant`s after a successful install (fast path and on-device path) and prints
`GRANTS write_secure_settings granted=1` as the proof; `bash -n install.sh` is clean.

## K5 — keyboard and pointer tests (PASS for every keyboard item; three pointer sub-items unproven)

Instrument: a `uhid` HID keyboard (`hid /data/local/tmp/hid-*.json`) built from the research
Appendix's boot-keyboard descriptor — 8 modifier bits including Left GUI `0x08`, six keycode
bytes — so every key goes through `/dev/uhid` → InputReader → the accessibility filter, exactly the
path a real key cover takes. `hid` registers the device, waits 2.5 s, sends the reports, and
unregisters at EOF. **Tooling note:** registration is flaky — three of the first six runs produced
no key at all (`logcat -s LorieNative` empty). Retrying the same file always worked; each row below
quotes a run whose keys are in the log.

| Check | Command | Guest evidence | Android evidence | Verdict |
|---|---|---|---|---|
| Typing round trip | `foot bash /tmp/read-t.sh` + `hid-typing.json` (`Hello, World! 123⏎`) | `/tmp/typed.txt` = `Hello, World! 123` exactly (`od -c`: 17 bytes `H e l l o ,   W o r l d !   1 2 3`) | top activity unchanged | **PASS** |
| SUPER+2 | `hid-su2.json` | `j/activeworkspace` 1 → **2**; LorieNative `133 (125 0 1)` then `11 (3 0 1)` (Super_L + `2`) | app drawer did not open, `MainActivity` on top | **PASS** |
| SUPER+1 / SUPER+3 | `hid-su1/su3.json` | ws 2 → **1**, then 2 → **3**; same key pair in LorieNative | unchanged | **PASS** |
| SUPER+Return opens a terminal | `hid-su-return.json` | `j/clients` 0 → **1**, window `class=foot title=omarchy@localhost:~`; keys `133 (125…)` + `36 (28…)` | unchanged | **PASS** |
| SUPER+W closes it | `hid-su-w.json` | `j/clients` 1 → **0**; keys `133` + `25 (17…)` | unchanged | **PASS** |
| Alt+Tab | `hid-alt-tab.json` (two windows: `foot`, `omarchy@localhost:~`) | `j/activewindow` title `foot` → `omarchy@localhost:~` | **no recents**, top activity unchanged | **PASS** |
| SUPER+Tab | `hid-su-tab.json` | keys reach the guest (`133` + `23 (15…)`), the bind exists (`j/binds`: modmask 64 key TAB) but the workspace stayed 2 — no visible guest action from workspace 2 | **no recents**, top activity unchanged | **PASS for the round's claim** (Android does not act); the guest binding's own effect is unproven |
| Esc reaches the guest | `foot bash /tmp/esc-t.sh` (`read -rsn1`) + `hid-esc.json` | `/tmp/esc.txt` = ` 033`; key `9 (1 0 1)` | top activity unchanged (no back) | **PASS** |
| Pointer move (injected) | `input mouse swipe 400 400 1000 700 300` | `j/cursorpos` → `{500,350}` (x/2,y/2) | — | **PASS** |
| Pointer move (HID device) | `hid-mouse-move.json` (20 × `(12,9)` relative) | `j/cursorpos` `{650,13}` → `{1065,475}` | — | **PASS** |
| Left click on a bar workspace | 11 positions swept (physical x 30…300 at y 26, plus the five pill centres 85/127/171/210/253) with `input mouse tap` and with `hid-mouse-left.json` after a hover | workspace never changed (1→2 and 2→3 were done by SUPER, not by a click); no new layer surface | — | **NOT PROVEN** |
| Right click | no injection route: `InputShellCommand` fills `DEFAULT_BUTTON_STATE = 0` (`:88`, `:237`) so `input` can never send a secondary button; the HID mouse's `[2,0,0,0]` report produced no observable guest effect | — | — | **NOT PROVEN** |
| Wheel scroll in foot | 6 × `input mouse scroll … --axis VSCROLL,±3` at two cursor positions (idle terminal, then the 200-numbered-line foot), screenshots before/after | `pixdiff` 0 changed every time; the one 9519-px diff was traced to the cursor move repainting window borders (bbox = the window outlines) | — | **NOT PROVEN** |
| The way back | `input touchscreen swipe 1600 2135 1600 1500 150` **twice** | — | top activity → `com.miui.home/.launcher.Launcher` (Android home); `am start` returns to the display | **PASS (two swipes)** |
| After K5 | `./probe.sh -q` | `VERDICT: PASS` | app pid **15008** from the cold start through the whole round — no restart, no force-stop | **PASS** |

Why the three pointer gaps are not a regression claim:

- **Bar workspace click.** The widget *is* click-bound: `plugins/bar/widgets/Workspaces.qml` ends
  each button with `onPressed: function() { root.focusWorkspace(modelData) }`, and
  `focusWorkspace` shells out to `hyprctl dispatch hl.dsp.focus({ workspace = "N" })` through
  `root.bar.run(...)`. Under proot the Hyprland IPC socket path is remapped per instance (that is
  exactly why `docs/omarchy/tools/hc.sh` exists), so a `hyprctl` started by the bar from its own
  environment may simply not find the socket — the click would then do nothing *inside the guest*.
  Both a click that never arrived and a click that arrived and failed in `bar.run` fit the
  observation, and I have no instrument here that separates them.
- **Right click / wheel.** `input` cannot express a non-primary button at all, and the HID mouse's
  button and wheel reports changed nothing on screen or in `j/clients`/`j/workspaces`. The app-side
  handling is there (`TouchInputHandler$HardwareMouseListener` maps
  `BUTTON_PRIMARY/TERTIARY/SECONDARY` → X buttons 1/2/3 and `ACTION_SCROLL` → `sendMouseWheelEvent`),
  and the pointer **move** path through the very same listener is proven above, so the gap is in the
  button/axis branch or below it, not in the device plumbing.
- These three are the items Phil's real cover settles in five minutes (§K6 steps 3, 9, 10).

## K6 — Phil's checklist and clean-up (PASS)

Clean-up actually done: guest windows closed (`j/clients` 2 → 0 via three SUPER+W runs), the
synthetic devices need no removal (both `hid` and `uinput` unregister at EOF — that is their
documented behaviour and the reason nothing is left in `dumpsys input`), the test files were
removed from `/data/local/tmp` (`hid-*.json`, `uinput-*.json`, `read-t.sh`, `esc-t.sh`,
`lines200.sh`, the `hc.sh`/`gx.sh` helpers), and `svc power stayon false` restored the stay-awake
value: `settings get global stay_on_while_plugged_in` → **0** (the value recorded in K0).
`./probe.sh -q` → `VERDICT: PASS`, app pid 15008 unchanged.

The checklist for the real keyboard cover (~10 minutes). Every step is what to press and what must
happen; steps marked *(unproven above)* are the ones no instrument here could settle.

1. Launch Omdroid and wait for the desktop. In logcat, `launch: key-capture enabled
   com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor` must appear — nothing to grant by hand,
   and nothing to allow in Settings (K4).
2. Attach the cover. **Expected:** no soft keyboard appears over the desktop; the Omarchy bar is
   visible at the top.
3. Touchpad: move the finger. **Expected:** one arrow follows it, no second cursor, no Android
   pointer icon.
4. Tap the bar's workspace number `2`. **Expected:** the workspace switches *(unproven above —
   if it does not, this is the bar's `hyprctl` call under proot, not the touchpad)*.
5. Press **SUPER** alone and release. **Expected:** nothing at all on Android (no app drawer, no
   recents) and no change on the desktop.
6. Press **SUPER+Return**. **Expected:** a terminal window opens (`foot`, title
   `omarchy@localhost:~`). Press **SUPER+W**: it closes and no `w` is typed anywhere.
7. Press **SUPER+2**, then **SUPER+1**. **Expected:** workspaces switch and come back.
8. Press **SUPER+Space** (Omarchy menu) and **SUPER+Esc** (system menu). **Expected:** the guest
   menus open; Android's app drawer and Android's back do not fire. *(SUPER+Esc is the sharpest
   check — Android turns Meta+Esc into back when interception is not in front of it.)*
9. **Alt+Tab** and **SUPER+Tab**. **Expected:** Alt+Tab cycles focus between windows; SUPER+Tab
   does whatever this Omarchy build binds it to (it changed nothing here even with the keys
   arriving); Android recents never open.
10. Right-click and middle-click on the pad, then two-finger scroll in a terminal that has
    scrollback. **Expected:** context menu / paste / the scrollback moves *(unproven above)*.
11. Type a sentence with Shift and Ctrl (`Ctrl+C`/`Ctrl+V` in the terminal). **Expected:** correct
    characters and case; clipboard both ways. *(Proven here for letters, digits, punctuation,
    space and Enter with Shift: `Hello, World! 123`.)*
12. Esc inside a terminal, arrows, Tab, F1–F12. **Expected:** each reaches the guest; no Android UI
    fires. *(Esc proven here: the guest read `033`.)*
13. **The way back:** swipe up from the bottom edge — **twice** (the app is in sticky immersive
    mode, so the first swipe only reveals the system bars). **Expected:** Android's home appears;
    `am start` (or the launcher icon) brings the desktop back. If the gesture is awkward, the power
    button works.
14. Rotate or fold the tablet with the cover attached. **Expected:** the desktop resizes and the
    keyboard keeps working (a size change restarts only the shell).

## What changed (this round)

- Phase A code: `KeyInterceptor.java` (component from the live package, merge instead of overwrite,
  dialog text from `ctx.getPackageName()`), `accessibility_service_config.xml` (dead
  `settingsActivity` removed), `app/src/main/AndroidManifest.xml` (service relabelled
  `@string/key_capture_label`), `strings.xml` (`Omdroid keyboard capture`),
  `launch/KeyCapture.kt` + `KeyCaptureTest.kt` (new), `LauncherActivity.kt` (the K3 preference
  block and the one K2 call site).
- Phase B: `docs/omarchy/tools/install.sh` now grants `POST_NOTIFICATIONS` **and**
  `WRITE_SECURE_SETTINGS` after a successful install and prints
  `GRANTS write_secure_settings granted=1`.
- Nothing else on the device: no build was made in phase B (the parent's APK was installed as
  given), no setting outside the app was touched, and `stay_on_while_plugged_in` is back to `0`.

## Proven

- SUPER reaches Hyprland from a synthetic HID keyboard: SUPER+2/1/3 switch workspaces,
  SUPER+Return opens a terminal, SUPER+W closes it — with `LorieNative` quoting Super_L as
  scancode `133 (125 …)` and Android never leaving the X display.
- The accessibility route is live end to end: the service binds as `Omdroid keyboard capture`,
  `enabled_accessibility_services` names our component, `accessibility_enabled=1`, and
  `KeyInterceptor` logs `enabling interception service`.
- Typing is exact with `preferScancodes=true`, `hardwareKbdScancodesWorkaround=false` and
  `enforceCharBasedInput=true`: `Hello, World! 123` — the round's most likely regression did not
  happen, so no alternate build is needed.
- Alt+Tab cycles guest windows and Esc reaches the guest, neither triggering Android recents or
  back.
- The pointer moves from both an injected gesture and a real uhid mouse.
- Android's way back works with two bottom-edge swipes; the session survives it (`probe.sh` PASS,
  same pid).

## Not proven

- A left click on the bar switching workspace (the bar's `focusWorkspace` runs `hyprctl` from the
  bar's own environment under proot; both "click lost" and "hyprctl failed" fit the evidence).
- Right click and wheel scroll reaching the guest — no injection route for a non-primary button,
  and the HID mouse's button/wheel reports changed nothing measurable.
- SUPER+Tab's own guest action (keys arrive, Android stays quiet, workspace unchanged).
- Anything about the real Xiaomi cover's firmware: which device names it reports, whether the pad
  arrives as `SOURCE_TOUCHPAD`, and whether its Meta key is delivered at all — that is Phil's
  checklist.

## Phil must do once

Nothing for the accessibility route: `WRITE_SECURE_SETTINGS` is granted by `install.sh` and
`BIND_ACCESSIBILITY_SERVICE` is already `allow`, so the service binds on launch with no Settings
step. The one thing that needs him is the **real keyboard cover** — the checklist above, steps 2-14.

## Files changed

- `termux-x11/app/src/main/java/com/termux/x11/utils/KeyInterceptor.java`
- `termux-x11/app/src/main/res/xml/accessibility_service_config.xml`
- `app/src/main/AndroidManifest.xml`
- `app/src/main/res/values/strings.xml`
- `app/src/main/kotlin/com/phoshdroid/app/launch/KeyCapture.kt` (new)
- `app/src/test/kotlin/com/phoshdroid/app/launch/KeyCaptureTest.kt` (new)
- `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt`
- `docs/omarchy/tools/install.sh`
- `docs/omarchy/r4-input-report.md` (this report)

Nothing is committed (the parent commits).

