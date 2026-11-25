# R7 research: phone as a desktop (dock to a monitor = Omarchy, undock = Android)

Research only: nothing was built, no device was touched, no adb. Every claim cites a source
(file:line, an AOSP tag, or a URL with its date) or is marked **guess**.

Goal (Phil, verbatim in the brief): plug the phone into a monitor + keyboard + mouse and use
Omarchy with keyboard and mouse; unplug and Android is normal, with Omarchy still there.

**Verdict: feasible, and most of the hard parts already exist in this stack.** The X root already
follows whatever surface it is drawn on, Termux:X11 already reads per-display metrics and already
handles DeX input, and the guest's Mesa already knows the Adreno 840. What is missing is Android-side
dock detection, geometry computed from the *target* display instead of the phone's, launching the
display activity on that display, keyboard capture for Meta, and the live UI-mode switch.

**The one blocker to clear first:** Samsung ends the DeX/desktop session when the cable is pulled
("DeX will restart if you remove or unplug the HDMI cable", Samsung support ANS10001955), and our
manifest currently asks Samsung *not* to keep the process alive (`keep_process_alive=false`). Whether
the proot session survives an undock is the single biggest unknown, and it needs the phone.

---

## 1. External display on Android 16/17 for a third-party app

| Question | Answer | Source |
| --- | --- | --- |
| What does plugging in a monitor do? | Two modes: **mirror** the phone, or start a **desktop session on the external display**. The phone and the external display then "operate independently, and apps are specific to the display on which they're running" | Android Developers Blog, *Developer preview: Enhanced Android desktop experiences with connected displays* (2025-06); same blog *Android devices extend seamlessly to connected displays* (GA in **Android 16 QPR3**, posted 2026-03) |
| Is it in stable Android 17? | Yes: "Connected Displays: Now in stable as of Android 16 QPR3" and Android 17 keeps it; Sony ships "Desktop mode with an external display" on Xperia with Android 17 | developer.android.com blog *Adaptive development for the expanding Android ecosystem*; sony.co.uk support article 00409051 |
| Who chooses mirror vs desktop? | Android 17 asks on connect — "connect the screen as a secondary display or mirror the phone screen" — and remembers it per display; Samsung exposes the same choice as Settings → Connected devices → Samsung DeX → **Connected display → Extend / Screen mirroring** | corion.net, *Android Desktop mode (Android 17)* (2026-07-05, Pixel 9 Pro/GrapheneOS); Samsung support TSG10007466 |
| Is the external display a real display or a virtual one? | Journalists describe Android 16 desktop mode as "projects a virtual display to the external monitor, allowing your phone's main screen to operate independently" | androidauthority.com *Android 16's Desktop Mode transforms your Pixel phone into a PC* (2025-06-10) — **guess at the implementation level**; see the launch-permission rule below, which is why it matters |
| How does an app put an Activity on that display? | `ActivityOptions.setLaunchDisplayId(displayId)`. "An app can launch activities on **public displays or displays where the app already has activities**. Otherwise, trying to launch on a display for which `ActivityManager#isActivityStartAllowedOnDisplay` returns false (such as a private display or an invalid display id) will result in an exception." Also: "ignored on devices that don't have `FEATURE_ACTIVITIES_ON_SECONDARY_DISPLAYS`" | `frameworks/base/core/java/android/app/ActivityOptions.java` @ `android-17.0.0_r1`, lines 1682-1703 |
| Default placement | "By default, the activity launches on the same display as the caller"; a launch from a shell/Application context lands on "the top display on which the user last interacted" | source.android.com/docs/core/display/multi_display/activity-launch (last updated 2026-10-09) |
| Can a **running** activity be moved to another display and keep its process? | Documented: "If the target display is specified with `ActivityOptions#setTargetDisplayId()`, then the activity is moved to that display (if allowed by security and other restrictions)." **Caveat:** no `setTargetDisplayId` exists in `ActivityOptions.java` at `android-17.0.0_r1` — the doc describes trunk/newer (or a SystemApi); public code must not rely on it | source.android.com activity-launch (above); `ActivityOptions.java @ android-17.0.0_r1` (grep: no match) |
| What config changes fire on a move, and is the Activity recreated? | Display changes can fire **color mode, touchscreen availability and density** changes. Android's **display compatibility mode** "prevents an app from restarting when the app moves between different displays"; it is on by default **for games** (`android:appCategory`). To handle it yourself, declare those changes in `configChanges` (`colorMode|touchscreen|density|…`) and implement `onConfigurationChanged()` | developer.android.com/guide/practices/device-compatibility-mode, §Display compatibility mode |
| Does the system avoid restarts on its own? | Yes — the GA release "included compatibility treatments to scale windows and **avoid app restarts when switching displays**", and tells apps not to cache the `Display` object because it "can change when an app window is moved to an external display" | Android Developers Blog, GA post (2026-03) |
| Anything else that bites? | Android 17 (API 37) removes the opt-out from orientation/resizability restrictions on `sw > 600 dp`, so the app must be adaptive; and "custom launchers are not supported when extending desktop sessions across both displays. When a device is in Kiosk mode, Android Desktop is limited to mirroring" | developer.android.com blog *Adaptive development…*; androidenterprise.community *Android 17 brings…* |
| `Presentation` instead of an Activity? | Only useful for a *second window* on another display, and it obeys the same private/public rule. Not a route to a full-screen desktop | `ActivityOptions`/`Display` rules above |

