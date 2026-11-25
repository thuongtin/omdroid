# Brief R5-README: README and AGENTS.md for touch, keyboard and the mobile UI (text only)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. No device, no gradle, no git commands that change anything, no push.
Repo: `<repo>` (branch `main`). You edit exactly two files:
`README.md` and `AGENTS.md`. Write a claims map (claim -> source file:line) to
`<scratch>/omarchy/r5/readme/claims.md`.

## What changed since the README was written (read the sources, do not trust this summary)

Sources, read them whole: `docs/omarchy/r4-touch-report.md`, `docs/omarchy/r4-input-report.md`,
`docs/omarchy/r5-omamobile-research.md` (sections 0, 5), `docs/omarchy/r5-mobile-ui-report.md`,
`docs/omarchy/r5-mobile-ui-device-report.md` (both rounds), `docs/omarchy/r5-touch-patch-report.md`,
`docs/omarchy/r5-touch-device-report.md`, `rootfs/overlay/etc/phoshdroid/omamobile/SOURCE.md`,
`rootfs/overlay/etc/phoshdroid/lib/README.md`, and `git log --oneline v0.0.14-alpha..HEAD`.

1. **Touch.** Taps did nothing (aquamarine's Wayland backend had no touch device). Omdroid now
   ships a patched aquamarine (`rootfs/patches/aquamarine/0002-*`, built by
   `rootfs/build-aquamarine.sh`, delivered in the APK at `/etc/phoshdroid/lib`) and runs
   Termux:X11 in direct touch: taps within 1 px, the bar 9/9, quick swipes, two touch points.
2. **Keyboard pass-through.** A hardware keyboard's SUPER, Alt+Tab, Esc reach Omarchy through
   Termux:X11's key-interceptor accessibility service, which the app enables itself; `install.sh`
   grants `WRITE_SECURE_SETTINGS`. Every key is sent as a scancode.
3. **Mobile UI.** Five plugins vendored from Omamobile (MIT, commit in `SOURCE.md`): phone bar,
   quick settings, launcher/dock, back gesture, app switcher; 44 px bar, 16 px type, no gaps, the
   screensaver off, the pointer hidden after a touch. `~/.config/omdroid/ui` = `mobile` (default)
   or `desktop` (the stock Omarchy session), read at each session start.
4. **Install.** `install.sh` tries `pm install` from `/data/local/tmp` first (works on HyperOS).
5. Screenshots: `docs/screenshots/mobile-desktop.jpg`, `docs/screenshots/mobile-quicksettings.jpg`
   (new), next to the existing ones.

## What to write

- README: the Status table gains the new proven rows (each with its number and report link); a
  short "Mobile UI" section (what it is, the switch, credit to Omamobile with the link and licence,
  which plugins and why only those) with the two new screenshots; "How it works" gains the touch
  path (one paragraph) and the keyboard path (one paragraph); the tools table gains any new tools
  in `docs/omarchy/tools/` (one line each); "Not verified yet" gets: real fingers (all touch so far
  was injected), the real keyboard cover (synthetic keyboards only), pinch and three-finger
  gestures, the fresh-image path for the patched library (no repack this round), the idle lock
  that fires but does not lock, install over an existing Phoshdroid. Credits: Omamobile (MIT),
  aquamarine (BSD-3-Clause, patched). Keep the "Highly experimental" box. Keep it honest: a claim
  without a PASS row in a report goes under "Not verified yet".
- AGENTS.md: the Layout section names the new pieces (`rootfs/patches/aquamarine/`,
  `rootfs/build-aquamarine.sh`, `rootfs/overlay/etc/phoshdroid/{lib/,omamobile/,omdroid-ui.sh}`,
  `launch/KeyCapture.kt`), and Pitfalls gains: a cold start re-syncs every guest overlay file from
  the APK (a fix pushed by hand is reverted until the APK carries it); Quickshell `ScreencopyView`
  kills the shell under proot (dmabuf v3); the `syncGuestOverlay` list, the packager block and
  the overlay must still name the same files (now including `lib/`, `omamobile/`, `omdroid-ui.sh`).
  Keep AGENTS.md compact (it is read by every agent).

Rules: no device serial, no `/home/` paths, no email addresses in either file
(`grep -nE '<tablet serial>|/home/|@' README.md AGENTS.md` must print nothing except existing
`git clone`/URL lines you did not add). Every `docs/...` path you write must exist
(`ls` them). Do not invent numbers.

Final reply, at most 6 lines: line counts of both files, the sections changed, the grep result,
and anything you left out for lack of proof.
