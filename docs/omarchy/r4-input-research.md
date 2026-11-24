# R4-INPUT research — hardware keyboard and mouse in Omarchy (change plan, nothing implemented)

Worker: one session, no subagents, no `delegate_task`, no device, no adb, no gradle. Nothing in this
round is implemented; this file is the plan a later round executes. Every claim below cites what was
read. Anything I could not read is marked **guess** or listed under *Unknowns*.

Sources: the submodule `termux-x11/` at `phoshdroid-integration` (`c455fda`), this repo at `50af747`,
AOSP tag `android-16.0.0_r1` (fetched files kept in
`<scratch>/omarchy/r4/research-input/aosp/`), the guest payload at
`<scratch>/omarchy/upstream/`, and cage/wlroots sources already downloaded for the
touch round at `<scratch>/omarchy/r4/research-touch/` (wlroots 0.19-era X11 backend,
cage `seat.c`). The Google help page for restricted settings is pinned in §Change plan 3.

---

## 1. Today — what the source says about goals 1-4

### 1.1 Goal 1: every key reaches Hyprland with the right keysym

**The path, end to end.** Android `KeyEvent` → `MainActivity.mLorieKeyListener`
(`MainActivity.java:200-223`) → `TouchInputHandler.sendKeyEvent` (`TouchInputHandler.java:787-835`)
→ `InputEventSender.sendKeyEvent` (`InputEventSender.java:165-253`) → JNI
`sendKeyEvent` (`cpp/lorie/activity.c:340-349`) which writes `EVENT_KEY` with
`code = (scanCode ?: android_to_linux_keycode[keyCode]) + 8` → `cmdentrypoint.c:384-386`
(`QueueKeyboardEvents` on `lorieKeyboard`) → Xlorie's keymap → cage → Hyprland.

**SUPER never arrives today, and this is the round's central finding.** Android 16's
`PhoneWindowManager.interceptKeyBeforeDispatching` handles `KEYCODE_META_LEFT/RIGHT` itself: on down
it only sets `mPendingMetaAction` and returns `true`; on up it calls `launchAllAppsAction()` and
returns `true` (`PhoneWindowManager.java:3990-4019`). `return true` means the window never sees the
event. So **pressing Meta alone opens the app drawer and sends nothing to the app**, and a subsequent
`SUPER+W` arrives at the app as a plain `W` whose `metaState` has the Meta bit set
(`InputEventSender.java:189-194` then sends only the `W` scancode) — the guest types `w`. The same
switch consumes Meta+Tab (recents, `:3928-3947`), Alt+Tab (recents, `:3935-3945`), Meta+Esc (back,
`:3803-3809`), Meta+S (screenshot), Meta+L (lock), Meta+N (notifications), Meta+A (assistant),
Meta+I (settings), Meta+H/Enter (home shortcuts), Meta+Alt+T/3/4/5/6 (talkback/bounce/mouse-keys/
sticky/slow keys), Meta+Ctrl+Del (bugreport), Meta+Left/Right/Ctrl+dpad (split/desktop).
None of this is Samsung-specific: it is AOSP `PhoneWindowManager`, so HyperOS inherits it unless it
patches it (**HyperOS specifics: Unknown**).

**What does arrive.** Plain keys, Ctrl/Alt/Shift combinations, arrows, F1-F12, Esc, Tab, and
`SUPER+<key>` *as a bare key with a meta bit* — the modifier press itself is what is lost.
Round 1 already proved plain keys and Enter arrive in the guest: `adb shell input text hello` +
`KEYCODE_ENTER` into a `read -r` script produced `/tmp/typed.txt` = `hello`
(`device-bringup-report.md:9,94`).

**Two encoding paths, and the default one is wrong for a desktop.** `preferScancodes` defaults to
`false` (`preferences.xml:43`). With it false, any key pressed with no Alt/Ctrl/Meta and a non-zero
`getUnicodeChar()` is sent as a **Unicode text event**, not a key event
(`InputEventSender.java:196-213`): the guest gets a synthesized keysym press+release from
`ucs2keysym` (`cmdentrypoint.c:387-393`), Android's own autorepeat is dropped
(`InputEventSender.java:238-242`), and the guest keymap only ever sees text, never keycodes. With
`preferScancodes=true` every key takes the scancode branch (`:194`) and Xlorie's keymap decides.

**Xlorie's keymap** is compiled with the defaults baked into our build — rules `evdev`, model
`pc105`, layout `us`, empty variant/options (`cpp/recipes/xserver.cmake:16-23`), data root taken from
the guest's `xkeyboard-config-2` (`LauncherActivity.kt:670-691`) — and the keyboard device is
initialised with those defaults (`cpp/lorie/InitInput.c:54-74` passes `NULL` for RMLVO, so
`xkbInit.c:534-537` → `XkbGetRulesDflts`). The keycode table maps Android's Meta to Linux
`KEY_LEFTMETA`/`KEY_RIGHTMETA` (`cpp/lorie/lorie.h:302-303`), which is X keycode 133/134 and
Super_L/Super_R under evdev.