**What this means for Omdroid.** Three routes, in order of robustness:

1. **System desktop session (no app work).** The user opens Omdroid from the monitor's taskbar/app
   drawer. The activity runs *on that display already* ("apps are specific to the display on which
   they're running"), so the X root is the monitor and everything downstream is the existing code.
   This always works and is the fallback if route 2 is refused.
2. **App-initiated launch.** `ActivityOptions.makeBasic().setLaunchDisplayId(id)` from
   `LauncherActivity.forwardToMainActivity()` (`app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt:339-359`).
   Succeeds only if the display is public or already hosts our activity — and whether the desktop
   session's display is public **must be read on the phone**: `Display.getFlags()` is public
   (`frameworks/base/core/java/android/view/Display.java` @ `android-17.0.0_r1:854`) and
   `FLAG_PRIVATE` is public (`:246`), so "public" is `(display.getFlags() & Display.FLAG_PRIVATE) == 0`
   — the convenience predicate is `hasAccess()`, which is `@TestApi` (`:2226-2237`).
   Wrap the launch in `try/catch (SecurityException)` and fall back to route 1.
3. **Mirroring mode.** No second display exists; nothing to do.

## 2. Samsung DeX (One UI 8+ on the Fold8 generation)

| Question | Answer | Source |
| --- | --- | --- |
| What *is* DeX now? | Since **One UI 8** Samsung replaced "classic" DeX with a version **built on Android 16's Desktop Mode**; Samsung and Google shipped the connected-display experience together | androidauthority.com *Samsung killed its classic DeX mode in One UI 8* (2025-07-24) |
| How does a normal app run in it? | Free-form, resizable, maximisable if it supports Android multi-window; otherwise "fixed-size window mode" and a "Some functions… may not be supported" notice | developer.samsung.com/samsung-dex/faq.html Q2/Q4/Q6; developer.samsung.com/samsung-dex/modify-optimizing.html |
| Full screen on launch | `<meta-data android:name="com.samsung.android.dex.launchwidth" android:value="0"/>` + `…launchheight` `0` ⇒ "the activity will be launched in full screen in Samsung DeX mode"; or `ActivityOptions.setLaunchBounds(new Rect(0,0,0,0))` | developer.samsung.com/samsung-dex/modify-optional.html |
| App requirements Samsung states | `android:resizeableActivity="true"`; do **not** declare `reqTouchScreen="finger"` / `android.hardware.touchscreen required=true` (it stops the app launching in desktop mode); handle 8 runtime changes (density xxxhdpi↔mdpi, resolution, orientation, screen layout, screen size, smallest width, **uiMode**, colour mode) | developer.samsung.com/samsung-dex/modify-optimizing.html |
| Survival across the mode switch | `com.samsung.android.multidisplay.keep_process_alive = true` (DeX ≥ 3.0) keeps the process alive when switching phone↔DeX; older: `com.samsung.android.keepalive.density`; plus the full `configChanges` list | same page |
| **What our build does** | `keep_process_alive` is **`false`** in the merged manifest — it was `true` when upstream added it in 2020 ("Prevent kill by Samsung Dex on plug/unplug", commit `a7037a3`) and was flipped to `false` in upstream `ee2224e` ("Big update. Replacing Xvfb and Xwayland with builtin X server"). `android.allow_multiple_resumed_activities=true` is also set | `termux-x11/app/src/main/AndroidManifest.xml:39-40`; `git log -L 36,41:app/src/main/AndroidManifest.xml` in the submodule |
| Meta/Super key | DeX consumes it for system shortcuts. An app can ask Samsung to capture it: `SemWindowManager.requestMetaKeyEvent(ComponentName, boolean)` by reflection — what `SamsungDexUtils` already does. From **Android 16.1 (API 36.1)** there is a proper API: `WindowManager.LayoutParams.setKeyboardCaptureEnabled(true)`, gated by `@RequiresPermission(permission.CAPTURE_KEYBOARD)` | `termux-x11/app/src/main/java/com/termux/x11/utils/SamsungDexUtils.java:15-43`; Moonlight's *Add support for Android 16.1 keyboard capture* (commit `ddb674a9b9`, 2026-09-01) for the two-branch pattern |
| Is `CAPTURE_KEYBOARD` grantable? | **Yes — `protectionLevel="normal"`**, behind the feature flag `com.android.hardware.input.request_key_capture_api`. A normal permission is granted at install from a `<uses-permission>` line, no adb and no accessibility service | `frameworks/base/core/res/AndroidManifest.xml` @ `android-17.0.0_r1:9715-9719` |
| What does keyboard capture actually do? | "Allows the currently focused window to capture keys before system processes system shortcuts and actions… certain system keys (Power keys, etc.) and shortcuts can be reserved"; without the permission it silently falls back to default handling — no exception | `frameworks/base/core/java/android/view/WindowManager.java` @ `android-17.0.0_r1:4754-4793` |
| Mouse input in DeX | A real pointer arrives as `SOURCE_MOUSE` (absolute) and the phone-side DeX touchpad as `SOURCE_MOUSE|SOURCE_TOUCHSCREEN` with `TOOL_TYPE_FINGER` | `termux-x11/.../input/TouchInputHandler.java:264-276, 301-304` (see §3) |
| Can DeX be turned off so the monitor is a plain second display? | One UI 8 **removed** "Auto start when HDMI is connected"; the replacement is Settings → Connected devices → Samsung DeX → **Connected display → Extend / Screen mirroring**. "Screen mirroring" duplicates the phone — it is **not** a plain second display. There is no supported "second display without a desktop session" on Samsung | androidauthority.com 2025-07-24; Samsung support TSG10007466; samsung.com support ANS10001955 |
| Detecting "docked" | `DisplayManager.getDisplays(DISPLAY_CATEGORY_PRESENTATION)` non-empty, or any display with id ≠ `DEFAULT_DISPLAY` and `(display.getFlags() & Display.FLAG_PRIVATE) == 0` (`Display.java:246,854`); `UiModeManager.getCurrentModeType() == UI_MODE_TYPE_DESK`; Samsung-only: hidden `Configuration.SEM_DESKTOP_MODE_ENABLED == semDesktopModeEnabled` (the snippet Samsung publishes, already implemented in `SamsungDexUtils.checkDeXEnabled`); broadcasts `android.app.action.ENTER_KNOX_DESKTOP_MODE` / `EXIT_KNOX_DESKTOP_MODE` with `android.app.extra.DISPLAY_TYPE` (`SemDesktopModeState.DISPLAY_TYPE_DUAL` 101, `…_STANDALONE`) | developer.samsung.com/samsung-dex/modify-optimizing.html; `SamsungDexUtils.java:45-54` |
| Keyboard/mouse presence | `InputManager.getInputDeviceIds()` → `InputDevice.getSources()` for `SOURCE_KEYBOARD` (alphabetic) / `SOURCE_MOUSE`, or `Configuration.keyboard`/`navigation`. Standard API; no citation needed beyond the header | — |

## 3. Termux:X11 and a second display

Read from the submodule at HEAD `77caf12` (branch `phoshdroid-integration`).

| Fact | Evidence |
| --- | --- |
| `MainActivity` declares `configChanges` for `screenSize`, `smallestScreenSize`, `screenLayout`, `density`, `orientation`, `uiMode`, … but **not `colorMode`**, and `resizeableActivity="true"` | `termux-x11/app/src/main/AndroidManifest.xml:23-26` |
| Omdroid's own manifest overrides the activity to `launchMode="singleTask"` (submodule says `singleInstance`) and keeps `exported=true` | `app/src/main/AndroidManifest.xml:52-57` |
| The X screen follows the Android surface: `surfaceChanged` → `getDimensionsFromSettings()` → `mCallback.changed(w, h, p.x, p.y)` → `handleHostSizeChanged`/`handleClientSizeChanged` + `LorieView.sendWindowChange(w, h, fps, name)` | `LorieView.java:560-572`, `MainActivity.java:225-238` |
| A destroyed surface sends `changed(0, 0, 0, 0)` → `sendWindowChange(0, 0, …)`, but the server **ignores** a zero size (`if (output && width && height …)`), so the X root survives an Activity recreate and keeps its size until the next real surface reports | `LorieView.java:574-578`, `activity.c:295-306`, `InitOutput.c:672-699` (guard at 687) |
| The X server is in the app process; the launcher starts it once behind a process-wide flag and only builds the intent if it is not running | `LauncherActivity.kt:764-775` (via `CmdEntryPoint`), `launch-contract.md` §5 |
| The view reports which display it is on: `"builtin"` when `Display.DEFAULT_DISPLAY`, `"dex"` when `SamsungDexUtils.checkDeXEnabled`, else `"external"` | `MainActivity.java:231-236` |
| Metrics are per-display, not per-device: `getRealMetrics()` uses `getLorieView().getDisplay().getRealMetrics(m)` | `MainActivity.java:919-923` |
| Secondary displays can already get their own SharedPreferences (`storeSecondaryDisplayPreferencesSeparately` + `getDefaultDisplay().getDisplayId() != DEFAULT_DISPLAY`) | `LoriePreferences.java:836-856` |
| Hardware mouse path exists: `TOOL_TYPE_MOUSE`/`SOURCE_MOUSE`/`SOURCE_MOUSE_RELATIVE` → `mHMListener`; `BUTTON_PRIMARY/TERTIARY/SECONDARY` → left/middle/right; wheel from `AXIS_VSCROLL`/`AXIS_HSCROLL`; `pointerCapture=true` → `requestPointerCapture()` (relative motion, Android pointer hidden) | `input/TouchInputHandler.java:155-157, 301-304, 340-345, 399-402` |
| What is actually **proven** on device: pointer motion (both `input mouse swipe` and a real HID mouse) moves the guest cursor. A left click, right click and wheel are **not proven** — no injection route carries a non-primary button, and a HID left click over the bar produced no workspace change | `docs/omarchy/r4-input-report.md:261-265, 279-282` |
| DeX input already special-cased: `isDexEvent()` (`SOURCE_MOUSE|SOURCE_TOUCHSCREEN`, `TOOL_TYPE_FINGER`) → touchpad strategy; captured DeX touchpad buttons mapped | `input/TouchInputHandler.java:264-276, 306-332` |
| **Not** there: any `DisplayManager` registration, any display-add/remove reaction, any use of `setLaunchDisplayId`, any display in `AndroidManifest` for the X activity beyond fullscreen prefs | grep over `app/src/main/java`: only `SamsungDexUtils`, `MainActivity.onConfigurationChanged`, `LoriePreferences` |
| **What assumes the default display:** nothing that hard-codes the primary display's *size*. The only default-display references are the pref-store selector (`getDefaultDisplay().getDisplayId()`, `LoriePreferences.java:852`) and the `"builtin"` display name (`MainActivity.java:231`); density, screen size and metrics all come from the view/activity's own display | `LorieView.java:616-652` (measured size), `MainActivity.java:703, 919-923` |

So the display half of §3 is already right — the X screen is the surface, and the surface follows
the display. The gap is above it, in our app.

**Two concrete defects for a dock flow:**

- `colorMode` is missing from `configChanges` (manifest line 25). A display move changes colour
  mode (`developer.android.com/…/device-compatibility-mode`, §Display compatibility mode), and
  without that entry the Activity restarts unless display compatibility mode rescues it. Our app
  declares no `android:appCategory`, so it is **not** a game for that default — add `colorMode`
  (and `touchscreen`, also named in that doc) rather than rely on it.
- On `surfaceDestroyed` the view reports a 0×0 screen size. The server ignores it, so the desktop is
  safe, but `handleHostSizeChanged(0,0)` runs `resetTransformation()` with a zero divisor
  (`TouchInputHandler.java:360-374`). Harmless once a real surface arrives, but noisy.

## 4. The GPU: does the guest's Mesa know the Adreno 840?

**Yes, at the revision the guest is built from.**

| Fact | Evidence |
| --- | --- |
| Guest Mesa = `lfdevs/mesa-for-android-container` @ `98f3d6229d61452cef80f8563af7c56ae599dc14` | `…/BlackFireAlex-omarchy-android-0f4cee8/manifest/components.lock`, line `mesa|git|…` |
| Shipped as Mesa **26.3.0-devel**, `libgallium-26.3.0-devel.so` 28,206,784 B, DRI dir + `freedreno_icd.json` under `/opt/omarchy-android/mesa/` | `docs/omarchy/payload-findings.md:99-107, 141` |
| The app points the guest at it: `MESA_LOADER_DRIVER_OVERRIDE=kgsl`, `LIBGL_DRIVERS_PATH`, `VK_ICD_FILENAMES` | `app/src/main/kotlin/com/phoshdroid/app/proot/ProotCommandBuilder.kt:128-158`; `rootfs/overlay/etc/phoshdroid/start.sh:39-48` |
| At that revision the device table has the 840: `GPUId(chip_id=0xffff44050A31, name="Adreno (TM) 840")` → `A6xxGPUInfo(CHIP.A8XX, [a7xx_base, a7xx_gen3, a8xx_base, a8xx_gen2, GPUProps(shading_rate_matches_vk=True)], num_ccu=6, num_slices=3, tile_align_w=96, …)` | `src/freedreno/common/freedreno_devices.py` @ `98f3d62`, fetched from the fork, line 1550 |
| The `0xffff…` high half is a fuse-id wildcard, so the kernel's own id `0x44050A31` matches without a `# KGSL` row (the table carries explicit KGSL rows for 830 `0x44050001` and 829) | `src/freedreno/common/freedreno_dev_info.c`, `dev_id_compare()`, cases (c)/(d) with `WILDCARD_FUSE_ID = 0x0000ffff00000000` |
| Upstream `main` carries **two** 840 ids — `0xffff44050A31` and `0xffff44050A21` — i.e. two bins/variants | `gitlab.freedesktop.org/mesa/mesa/-/raw/main/src/freedreno/common/freedreno_devices.py`, lines 1579 and 1600 |
| Same table already covers the tablet: `0x44050001` "Adreno (TM) 830" (KGSL) | fork file, line 1483 |

**What could still go wrong (all testable in one boot):** if the Fold8's kernel reports a chip id
outside those two rows, `fd_dev_info()` returns NULL and the `kgsl` Gallium driver does not load;
Mesa then has no hardware driver for KGSL and the session falls back to software (llvmpipe/pixman)
rather than failing outright — **guess** on the exact fallback. Probe: `cat
/sys/class/kgsl/kgsl-3d0/gpu_model` and the chip id, then a guest `eglinfo`/the project's own
`scripts/egl-probe.py`; the renderer string must say Adreno 840, not llvmpipe. The 840's
`a8xx_gen2` property list (6 CCU, 3 slices) also means the guest is not exercising the tablet's
2-slice/4-CCU path; a slice-count bug would show as corruption, not a refusal.

## 5. Omdroid changes needed

### (a) Dock: monitor + keyboard + mouse → Omarchy full screen on the monitor

| # | Change | Where |
| --- | --- | --- |
| a1 | **Dock detection.** A `DockMonitor` (new, or `DisplayShiftMonitor` grown) registering `DisplayManager.DisplayListener` + the existing `ActivityLifecycleCallbacks`, computing `externalDisplayId` from `getDisplays(DISPLAY_CATEGORY_PRESENTATION)` / any non-private display ≠ `DEFAULT_DISPLAY`, and `docked = external != null || UiModeManager.modeType == UI_MODE_TYPE_DESK` | new `app/src/main/kotlin/com/phoshdroid/app/DockMonitor.kt`; hook beside `DisplayShiftMonitor` in `PhoshdroidApp.kt:16` |
| a2 | **Write the UI mode before the session starts.** `~/.config/omdroid/ui` = `desktop` on dock, `mobile` on undock, written straight into the extracted guest (`<rootfs>/home/omarchy/.config/omdroid/ui`) before `start.sh` runs — `omdroid-ui.sh` reads it at session start and nothing else touches it | new write in `launch/SessionPrep.kt`; reader `rootfs/overlay/etc/phoshdroid/omdroid-ui.sh:37-46, 464-482`; call site `start.sh:72` |
| a3 | **Geometry and scale from the TARGET display, not the launcher's window.** `computeGeometry()` and `UiScale.resolve()` both read `windowManager.currentWindowMetrics` / `resources.displayMetrics` of the *launcher*, which is on the phone. Feed them `displayManager.getDisplay(id)` → `createDisplayContext(display).resources.displayMetrics` (density, real size) and the display's cutout insets | `LauncherActivity.computeGeometry()` (`LauncherActivity.kt:284-337`), `launch/DisplayGeometry.kt`, `launch/UiScale.kt` |
| a4 | **Launch the display activity on that display.** `ActivityOptions.makeBasic().setLaunchDisplayId(id)` on the `com.termux.x11.MainActivity` intent, in `try/catch (SecurityException)` with a fallback to today's plain `startActivity` | `LauncherActivity.forwardToMainActivity()` (`LauncherActivity.kt:339-359`) |
| a5 | **Full screen + keyboard capture.** Keep `fullscreen=true`; add `<uses-permission android:name="android.permission.CAPTURE_KEYBOARD"/>` and call `window.attributes.setKeyboardCaptureEnabled(true)` when docked (API 36.1+; on older Samsung fall back to `SamsungDexUtils.dexMetaKeyCapture(activity, true)`); Samsung full-screen launch meta-data `com.samsung.android.dex.launchwidth/launchheight = 0` | `app/src/main/AndroidManifest.xml`; a new call in `MainActivity.onCreate`/`onWindowFocusChanged` (submodule) or from the launcher |
| a6 | **Phone screen free.** Comes for free with the system desktop session (phone and external display are independent). If route 2 (app-initiated) is used instead, the phone keeps its own Android UI because the display activity is a second task on another display — `android.allow_multiple_resumed_activities=true` is already set | §1, §2 |
| a7 | **Input.** Mouse motion is proven, clicks are not (`r4-input-report.md:261-265`), so the first docked round must settle a real left click and the wheel before the flow is called working; Meta needs a5. The extra-key bar should be hidden in `desktop` dock mode (it is a phone affordance): write `showAdditionalKbd=false` | `LauncherActivity.computeGeometry()` reads those prefs; skill: launcher force-writes them |

### (b) Undock → Android normal, session alive, reopenable in `mobile` UI

| # | Change | Where |
| --- | --- | --- |
| b1 | **Survive the DeX teardown.** Set `com.samsung.android.multidisplay.keep_process_alive = true` (today `false`), and confirm the foreground service keeps the proot alive; if Samsung still kills it, the fallback is to restart the *session* deliberately on undock (the existing `RESTART_SESSION_ON_DISPLAY_SHIFT` path already does that safely) | `termux-x11/app/src/main/AndroidManifest.xml:39`; `DisplayShiftMonitor.checkAndMaybeRestart`, `LauncherActivity.RESTART_SESSION_ON_DISPLAY_SHIFT = false` (`LauncherActivity.kt:922`) |
| b2 | **Switch the UI mode back to `mobile`** the moment the external display disappears (a2), then let the guest's watcher do the live switch (c) | a1 + c |
| b3 | **Re-show the session on the phone.** The display activity is already on the built-in display after Android moves it back; the launcher's `LaunchDecision` forward path handles a re-tap. Unplug has to be treated like a size change, not like a session end — contract §3 already forbids restarting the session for a size change | `launch/LaunchDecision.kt`, `launch/LaunchReadiness.kt`, `launch-contract.md` §3 |
| b4 | **Do not lose the guest if the Activity dies.** The X server lives in the process (a process kill kills it); `keep_process_alive=true` plus the FGS is the only lever. Verified only on the phone (milestone 6) | §2, §3 |

### (c) Live UI-mode switch (today: read once at session start)

Today `start.sh` runs `omdroid-ui.sh` once (`start.sh:72`), then `omarchy-plugin-index.sh`
(`start.sh:78`), and the shell loads that index (`omdroid-ui.sh:1-14`). A live switch therefore
needs, in this order:

1. write `~/.config/omdroid/ui` (host or guest, one line);
2. re-run `omdroid-ui.sh` — it is idempotent and key-level (`theme_apply`, `shell_json_apply`,
   `looknfeel_apply`, `link_plugins`/`unlink_plugins`, `link_helpers`, `link_app_icons`);
3. rebuild the plugin index (`omarchy-plugin-index.sh`) because Quickshell reads the scan file, not
   a live directory scan (`start.sh:78`);
4. restart **only the shell** — `omarchy-restart-shell` is already the watcher's remedy and brings the
   layers back in ~2.4 s (`omarchy-watch.py:163-201`, rate-limited to 6/min and ≥2 s apart);
5. the Hyprland half (`looknfeel.lua` block) needs a config reload; **risk:** `hyprctl reload`
   re-applies the start-time output mode (project notes), so run it only with the monitor size
   unchanged, or let the watcher fix the size afterwards.

**No new IPC is needed for this.** `omarchy-watch.py` already polls every 0.25 s with a stable-size
rule and a rate-limited `act()`. Give it one more watched file (`~/.config/omdroid/ui`) and let it
run steps 2-4 itself; the app only writes the file. That keeps the switch inside the guest, where
the plugin index and the shell live, and it needs no socket (the root broker socket is a root-only
channel and should not be reused for this).

### Risks

- The desktop session's display may be **private** to SystemUI, in which case a4 throws and only a1's
  "user opens it on the monitor" route works. Read `display.getFlags() & Display.FLAG_PRIVATE` on the phone.
- Samsung's own teardown on unplug may kill the process regardless of `keep_process_alive`
  (`keep_process_alive` was originally for DeX dual mode, pre-Android-16 desktop mode).
- The monitor's density override (Settings → Connected devices → External display) decides `UiScale`;
  a 4K monitor at Android's default may resolve scale 2 and a 1920-logical-wide desktop, which the
  Omarchy shell's bar handles but looks large. The scale must come from the *display's* metrics (a3).
- `setLaunchDisplayId` is ignored entirely on a device without
  `FEATURE_ACTIVITIES_ON_SECONDARY_DISPLAYS` — a Samsung phone has it, the Xiaomi tablet may not.
- Two resumable activities (phone + monitor) also mean two `MainActivity` instances if anything
  launches the display activity twice; the X server is single-screen, so only **one** display
  activity may exist. Keep `singleTask` and pass the display id, never create a second instance.

## 6. Milestones

| # | Milestone | Proves | Acceptance test | Device |
| --- | --- | --- | --- | --- |
| **M1** | **Second display, app takes it (start here — no phone needed).** Enable Developer options → *Simulate secondary displays* → 1920×1080; then a real monitor over USB-C→HDMI | The X root follows the target display; `setLaunchDisplayId` is allowed; the desktop renders at the monitor's size without a session restart | `dumpsys display` lists the new id; logcat `Phoshdroid` shows `launch: display 2 1920x1080 dpi…`; `tools/probe.sh` prints `VERDICT: PASS` within 15 s of the hand-over; `hc.sh j/monitors` equals the display's size (not the tablet's); the session log has one resize line and no second `cage` start | **Xiaomi Pad 8 Pro** — it *does* output video: "supports DisplayPort Alt Mode 1.2" (mi.com FAQ KA-667493), USB 3.2 Gen 1 (mi.com specs) |
| M2 | **Dock detection + target-display geometry.** a1, a3 behind one pure function; dummy-display unit tests | The prediction equals the X root on the monitor (no resize at hand-over); dock/undock emit one log line each | logcat `dock: external=2 1920x1080 dpi=213 -> x=1920 y=1080 gap=0`; `fit-x11.log` stays 0 bytes (no second resize) | Tablet, then phone |
| M3 | **Live UI switch.** `desktop` while docked, `mobile` on undock, driven by the watcher watching the ui file | A mode switch with windows open: plugins and theme change, windows survive, session not restarted | `omdroid-ui.log` shows one `mode desktop`; `j/layers` has the stock layer set (desktop) / the omamobile ones (mobile); `probe.sh` PASS; session PID unchanged; an open `foot` still open | Tablet |
| M4 | **GPU on the phone.** Boot the session on the Fold8 and read the renderer | Adreno 840 is what Mesa binds (or the fallback is visible) | `cat /sys/class/kgsl/kgsl-3d0/gpu_model`; guest `egl-probe`/`VK_ICD` renderer string contains "840"; Hyprland has a monitor; first frame < the tablet's cold start | **Fold8** |
| M5 | **Dock on the phone.** Real monitor + keyboard + mouse, `desktop` UI, full screen | Phil's actual goal, minus undock: Meta reaches the guest, mouse clicks work, phone screen stays Android | `adb shell input` is not valid evidence; prove Meta with a guest key log (`foot /etc/phoshdroid/read-t.sh` + a real Meta+W) and mouse with a click that changes a workspace; `j/cursorpos` follows | Fold8 |
| M6 | **Undock.** Pull the cable with a session running | The session survives; Android is normal; reopening shows Omarchy in `mobile` | `ProotService.isRunning()` true, session PID identical, `omarchy-session.log` has no new `cage` line, ui file back to `mobile`, `probe.sh` PASS on the phone screen | Fold8 |

M1 can start today on the tablet and needs no phone build: the simulated display is enough to exercise
a3/a4 and the guest's follow-the-root behaviour, and the tablet does have DP Alt Mode for the real
half. **M4 is the first item that cannot be faked** — the GPU answer is already favourable in the
source (§4) but only the phone can confirm its chip id.

## Appendix: the host-side shape of a3/a4

```kotlin
// a3 — geometry from the display the desktop will actually be drawn on.
val dm = getSystemService(DisplayManager::class.java)
val target = dm.getDisplay(externalId) ?: dm.getDisplay(Display.DEFAULT_DISPLAY)
val dctx = createDisplayContext(target)                     // display-specific resources
val dm2  = dctx.resources.displayMetrics                    // density of THAT display
val b    = dctx.getSystemService(WindowManager::class.java).currentWindowMetrics.bounds
val geo  = DisplayGeometry.compute(                         // unchanged, better inputs
    windowWidth = b.width(), windowHeight = b.height(),
    density = dm2.density, extraKeyRows = rows,
    extraKeysShown = docked.not(), insetLeft = 0, /* cutout of the target display */)

// a4 — put the X surface there; fall back to today's behaviour on refusal.
val opts = ActivityOptions.makeBasic().setLaunchDisplayId(target.displayId).toBundle()
try { startActivity(waylandIntent, opts) } catch (e: SecurityException) { startActivity(waylandIntent) }
```

`docked.not()` is the phone affordance rule: the extra-key bar is a phone affordance and is hidden
when docked. The rest is the existing call — the point is that nothing downstream changes: the X root
is the surface, and the surface is on the monitor.

Flow, as it should look once a1-c exist:

```
dock    DisplayManager.added(id)   -> ui=desktop -> bootstrap (or forward) -> MainActivity on display id
                                     if a session is already up: write the ui file, guest watcher switches in place
undock  DisplayManager.removed(id) -> ui=mobile  -> guest watcher switches back; session and PIDs untouched
```

## 7. Marked as guess / unverified

- Whether the Android 16/17 desktop session's external display is a **public** display (app may
  launch onto it) or a SystemUI-owned **private** one (only route 1). Must be read on the phone.
- The exact behaviour when the Fold8's kernel reports a chip id outside the two 840 rows (I expect a
  software fallback, not a refusal).
