# R12: clipboard, browsers, Android controls, the key bar, the settings gear

Round 12 is five changes, each merged through its own pull request. None of them touches the guest
image, so the APK is the whole delivery.

| PR | change | merge |
| --- | --- | --- |
| #13 | the guest clipboard bridged to the X display Android talks to | `2e51439` |
| #14 | the Chromium family launches with the sandbox off | `98b5409` |
| #15 | Android's state and controls in the mobile quick settings (rebuild of #4) | `1e71b5b` |
| #17 | the extra-key bar hidden by default, summoned from a button | `b391a27` |
| #16 | the keyboard-settings gear no longer kills the desktop | `e2fecae` |

A path beginning `complete/` is under `rootfs/overlay/etc/phoshdroid/`, the directory the packager
installs and the APK re-syncs on a cold start.

## What changed

**Clipboard (#13).** `complete/omdroid-clipboard.py` mirrors two selections both ways: the X display's
`CLIPBOARD` and the Wayland one Android's paste targets. `session-start.sh` starts it, and its stop
path reads `/proc` rather than `pkill -f`, because a pattern naming the script also matches a wrapper
whose command line carries the hook's own text. Both halves must watch the same compositor — the
lesson that cost this round the most time; when one half watched cage and the other `wayland-1`, the
log said success while Hyprland's clipboard stayed empty.

**Browsers (#14).** `complete/bin/chromium-proot` dispatches on the name it was called by and links
only the names the image actually has, so a future Chromium-family install needs no code change. It
adds `--no-sandbox --disable-dev-shm-usage --password-store=basic`. Both sandbox helpers on the image
fail Chromium's check (one is `4755` but owned by `omarchy`, the other is `rwx------`), and neither
unprivileged user namespaces nor a setuid root helper can exist inside proot; the same trade Omarchy
makes. Brave opens a window (158.1.100.59, read on the tablet with `brave --version`). For Chromium the
link was checked with `chromium --version` (151.0.7922.137) rather than by opening a page; the two
binaries share the launcher, but only Brave was driven to a window.

**Android controls (#15).** The host publishes `state.json` (schema 2: a timestamp, a per-field
`observed` map, then the values), and the shell reads it: event-driven on the app side (receivers, a
`NetworkCallback`, `ContentObserver`s, a `FileObserver` on the request mailbox), about 7.5 writes a
minute idle instead of 30, and a field the guest has not seen confirmed for 10 s reads as unknown
rather than stale-false. The quick settings tiles render three states, and the Wi-Fi tile opens
Android's own settings page on the display the shell is on. Rustiqly's original work is carried in
this branch as `859f848`.

**Key bar (#17).** The bar under the desktop was a permanent affordance and is now a summoned one: it
starts hidden in every session, and a 36 dp translucent button in the bottom-right corner toggles it.
The bar is an overlay — a sibling of the X surface — so a toggle costs no X-root change and no guest
restart. The button lifts above the bar while the bar is shown and hides in picture-in-picture.
`DockMonitor` no longer flips Termux:X11's preferences, and `DisplayGeometry` no longer reserves the
bar's height, so the predicted root is the full window.

**The gear (#16).** Tapping the bar's settings key launched `LoriePreferences`, which Omdroid disables
in its manifest: the `ActivityNotFoundException` took the process and the desktop with it. The
activity is enabled and kept internal (`exported=false`, no intent filter), and our `preferences.xml`
was renamed to `omdroid_preferences.xml` so it stops shadowing the library's, whose `main` screen that
activity needs.

## Verified on the tablet

What was measured, and how. The tablet is a Xiaomi Pad 8 Pro; no serial appears in this document.
Three of the five changes were driven from an APK of their own branch (#13, #15, #17). The browser
launcher was driven by running the session hook by hand, because no APK carrying it had been built
at that point. The gear was tapped on the 0.0.21 candidate once that existed.

| change | what was seen |
| --- | --- |
| clipboard | both directions in one session with the bridge started by the hook, `owner=0x600001 text=…` and `wl-paste` returning the guest's string |
| browsers | a bare `brave` opens a real window, 8-10 processes after 45 s, and `chromium --version` reports 151.0.7922.137 |
| Android controls | the sheet reads Wi-Fi "Connected", Bluetooth "On", 95 %, "Autorotate", matching `dumpsys`; tapping the Wi-Fi tile raised Android's own Wi-Fi settings page; `state.json` carries schema 2 with per-field stamps |
| key bar | bar absent at start and the desktop full height; the button at `[3112,2048][3191,2127]`; one tap puts the bar at `[0,1971][3200,2136]` and lifts the button to `[3112,1883][3191,1962]`; a second tap hides it |
| the gear | tapped on the 0.0.21 candidate: Termux:X11's Preferences opens with the app's process id unchanged; before the fix the same tap terminated the process |
| the candidate | the 0.0.21 build (`versionCode 21`, `sha256 c49d0c36…`, every change above) installed and cold-started on the tablet: the desktop came up with the dock, the pill put the bar at `[0,1971][3200,2136]`, the gear opened Preferences with the app's process id unchanged, BACK returned, the pill hid the bar again, and the dock was there underneath |

**One correction worth recording.** After the preferences excursion the bottom of the desktop looked
empty and I read it as the shell having lost its dock. It had not: the summoned key bar is a
full-width overlay on the bottom strip, and while it is open it covers the dock. Hide the bar and the
dock is there. Reloading the page of assumptions that produced the false alarm also showed that
Hyprland's control socket is never missing — proot rebinds it under a translated name, so `ls` and a
second proot's `hyprctl` cannot see it while it answers. What the alarm did expose was a real blind
spot in the watcher, which now also judges the mobile bottom layer (`omamobile-dock` /
`omamobile-home-strip`); see `docs/omarchy/launch-contract.md` §2.

## Gates

On this release's tree (`647fa4e` plus this commit): `:app:testDebugUnitTest` 238 tests,
0 failures, 1 skipped; `:app:lintDebug` 0 errors, 37 pre-existing warnings; `:app:assembleDebug`
builds the APK with the submodule in it (1,124,879,400 B, `sha256 c49d0c36…`).

## Not verified

- The docked case for the Android bridge and for the key bar's button: no external monitor was
  available, and both were exercised undocked only.
- Picture-in-picture behaviour of the summon button.
- A human copy on Android by hand: the clipboard is proven with `wl-copy`/`wl-paste` and
  `xclip`-style helpers, not with a long press in an app. Images and INCR transfers are capped.
- Cold-starting an APK that carries the browser launcher: at the time it was tested, the fix was
  driven by running the session hook by hand.
- The depth-cap test in `AndroidControlRequests` provokes the cap rather than reproducing a real
  `StackOverflowError`.
- The key bar is an overlay: while it is open it covers the dock's strip, by design and visible to the
  user; there is no auto-hide.