**The guest's own layout** is Hyprland's, twice over: Omarchy's default module reads
`/etc/vconsole.conf`'s `XKBLAYOUT` (fallback `us`) and sets `kb_options =
compose:caps,shift:both_capslock_cancel`, `repeat_rate = 40` (`upstream/usr/share/omarchy/default/hypr/input.lua:16-60`),
then the user module overrides `kb_layout` with `os.getenv("OMARCHY_KEYBOARD_LAYOUT") or "us"`
(`upstream/home/omarchy/.config/hypr/input.lua:1-9`), loaded *after* the defaults
(`.../hypr/hyprland.lua:33-38`). Nothing in the host sets `OMARCHY_KEYBOARD_LAYOUT`
(`ProotCommandBuilder.kt:96-160` has no such key), so **the desktop is US today**. Changing layout is
therefore a guest/Hyprland knob, not an X knob — see §2.7.

**cage does not translate keysyms.** It forwards the keycode it received
(`research-touch/seat.c:279-308`; only Alt+`XF86Switch_VT_*` is consumed, and only with
`allow_vt_switch`, `:256-277`), so Hyprland decodes with its own keymap. That is the behaviour we
want: one layout authority.

### 1.2 Goal 2: Android must not act on those keys, and there must be a way back

Today **Android acts on all of them**: Meta → app drawer, Meta+Tab / Alt+Tab → recents,
Meta+Esc → back (§1.1). The app has an opt-in escape hatch, and it is off by default:

- `KeyInterceptor` is an `AccessibilityService` that requests `FLAG_REQUEST_FILTER_KEY_EVENTS`
  when the activity has window focus (`KeyInterceptor.java:76-90`), which the platform documents as
  receiving "the key events before applications allowing it implement global shortcuts"
  (`AccessibilityServiceInfo.java:287-300`). Its config declares
  `canRequestFilterKeyEvents="true"` (`res/xml/accessibility_service_config.xml:1-9`).
- Its `onKeyEvent` forwards to `MainActivity.handleKey`, and returns that result
  (`KeyInterceptor.java:92-116`), so a consumed key never reaches `PhoneWindowManager`.
- Enabling it needs one of: the Settings UI (blocked for sideloaded apps — see §2.3), or
  `Settings.Secure.putString(ENABLED_ACCESSIBILITY_SERVICES …)` from the app, which needs
  `WRITE_SECURE_SETTINGS` (`KeyInterceptor.java:31-48`, pref
  `enableAccessibilityServiceAutomatically`, default `false`, `preferences.xml:49`).
- **That write is broken in our APK**: `launch()` writes the literal
  `"com.termux.x11/.utils.KeyInterceptor"` (`KeyInterceptor.java:33`). Our package is
  `com.phoshdroid.app`, so the string names a component that does not exist and the service is never
  enabled. The failure dialog text has the same bug (`KeyInterceptor.java:39-41` tells the user to
  grant the permission to `com.termux.x11`). Parent-verified.
- `filterOutWinkey` (default `false`, `preferences.xml:51`) makes `handleKey` drop Meta and any
  Meta-modified event (`MainActivity.java:725-729`) so Samsung DeX shortcuts still work; for us it
  must stay `false` or SUPER dies at the last step.
- `dexMetaKeyCapture` (default `false`, `preferences.xml:45`) is **Samsung-only**: it is a
  reflection call into `com.samsung.android.view.SemWindowManager` behind an availability check
  (`SamsungDexUtils.java:15-43`). On the Xiaomi tablet it is a no-op — do not rely on it.

**The way back to Android** already exists and is documented in the code: releasing Esc
(`InputEventSender.java:249-250` → `MainActivity.setCapturingEnabled(false)` →
`TouchInputHandler.java:398-409` releases pointer capture and, with `pauseKeyInterceptingWithEsc`,
stops key interception `:545-547`). With interception off, Meta/Meta+Tab/back work as Android
expects again, and the Android pointer returns. The same "give Android its input back" action is
available from the extra-key bar, the notification buttons and the swipe/volume actions
(`TouchInputHandler.java:473-490` maps `release pointer and keyboard capture`, and
`preferences.xml:66-76` defaults the second notification button to `exit`).

**Plain Esc is not turned into back.** `interceptKeyBeforeDispatching` has no `KEYCODE_ESCAPE`
case; the ESCAPE case that calls `closeSystemDialogs()` sits in `interceptUnhandledKey`
(`PhoneWindowManager.java:4673-4679`), whose own comment says it "is only called if the initial down
was unhandled" (`:4612-4613`). So Esc reaches the focused app first and only a *declined* press
closes system dialogs — good for goal 2 (Esc stays a guest key: Hyprland/`vim`/`htop` get it) and
the reason Esc can double as the capture-release key.

### 1.3 Goal 3: touchpad and mouse move Hyprland's cursor; one cursor on screen

**Mouse already works.** A hardware mouse (`SOURCE_MOUSE`) is routed before the finger branch
(`TouchInputHandler.java:301-304`) into `HardwareMouseListener` (`:837-905`): absolute cursor moves
when not captured (`:866-869`), `BUTTON_PRIMARY/TERTIARY/SECONDARY` → X buttons 1/2/3 with both
press and release (`:849-853`, `:898-902`), and `ACTION_SCROLL` → `sendMouseWheelEvent` scaled ×100
(`:858-864`) which the native side turns into wheel valuators divided by 120
(`cmdentrypoint.c:369-380`). Round 1 already proved a pointer event reaches Hyprland: `input tap`
moved `hyprctl -j cursorpos` y 192 → 429 (`device-bringup-report.md:9`).

**Touchpad.** A key-cover touchpad enumerates as `SOURCE_TOUCHPAD` with `TOOL_TYPE_FINGER`, which
the outer handler forwards to a nested handler created for exactly that
(`TouchInputHandler.java:205`, dispatch at `:271-276`); that handler's strategy is
`TrackpadInputStrategy`, i.e. relative motion (`:387-396`), taps become left clicks
(`TapGestureDetector`), and two-finger drag becomes wheel events through
`GestureListener.onScroll` → `mInputStrategy.onScroll` (`:598-640`, wheel at `:344`/`:862`).
None of this depends on `touchMode` (the launcher sets `touchMode=3`, direct touch,
`LauncherActivity.kt:536-543`), because the mouse/touchpad branches are tested before the
finger branch (`:271-304`).

**One cursor: three candidate images, and the source says the count is one plus a question mark.**
1. Android's own pointer icon is set to `PointerIcon.TYPE_NULL` as soon as the X client connects
   (`MainActivity.java:906`); the constant is documented as "Null icon. It has no bitmap."
   (`PointerIcon.java:67-68`). It is not re-set anywhere else, so a pointer icon change by the
   framework must be treated as possible — device check.
2. Hyprland *composites its own cursor into its buffer*: the guest user config sets
   `cursor = { no_hardware_cursors = true, use_cpu_buffer = true, hide_on_key_press = false,
   hide_on_touch = false, inactive_timeout = 0 }` with the comment "Weston reports no cursor plane
   for its X11 output on this device. Composite the cursor into Hyprland's output so it remains
   visible" (`upstream/home/omarchy/.config/hypr/looknfeel.lua:14-22`). Cursor size 36, Adwaita
   (`:49-51`).
3. Xlorie also draws an X cursor, as a GL texture at the X pointer position
   (`cpp/lorie/renderer.c:545-554`, `:745-751`). cage sets a cursor image of its own when the seat
   gains pointer capability (`research-touch/seat.c:129-133`, `DEFAULT_XCURSOR`) and only replaces
   it when a client calls `wl_pointer.set_cursor` (`:482-496`); the wlroots X11 backend turns that
   into a real X cursor (`research-touch/wlr-x11-output.c:447-466`). Since Hyprland with
   `no_hardware_cursors=true` does not set a cursor surface (aquamarine's Wayland backend only
   pushes a cursor surface on `setCursor`, `research-touch/Wayland.cpp:815-831`), cage's `left_ptr`
   is what the X server has — so image (3) is a duplicate arrow tracking the same coordinates as
   (2). Whether it is visible/doubled on the device is a *check*, not a claim (§4).

### 1.4 Goal 4: optional pointer capture

Fully implemented and off by default. `pointerCapture=false` (`preferences.xml:33`) →
`TouchInputHandler.setCapturingEnabled(true)` calls `View.requestPointerCapture()`
(`TouchInputHandler.java:398-409`), and the platform documents the effect: "When the window has
pointer capture, the mouse pointer icon will disappear and will not change its position", with mouse
events delivered as `SOURCE_MOUSE_RELATIVE` (relative in `getX/getY`) and touchpad events as
`SOURCE_TOUCHPAD` with `AXIS_RELATIVE_X/Y` (`View.java:31015-31055`). The app handles both
(`TouchInputHandler.java:870-895`), scales by `capturedPointerSpeedFactor` and
`transformCapturedPointer` (`:437-452`), and the documented way out is the same Esc:
`InputEventSender.java:249-250`. Note `TouchInputHandler.java:294-295` re-enables capture on every
`ACTION_UP`, so a tap after Esc turns capture back on — that is intended behaviour, worth knowing
before testing.

---

## 2. Change plan, ranked

Nothing here is done. Each item names the goal it serves and its cost/risk.

### 2.1 (P0) Fix `KeyInterceptor`'s component name, dialog text and label — goal 2, and a prerequisite for goal 1

Without this the whole accessibility route silently does nothing.

- `termux-x11/app/src/main/java/com/termux/x11/utils/KeyInterceptor.java:33`: replace the literal
  `"com.termux.x11/.utils.KeyInterceptor"` with a string built from the live package:
  `ctx.getPackageName() + "/" + KeyInterceptor.class.getName()` (or
  `new ComponentName(ctx, KeyInterceptor.class).flattenToString()`). Cost: one line, no behaviour
  change on a stock Termux:X11 build because there the two names coincide.
- `KeyInterceptor.java:37-44`: build the same string into the `WRITE_SECURE_SETTINGS` dialog text
  instead of `com.termux.x11`, so the instruction Phil is shown is `adb shell pm grant
  com.phoshdroid.app android.permission.WRITE_SECURE_SETTINGS`.
- Label: the submodule manifest declares the service as
  `android:label="Termux:X11 KeyInterceptor"` (`termux-x11/app/src/main/AndroidManifest.xml`,
  `<service android:name=".utils.KeyInterceptor">`). Redeclare the service in
  `app/src/main/AndroidManifest.xml` with `android:label="@string/accessibility_service_label"`
  plus `tools:replace="android:label"`, and add a string such as
  **"Omdroid keyboard capture"** (or just "Omdroid"). This is the name Phil will see in
  Settings → Accessibility, and the name he must allow restricted settings for.
- Optional: `res/xml/accessibility_service_config.xml:7` sets
  `android:settingsActivity=".LoriePreferences"`, which in the merged package resolves to
  `com.phoshdroid.app.LoriePreferences` — a class that does not exist, and `LoriePreferences` is
  disabled in our manifest anyway (`app/src/main/AndroidManifest.xml`, `android:enabled="false"`).
  Drop the attribute or point it at a real screen; otherwise the service's "Settings" link fails.

### 2.2 (P0) The preference set to write in the launcher block — goals 1, 2, 3, 4

`LauncherActivity.kt:536-558` is the only place that can set these: `LoriePreferences` is
`android:enabled="false"` in our manifest, so the submodule's settings UI is unreachable in the APK.
Values, with the default they replace and what each one changes:

| Pref | Today | Propose | What it changes | Cite |
|---|---|---|---|---|
| `preferScancodes` | `false` | **`true`** | every key becomes a keycode, not Unicode text; the guest keymap owns layout/autorepeat | `preferences.xml:43`, `InputEventSender.java:194-213` |
| `enableAccessibilityServiceAutomatically` | `false` | **`true`** (after §2.3) | `KeyInterceptor.launch()` on each prefs change while `WRITE_SECURE_SETTINGS` is held | `preferences.xml:49`, `MainActivity.java:627-631` |
| `pauseKeyInterceptingWithEsc` | `false` | **`true`** | Esc becomes "give Android its keys/pointer back"; also makes interception conditional on `keyIntercepting` | `preferences.xml:50`, `TouchInputHandler.java:404-408`, `:545-547`, `InputEventSender.java:249-250` |
| `filterOutWinkey` | `false` | **`false`** (keep) | `true` would drop Meta *and every Meta-modified key* before the X server sees it | `preferences.xml:51`, `MainActivity.java:725-729` |
| `pointerCapture` | `false` | **`true`** | relative mouse, Android pointer icon disappears | `preferences.xml:33`, `View.java:31015-31055` |
| `transformCapturedPointer` | `"no"` | `"no"` | only needed if relative motion comes out rotated; `"at"` = automatic for touchpads | `preferences.xml:34`, `TouchInputHandler.java:437-452` |
| `showIMEWhileExternalConnected` | `true` | **`false`** | stops the soft keyboard popping up over the desktop when the cover is attached | `preferences.xml:42`, `MainActivity.java:941-949` |
| `hardwareKbdScancodesWorkaround` | `true` | **`false`** | `true` routes hardware keys through normal dispatch so an IME can compose them (upstream issue #635); `false` intercepts them pre-IME, so no IME can eat SUPER. **Trade-off**, see risk | `preferences.xml:44`, `LorieView.java:707-722` |
| `enforceCharBasedInput` | `false` | **`true`** | sets the input connection to `TYPE_NULL`, suppressing suggestions/predictive/CJK composition | `preferences.xml:52`, `LorieView.java:802-813` |
| `touchMode` | `"3"` | keep `"3"` | direct touch for the finger; mouse/touchpad paths bypass it anyway | `LauncherActivity.kt:536-543`, `TouchInputHandler.java:271-304` |
| `dexMetaKeyCapture` | `false` | keep `false` | Samsung-only reflection; no-op on HyperOS | `preferences.xml:45`, `SamsungDexUtils.java:15-43` |

Risk on `hardwareKbdScancodesWorkaround=false`: it is the pref upstream added *because* pre-IME
interception made hardware keys invisible to IMEs (`git log -1 3c8cc75`, issue 635 fetched:
"[Bug]: hardware keyboard does not work with IME"). On this tablet the only IME we want is the
extra-key bar's own input, which is why `enforceCharBasedInput=true` should be tried in the same
round; if typing into the guest breaks, flip it back to `true` first — that is the single most
likely regression in this plan.

Risk on `enforceCharBasedInput=true`: no CJK composition and no predictive text from the soft
keyboard. Acceptable for a desktop, and reversible per session.

Implementation note: the block currently ends in `.apply()` (`LauncherActivity.kt:558`). These keys
must be written **before** `startXServer`/hand-over (they already are, same block), and the
accessibility grant (§2.3) must happen before the first key press, otherwise the first Meta press
still opens the drawer.

### 2.3 (P0) The one-time grant and the "restricted settings" step — goal 2

The service cannot be enabled until two independent gates are open.

1. **Permission.** `WRITE_SECURE_SETTINGS` is already declared
   (`termux-x11/app/src/main/AndroidManifest.xml`, `<uses-permission android:name=
   "android.permission.WRITE_SECURE_SETTINGS">`), but it is signature|privileged, so it must be
   granted over adb: `adb -s <serial> shell pm grant com.phoshdroid.app
   android.permission.WRITE_SECURE_SETTINGS`. With it, the in-app
   `Settings.Secure.putString` path works (`KeyInterceptor.java:31-48`).
2. **AppOps.** Since Android 13, an accessibility service of a sideloaded app is refused at
   registration if the `BIND_ACCESSIBILITY_SERVICE` app-op is not allowed:
   `AccessibilitySecurityPolicy.canRegisterService` skips any service whose
   `AppOpsManager.noteOpNoThrow(OPSTR_BIND_ACCESSIBILITY_SERVICE, …)` is not `MODE_ALLOWED`
   (`AccessibilitySecurityPolicy.java:599-628`). The user-facing unlock is Settings → Apps →
   Omdroid → ⋮ (More) → **Allow restricted settings** (Google's own steps:
   <https://support.google.com/android/answer/12623953>, "Allow restricted settings"; Android 13+).
   Writing the setting *first* and then allowing restricted settings is fine — the service
   registers on the next accessibility-service refresh.
3. Preferred order for a scripted install (`docs/omarchy/tools/install.sh` already verifies the
   installed sha256, and `adb install` itself is refused on HyperOS, so the on-device installer is
   what puts the APK down): open Settings → Apps → Omdroid → ⋮ → Allow restricted settings, then
   `pm grant`, then launch. `adb shell appops set com.phoshdroid.app BIND_ACCESSIBILITY_SERVICE allow`
   is the shortcut for step 2 **if HyperOS honours it** — *Unknown*, verify before relying on it in
   a script.
4. Verification that the gate is open, without the UI: after launch, with `enableAccessibilityServiceAutomatically=true`,
   `adb shell settings get secure enabled_accessibility_services` must list
   `com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor` (the class keeps its `com.termux.x11`
   name because it lives in the submodule package, only the *package* part changes), and
   `adb shell dumpsys accessibility | grep -i keyinterceptor` must show it bound. If the app-op is
   still denied, the setting can be written and still not bind — that distinction is the whole point
   of checking both.

5. **Do not clobber the user's other accessibility services.** `KeyInterceptor.launch()` writes the
   **whole** `Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES` string
   (`KeyInterceptor.java:33`), so enabling Omdroid's capture silently disables anything else Phil has
   turned on (a password manager, TalkBack, a gesture app) and leaves it off after the session ends.
   The same patch as §2.1 should read the current value, append `:<component>` if absent, and only
   then write. Cost: three lines. Risk if skipped: a user-visible regression outside this app.

### 2.4 (P1) Keep the guest out of the picture for SUPER — goals 1, 2

No guest change is required for SUPER to work: the X keymap already maps 133/134 to
Super_L/Super_R (`cpp/recipes/xserver.cmake:16-23` + `lorie.h:302-303`), and Hyprland binds on
keysyms it derives from its own `kb_layout`. What *is* required is that the Meta press/release
reaches Xlorie at all, which is §2.1-2.3. Do **not** add a guest-side "synthesise Super" hack: it
would double-press once the accessibility route works.

### 2.5 (P1) Interception follows window focus — know it before testing — goals 1, 2

`LaunchReadiness`/`SessionPrep` are out of scope, but one interaction is worth noting for the
implementer: `KeyInterceptor.recheck()` only requests key filtering while
`MainActivity.hasWindowFocus()` (`KeyInterceptor.java:76-90`, called from
`MainActivity.java:772-774`), so any Android overlay that takes focus (permission dialog,
notification shade, recents) suspends interception and the next Meta press goes to Android. That is
the desired fail-safe, not a bug — but a test that taps the screen and then presses SUPER can see
one swallowed press. Wait for focus before asserting.

### 2.6 (P2) Pointer capture as an opt-in, not the default — goal 4

`pointerCapture=true` gives relative motion and removes Android's pointer, at the cost of "the
cursor stops at the edge of nothing" (no absolute positioning; the guest cursor can hit the screen
edge and stay). Two acceptable end states: (a) `pointerCapture=false` — absolute motion, cursor
follows the finger/mouse, one cursor as today; (b) `pointerCapture=true` — relative motion, Esc
releases. Recommend shipping (a) as the default and exposing (b) as the documented Esc-released
mode, because §1.3 already gives a consistent absolute cursor and Phil's first complaint is about
keys, not acceleration.

### 2.7 (P2) Layouts other than US — goal 1

Three levers, in order of preference:
1. Set `OMARCHY_KEYBOARD_LAYOUT` in the guest env from the host
   (`ProotCommandBuilder.kt:96-160` builds the env list; add the key there) — the user module reads
   it and only the first entry drives Hyprland's bindings
   (`upstream/home/omarchy/.config/hypr/input.lua:1-9`, and the default module's comment about
   "first entry in kb_layout", `default/hypr/input.lua:38-46`).
2. Or write `XKBLAYOUT=`/`XKBVARIANT=` into the guest's `/etc/vconsole.conf` at image build time —
   that is what the default module reads when `OMARCHY_KEYBOARD_LAYOUT` is unset.
3. Runtime, per session: `hyprctl switchxkblayout current <next|prev|ID>`; the wiki documents
   `current`, `all` and numeric IDs, and that `hyprctl devices` is how you find the device name
   (<https://wiki.hypr.land/configuring/core/advanced-configuration/using-hyprctl>, section on
   `switchxkblayout`).
With `preferScancodes=true` this is the *only* layout authority: Xlorie's keymap only decides the
keysyms cage sees, and Hyprland re-derives its own.

---

## 3. Test plan

### 3.1 What a script can do over adb as uid `shell` on Android 16

`input` is a shell command that injects through `InputManager.injectInputEvent`
(`InputShellCommand.java:140-142`). Its subcommands on `android-16.0.0_r1` are `text`, `keyevent`,
`tap`, `swipe`, `draganddrop`, `press`, `roll`, `scroll`, `motionevent`, `keycombination`
(`InputShellCommand.java:288-311`, help text `:319-361`), with an optional source prefix from
`keyboard, dpad, gamepad, touchscreen, mouse, stylus, trackball, touchpad, touchnavigation,
joystick, rotaryencoder` (`:112-129`) and an optional `-d <displayId>`.

Three properties matter for honest testing:

- **`keycombination` exercises the window-manager policy, but it CANNOT exercise the accessibility
  filter.** It holds the named keys down together and injects them **async precisely so**
  "interceptKeyBeforeQueueing or interceptKeyBeforeDispatching could handle keys"
  (`InputShellCommand.java:732-735`). What it does *not* do is pass through the accessibility input
  filter: in `InputDispatcher`, `mPolicy.filterInputEvent` is called only from `notifyKey`
  (`InputDispatcher.cpp:4493`) and `notifyMotion` (`:4618`) — the paths InputReader feeds from a real
  device — while `injectInputEvent` (`:4776-4866`) goes straight from
  `interceptKeyBeforeQueueing` (`:4832`) into the inbound queue. **So an injected Meta press is
  consumed by `interceptKeyBeforeDispatching` even when our service is enabled, and no `input …`
  test can ever show the interception working.** That is the trap the brief warns about, pointing
  the other way: injection bypasses the filter and therefore only produces false negatives for
  goal 2. Proof of interception must come from a real InputReader device — `uinput`/`hid`
  (§3.2 T10/T11) or Phil's hands (§3.3).
- **The filter really does sit in front of the Meta/Tab policy for real devices.** Real keys take
  `interceptKeyBeforeQueueing` → `filterInputEvent` (accessibility, can consume) → enqueue →
  `interceptKeyBeforeDispatching` (the Meta/recents/back switch, `:6643`). The filter's only gate is
  `FLAG_PASS_TO_USER` (`AccessibilityInputFilter.java:351-395`, gate at `:366-372`), which
  `interceptKeyBeforeQueueing` sets for every key while the device is interactive
  (`PhoneWindowManager.java:5226-5242`) — so Meta, Tab and Esc are all offered to the service.
  Unhandled events are re-injected into the app stream (`KeyEventDispatcher.java:257-279`).
- **`uinput` and `hid` exist and are the "real device" tools.** `uinput -` takes evemu recordings
  or a JSON-ish command stream with `register` (name, vid, pid, bus, `UI_SET_*` configuration) and
  event commands; the README also documents `delay` and the CTS examples
  (`cmds/uinput/README.md`, whole file). `hid -` registers a `uhid` device from a **USB HID report
  descriptor byte array**, which is the only way to synthesise a keyboard whose raw descriptor
  actually contains a Meta/GUI usage (`cmds/hid/README.md:29-70`). Both go through `/dev/uinput` /
  `/dev/uhid` and InputReader, so they are closer to the real key cover than `input`; whether uid
  `shell` may open those nodes on HyperOS is *Unknown* (CTS runs them as shell, so it normally can).

What each test proves, and what it does not: `input` proves the app+policy+guest path for keys the
policy does not consume, but because `injectInputEvent` skips `filterInputEvent` it can never prove
that the accessibility interception works — only a false negative can come from it. `uinput`/`hid`
feed InputReader, so they exercise both the filter and the app path; **none** of them proves what the
Xiaomi cover's firmware actually sends (§4).

### 3.2 Host-side tests (run after each build)

Set up once: `<serial>` = `TABLET_SERIAL` per `docs/omarchy/tools/` convention (the tools refuse to
run without it), and a guest shell helper (`docs/omarchy/tools/` has `gx.sh`/`sx.sh` style wrappers
from earlier rounds; use `hyprctl` in the guest).

| # | Command | Expected guest-side evidence | What it proves |
|---|---|---|---|
| T0 | `adb -s <serial> shell settings get secure enabled_accessibility_services` then `dumpsys accessibility \| grep -i keyinterceptor` | the string lists `com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor`; dumpsys shows it bound | §2.1-2.3 landed and the app-op is open |
| T1 | **control (policy path)**: desktop focused, `input keycombination KEYCODE_META_LEFT KEYCODE_TAB` | Android recents appear; `hyprctl -j activeworkspace` unchanged | the Meta/Tab policy is live on this device (matches `PhoneWindowManager.java:3928-3947`) |
| T2 | **control (policy path)**: `input keyevent KEYCODE_META_LEFT` (down+up) | Android app drawer appears | reproduces Phil's "app drawer on Meta" from source (`:3990-4019`); also proves `input` reaches the policy at all |
| T3 | **predicted FAILURE, keep it in the record**: with the service ON and a guest terminal focused, `input keycombination KEYCODE_META_LEFT KEYCODE_3` | the drawer still opens and the guest receives a bare `3` | injection skips the accessibility filter (§3.1), so this row must fail even when the feature works — do not treat it as a regression |
| T4 | service ON, `input keycombination KEYCODE_META_LEFT KEYCODE_2` | expected: workspace stays put (the modifier press was eaten at dispatch) — record the actual `hyprctl -j activeworkspace` id | shows the injection limitation, not the feature; superseded by T10/T11 |
| T5 | service ON, `input keycombination -t 200 KEYCODE_META_LEFT KEYCODE_ENTER` | expected: a bare Return reaches the guest, no new window from a SUPER bind | same limitation |
| T6 | service ON, focus in a guest terminal: `input text hello` + `input keyevent KEYCODE_ENTER` into the round-1 `read -r` script | `/tmp/typed.txt` = `hello` (`device-bringup-report.md:9`) | text still works with `preferScancodes=true` (scancode 0 → keycode table fallback, `lorie.h:214+`) |
| T7 | `input mouse tap 1600 1000` | `hyprctl -j cursorpos` moves to ≈ (800, 500) scaled; a click lands | absolute pointer + left button |
| T8 | `input mouse swipe 800 600 1200 600 300` and `input mouse scroll 800 600 --axis VSCROLL,-2` | cursorpos follows the swipe; a scrollable guest app scrolls | right/middle/scroll plumbing (`TouchInputHandler.java:837-905`, `cmdentrypoint.c:369-380`) |
| T9 | `input touchpad swipe 500 500 900 500 300` | cursorpos moves in the same direction; two-finger drag (second finger) scrolls | the touchpad branch, i.e. the key cover's pad path |
| T10 | **acceptance for goals 1+2**: `uinput /data/local/tmp/kbd.json` registering a keyboard with `UI_SET_KEYBIT` including `KEY_LEFTMETA` (125) and `KEY_2`/`KEY_ENTER`, then event commands pressing Meta with `2`, and Meta with `ENTER` | `hyprctl -j activeworkspace` → the second workspace after the `2` combo; `hyprctl -j clients` gains a terminal after the `ENTER` combo; **no** app drawer/recents anywhere | the only scriptable path that passes through InputReader, i.e. through the accessibility filter — this is the row that can actually go green for SUPER. Also proves the app path with a *device*, and logs `DEVICES found device "…"` (`TouchInputHandler.java:238-262`) |
| T11 | **acceptance, closest to the cover**: `hid /data/local/tmp/kbd.json` with a HID report descriptor that contains usage `0xE3` (Keyboard Left GUI) and `0xE2`, then `hid` input reports pressing it together with `0x1E` (`2`) | same evidence as T10 | a real `uhid` keyboard whose descriptor has a Meta usage, i.e. the synthetic analogue of the Xiaomi cover |
| T12 | with `pointerCapture=true`: press Esc | Android pointer returns (screencap), `dumpsys input` no longer reports the pointer captured; the next tap re-captures (`TouchInputHandler.java:294-295`) | §1.4's documented way out, `InputEventSender.java:249-250` |

Notes for the implementer of these tests: watch `adb logcat -s DEVICES KeyInterceptor KeyEvent
LorieNative` — `KeyInterceptor` logs "enabling interception service"/"disabling interception
service" (`KeyInterceptor.java:71-84`) and `LorieNative` logs every key it queues
(`activity.c:343`), which is the cheapest way to tell "the key never arrived" from "the guest
dropped it". `hyprctl devices` is the guest-side device/layout list (documented as "lists all
connected keyboards and mice",
<https://wiki.hypr.land/configuring/core/advanced-configuration/using-hyprctl>); read its exact
field names once on the device before scripting against `-j` (§4).

### 3.3 Phil's manual checklist (real keyboard cover, ~10 minutes)

1. Install, allow restricted settings for Omdroid (§2.3), grant `WRITE_SECURE_SETTINGS`, launch,
   wait for the desktop.
2. Attach the cover. **Expected:** no soft keyboard appears; the Omarchy bar is visible.
3. Tap the bar with the touchpad. **Expected:** the cursor moves, the click registers, exactly one
   arrow is visible.
4. Press **SUPER** alone and release. **Expected:** nothing opens on Android (no app drawer), and
   the desktop does not change. *This is the round's headline check.*
5. Press **SUPER+Return**. **Expected:** a terminal window opens in Omarchy
   (`default/hypr/bindings/applications.lua:2`).
6. **SUPER+2**, then **SUPER+1**. **Expected:** workspaces switch and come back (bound on keycodes
   10-19, `bindings/tiling.lua:21-22`).
7. **SUPER+W** on a window. **Expected:** the window closes (`bindings/tiling.lua:1`); no `w` is
   typed anywhere.
8. **SUPER+Space**. **Expected:** the Omarchy menu opens (`bindings/utilities.lua:1`), and the
   Android app drawer does not.
9. **SUPER+Esc**. **Expected:** Omarchy's system menu opens (`bindings/utilities.lua:8`). This is the
   sharpest single check in the list: Android turns Meta+Esc into *back*
   (`PhoneWindowManager.java:3803-3809`), so a working system menu means interception beat the
   policy; a trip to the previous app means it did not.
10. **Alt+Tab** and **SUPER+Tab**. **Expected:** Alt+Tab cycles focus between windows
    (`bindings/tiling.lua:47`), SUPER+Tab changes workspace (`:33`) — **not** Android recents, which
    is what both do today (`PhoneWindowManager.java:3928-3947`).
11. Type a sentence with Shift/Ctrl (Ctrl+C, Ctrl+V in the terminal). **Expected:** correct
    characters, correct case, clipboard both ways.
12. Arrows, Tab, Esc inside the terminal; F1–F12 (e.g. `SUPER+F1` if bound, or `cat -v` in the
    terminal to see escape codes). **Expected:** each reaches the guest, none triggers an Android UI.
13. **Esc** once. **Expected:** the desktop keeps running, Android gets its keys back — press
    **SUPER** now and the app drawer *does* open; tap the screen to re-capture.
14. Right-click and middle-click on the touchpad (two-finger tap / three-finger tap or the pad's
    click buttons), then two-finger scroll in a browser window. **Expected:** context menu,
    paste/middle behaviours, page scrolls.
15. Rotate or fold the tablet with the cover attached. **Expected:** the desktop resizes and the
    keyboard keeps working (a size change restarts only the shell).

---

## 4. Unknowns only a device can answer

1. **HyperOS.** Whether HyperOS 3 patches `PhoneWindowManager`'s Meta handling, or adds shortcuts of
   its own on top (assistant key, `Alt+Tab`, Meta+letter). AOSP source cannot tell us; T1/T2 on the
   device is the measurement.
2. **Whether the restricted-settings gate can be bypassed over adb** on HyperOS
   (`appops set com.phoshdroid.app BIND_ACCESSIBILITY_SERVICE allow`), and whether the in-app
   `Settings.Secure` write then binds (`AccessibilitySecurityPolicy.java:618-625` is the gate).
3. **What the cover actually reports**: device names and sources for `Xiaomi Focus Pen Pro Keyboard`
   / `… Mouse`, whether the pad arrives as `SOURCE_TOUCHPAD` with `TOOL_TYPE_FINGER` (the branch at
   `TouchInputHandler.java:271-276` assumes it), whether the keyboard reports scancodes or 0 (which
   decides whether `preferScancodes` gives us the guest keymap or falls back to
   `android_to_linux_keycode`), and whether a Meta press is even delivered by the firmware.
4. **Cursor count on the glass.** §1.3 predicts Hyprland's composited cursor plus a possible
   duplicate X cursor from cage's `left_ptr`. A `screencap` of a region with the pointer parked on a
   contrasting background settles it; if doubled, the cheapest fix is guest-side (let Hyprland own
   the only cursor, e.g. by having cage's X cursor go transparent), not another pref.
5. **`hyprctl -j devices` field names** on this Hyprland build (`/opt/omarchy-android/hyprland`) —
   read them once before a script greps them. Hyprland's own man page documents `devices` only as
   "Lists all connected input devices" (`docs/hyprctl.1.rst:88-90`,
   <https://github.com/hyprwm/Hyprland/blob/v0.57.2/docs/hyprctl.1.rst>), so the JSON field names
   are unverified here; the wiki's `switchxkblayout` section is what documents `current`/`all`/IDs
   (<https://wiki.hypr.land/configuring/core/advanced-configuration/using-hyprctl>).
6. **Whether `uinput`/`hid` may open `/dev/uinput`/`/dev/uhid` as uid `shell`** on this device.
7. **`hardwareKbdScancodesWorkaround=false` side effects** on HyperOS's IME — the one setting in
   §2.2 that can plausibly break typing; if it does, revert to `true` and rely on
   `enforceCharBasedInput` alone.
8. **Whether the extra-key bar is still needed** once the cover works: with `showAdditionalKbd=true`
   the bar occupies height that `DisplayGeometry` already predicts (`LauncherActivity.kt:312-335`),
   so turning it off is a geometry change, not just a visual one — measure the X root before/after.

---

## Appendix — copy-paste synthetic devices for T10/T11

Both tools read a file or stdin, both unregister the device at EOF, so keep the process alive
(`uinput -` / `hid -`) when the test needs the device to persist between commands
(`cmds/uinput/README.md` "Notes", `cmds/hid/README.md` "Notes"). Command shapes are from those two
READMEs at `android-16.0.0_r1`: `register`, `delay {duration}`, `inject {events:[…]}`,
`sync {syncToken}`, `updateTimeBase` for uinput; `register`, `delay`, `report {report:[…]}` for hid.

`/data/local/tmp/uinput-kbd.json` — a keyboard that has a Meta key, pressing **Meta+2**:

```json5
{"id":1,"command":"register","name":"Omdroid Test Keyboard","vid":0x18d2,"pid":0x2c42,"bus":"usb",
 "configuration":[{"type":"UI_SET_EVBIT","data":["EV_KEY"]},
                  {"type":"UI_SET_KEYBIT","data":["KEY_LEFTMETA","KEY_ENTER","KEY_2"]}]}
{"id":1,"command":"delay","duration":800}
{"id":1,"command":"inject","events":["EV_KEY","KEY_LEFTMETA",1, "EV_SYN","SYN_REPORT",0,
                                     "EV_KEY","KEY_2",1,        "EV_SYN","SYN_REPORT",0]}
{"id":1,"command":"delay","duration":200}
{"id":1,"command":"inject","events":["EV_KEY","KEY_2",0,        "EV_SYN","SYN_REPORT",0,
                                     "EV_KEY","KEY_LEFTMETA",0, "EV_SYN","SYN_REPORT",0]}
{"id":1,"command":"sync","syncToken":"done"}
```

`/data/local/tmp/hid-kbd.json` — the same physical device as a `uhid` HID keyboard (boot-style
descriptor: 8 modifier bits including Left GUI `0x08`, 1 reserved byte, 6 keycode bytes). Send the
report **after** the device has been added (the README's warning), and again with an all-zero report
to release:

```json
{"id":1,"command":"register","name":"Omdroid Test HID Keyboard","vid":0x18d1,"pid":0x2c40,"bus":"usb",
 "descriptor":[0x05,0x01,0x09,0x06,0xA1,0x01,0x05,0x07,0x19,0xE0,0x29,0xE7,
               0x15,0x00,0x25,0x01,0x75,0x01,0x95,0x08,0x81,0x02,
               0x95,0x01,0x75,0x08,0x81,0x01,
               0x95,0x06,0x75,0x08,0x15,0x00,0x25,0x65,0x05,0x07,0x19,0x00,0x29,0x65,0x81,0x00,
               0xC0]}
{"id":1,"command":"delay","duration":800}
{"id":1,"command":"report","report":[0x08,0x00,0x1E,0x00,0x00,0x00,0x00,0x00]}
{"id":1,"command":"delay","duration":200}
{"id":1,"command":"report","report":[0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00]}
```

`0x1E` is HID keyboard usage "2"; `0x08` in the first report byte is Left GUI. If the guest receives
`2` but no workspace change, the modifier never reached Android — check `adb logcat -s LorieNative`
(`activity.c:343` logs every key it queues) before blaming Hyprland, and `getevent -l` to confirm the
kernel saw the Meta down at all (`cmds/hid/README.md` note 5).
