# Brief R4-INPUT-RESEARCH: pass a hardware keyboard and mouse through to Omarchy (read-only)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. You have NO device: no adb, no gradle, no git commands that change
anything. You write exactly one file: `docs/omarchy/r4-input-research.md` (repo
`<repo>`, read `AGENTS.md`). Scratch:
`<scratch>/omarchy/r4/research-input/`.

## Goal

Phil wants the keyboard and mouse attached to the Android tablet to work in the Omarchy desktop
as they would on a Linux PC. His tablet (Xiaomi Pad 8 Pro, Android 16, HyperOS 3.0) has a Xiaomi
keyboard cover with a touchpad; Android lists `Xiaomi Focus Pen Pro Keyboard`,
`Xiaomi Focus Pen Pro Mouse` (sources `MOUSE | TOUCHPAD`), `Xiaomi Keyboard` and `Xiaomi Mouse`.
Omarchy is driven by the keyboard: SUPER (the Meta/Windows key) is its main modifier
(SUPER+Return terminal, SUPER+Space launcher, SUPER+1..9 workspaces, SUPER+W close), plus
Alt/Ctrl/Shift combinations and the F-keys. Your job is a change plan a later agent can
implement and test; nothing is implemented in this round.

What "works" means, to be checked item by item in your plan:
1. Every key reaches Hyprland with the right keysym, including SUPER alone and SUPER+key,
   Alt+Tab, Ctrl+Space, Esc, Tab, the arrows, F1-F12, and the layout (US first; say how other
   layouts would be chosen).
2. Android does not ALSO act on those keys while the desktop is on top (no app drawer or taskbar
   on Meta, no recents on Alt+Tab or Meta+Tab, no back on Esc), and there is a way to get back
   to Android (say which key or gesture).
3. The touchpad and a mouse move Hyprland's cursor; left, right and middle buttons and
   two-finger scroll work; there is one cursor on screen, not Android's arrow on top of
   Hyprland's.
4. Optionally pointer capture (relative motion, no Android cursor) with a documented way out.

## What to read (local, then upstream)

- Termux:X11 in the submodule `termux-x11/` (it runs in the app process): `MainActivity.java`
  (key and generic motion handling), `LorieView.java`, `input/**`, `utils/KeyInterceptor*`
  (an accessibility service; its label in the built APK is "Termux:X11 KeyInterceptor"),
  `res/xml/accessibility_service_config.xml`, `Prefs`/`LoriePreferences.java` and the
  preference XML for every input key: `preferScancodes`, `enforceCharBasedInput`,
  `hardwareKbdScancodesWorkaround`, `dexMetaKeyCapture`, `enableAccessibilityServiceAutomatically`,
  `pauseKeyInterceptingWithEsc`, `filterOutWinkey`, `pointerCapture`,
  `transformCapturedPointer`, `showIMEWhileExternalConnected`, and any other you find. For each
  key: default value, what it changes, file:line.
- What the app sets today: the `getDefaultSharedPreferences(this).edit()` block in
  `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt` (it sets `touchMode`, the extra-key
  bar, `fullscreen`, `hideCutout`, `adjustHeightForEK`; none of the keys above). The merged
  manifest is `app/src/main/AndroidManifest.xml` plus the submodule's.
- How an accessibility service of a SIDELOADED app is enabled on Android 13+ (the "restricted
  setting" step), and whether `adb shell settings put secure enabled_accessibility_services ...`
  works; the exact component name in this APK. Android's own documentation, pinned.
- What Android 16 intercepts before an app sees it (Meta, Meta+Tab, Alt+Tab, Esc as back, the
  pointer icon over apps) and the app-side APIs that opt out or capture
  (`View.requestPointerCapture`, `PointerIcon.TYPE_NULL`, `onKeyDown` vs accessibility
  `onKeyEvent`, `Activity.requestShowKeyboardShortcuts`, HyperOS specifics if documented).
- Guest side: how a key and a pointer event travel Xlorie -> cage (wlroots 0.20 x11 backend:
  where its keymap comes from) -> Hyprland (nested; `input:kb_layout` in Omarchy's
  `<scratch>/omarchy/upstream/usr/share/omarchy/default/hypr/input.lua` and the user
  config under `.../upstream/home/omarchy/.config/hypr/`), and whether the nested Hyprland draws
  its own cursor. The upstream payload's own keyboard option is described in
  `<scratch>/omarchy/upstream/BlackFireAlex-omarchy-android-0f4cee8/docs/options.md`.
- Earlier findings in this repo: `docs/omarchy/device-bringup-report.md` (round 1 keyboard test),
  `docs/omarchy/ARCHITECTURE.md`.

## How it will be tested (put this in the plan)

Find out from AOSP documentation or source, not a device: which of these a script can use
over adb as uid shell on Android 16, and what each proves:
- `input keyboard keyevent ...`, `input mouse tap|swipe|scroll`, `input touchpad ...`;
- the `uinput` and `hid` shell commands (JSON-described virtual devices used by CTS), so a
  virtual keyboard with a Meta key and a virtual mouse can be registered;
- whether events injected by `input` pass through an accessibility key filter and through
  Android's own Meta interception, so a test does not prove something injection bypasses.
Then a short manual checklist for Phil with the real keyboard cover (each step: what to press,
what must happen).

## Deliverable

`docs/omarchy/r4-input-research.md`, with:
- **Today**: what happens now for each of goals 1-4, as far as source can tell (file:line).
- **Change plan**, ranked: exact preference values to set in the launcher block, code changes
  (file, function, what), the accessibility-service enabling flow, the user-visible label for the
  service (it should say Omdroid), and anything needed in the guest. For each: the goal it serves
  and its cost or risk.
- **Test plan**: the adb-driven tests (commands, expected guest-side evidence such as
  `hyprctl -j devices`, `hyprctl -j cursorpos`, a workspace switch from SUPER+2) and Phil's manual
  checklist.
- **Unknowns** that only a device can answer.

Rules: every claim cites what you read (file:line, or a URL pinned to a version); anything else is
marked as a guess. Do not edit any other file.

Final reply, at most 8 lines: the three most important changes, how SUPER will reach Hyprland,
how the tests will run, and the file path.