- Whether Samsung honours `keep_process_alive=true` for the *new* desktop-mode DeX; the flag dates
  from DeX 3.0.
- Whether `setTargetDisplayId` (the documented "move a running activity") is public in any shipping
  API level; it is absent from `android-17.0.0_r1`.
- Xiaomi HyperOS's own desktop/mirror behaviour on the tablet; M1 only needs the display to appear
  and `setLaunchDisplayId` to be honoured.

## Sources

**Repo, read**
`AGENTS.md`; `README.md`; `docs/omarchy/launch-contract.md`; `docs/omarchy/r4-input-report.md`;
`docs/omarchy/payload-findings.md:99-107,141`;
`app/src/main/AndroidManifest.xml:1-70`; `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt:215-359, 764-775, 917`;
`app/src/main/kotlin/com/phoshdroid/app/DisplayShiftMonitor.kt`; `launch/DisplayGeometry.kt`; `launch/UiScale.kt`;
`app/src/main/kotlin/com/phoshdroid/app/proot/ProotCommandBuilder.kt:128-158`;
`rootfs/overlay/etc/phoshdroid/{start.sh,omdroid-ui.sh,omarchy-watch.py,fit-x11.py}`;
`termux-x11/` (HEAD `77caf12`): `AndroidManifest.xml`, `MainActivity.java`, `LorieView.java`,
`LoriePreferences.java:836-856`, `input/TouchInputHandler.java`, `utils/SamsungDexUtils.java`,
`cpp/lorie/{activity.c,cmdentrypoint.c,InitOutput.c}`, `git log -L 36,41:app/src/main/AndroidManifest.xml`.

**Mesa**
`lfdevs/mesa-for-android-container` @ `98f3d6229d61452cef80f8563af7c56ae599dc14`:
`src/freedreno/common/freedreno_devices.py:1481-1550`, `src/freedreno/common/freedreno_dev_info.c`;
upstream `mesa` `main`: same `freedreno_devices.py:1579,1600`.

**AOSP @ `android-17.0.0_r1`**
`core/java/android/app/ActivityOptions.java:1682-1703`; `core/java/android/view/WindowManager.java:4754-4793`;
`core/java/android/view/Display.java:246,314,2233`; `core/res/AndroidManifest.xml:9715-9719`.

**Web**
source.android.com/docs/core/display/multi_display/activity-launch (updated 2026-10-09);
developer.android.com/guide/practices/device-compatibility-mode; developer.android.com/blog/posts/android-devices-extend-seamlessly-to-connected-displays (GA, 16 QPR3);
android-developers.googleblog.com/2025/06/developer-preview-enhanced-android-desktop-experiences-connected-displays.html;
developer.android.com/blog/posts/adaptive-development-for-the-expanding-android-ecosystem;
androidauthority.com/trying-android-16-desktop-mode-on-pixel-3565393 (2025-06-10);
androidauthority.com/one-ui-8-classic-dex-3580755 (2025-07-24);
androidauthority.com/android-external-display-connection-dialog-3619980 (2025-11-26);
corion.net/blog/2026/07/05/android-desktop-mode-android-17;
sony.co.uk/electronics/support/articles/00409051;
androidenterprise.community (Android 17 enterprise, desktop/kiosk note);
developer.samsung.com/samsung-dex/{modify-optimizing,modify-optional,faq}.html;
samsung.com/us/support/troubleshoot/TSG10007466; samsung.com/us/support/answer/ANS10001955;
mi.com/global/support/faq/details/KA-667493 (Pad 8 Pro, DP Alt Mode 1.2);
moonlight-android commit `ddb674a9b9` (Android 16.1 keyboard capture), 2026-09-01.
