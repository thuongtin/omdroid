# Brief R5-MOBILE-UI: Omamobile's phone shell pieces in Omdroid (code phase, no device)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. You have NO device in this run (another agent owns the tablet).

Repo: `<repo>` (branch `main`, read `AGENTS.md`).
Read first, whole: `docs/omarchy/r5-omamobile-research.md` (what to port, why, file:line).
Omamobile clone: `<scratch>/omarchy/r5/research/omamobile` (re-clone shallow from
`https://github.com/derekross/omamobile` if it is gone; record the commit sha you port from).
Guest files (read-only): `<scratch>/omarchy/upstream/` (`usr/share/omarchy/` =
Omarchy incl. `shell/`, `home/omarchy/.config/` = the user config the guest starts with).
Report, created in your FIRST calls and updated after every step:
`docs/omarchy/r5-mobile-ui-report.md` (STATUS TABLE rows U1-U6, `PENDING` until proven).
Scratch: `<scratch>/omarchy/r5/mobile-ui/`.

## Goal

Phil asked for a more mobile-friendly UI using Omamobile, and said the blockers can be worked
around. This round builds the guest side, ready to test on the tablet next round:
1. a touch-sized theme pass (research §5a: bigger bar and type, no gaps);
2. Omamobile's five pointer-clean plugins (`omamobile.bar`, `omamobile.quicksettings`,
   `omamobile.launcher`, `omamobile.back`, `omamobile.switcher`, research §5b) with what they need
   to load and run in Omdroid's guest (helper scripts, a `uwsm-app` shim if needed, stubs for
   services proot does not have, so a tile shows "unavailable" instead of breaking);
3. a switch between this "mobile" UI and the stock desktop.
Real touch is being built by a sibling (an aquamarine `wl_touch` patch). Until it lands, taps
arrive as mouse clicks; the five plugins work with that (research §4). Write nothing that only
works with one of the two; prefer Qt pointer handlers that accept all devices.

## Decisions taken by the parent

- **Vendored, not packaged.** The plugin trees go into the repo under
  `rootfs/overlay/etc/phoshdroid/omamobile/` with Omamobile's `LICENSE` (MIT) and a `SOURCE.md`
  naming the upstream repository, the commit sha and every local change. Change upstream files as
  little as possible; put Omdroid-specific code in separate files.
- **Never clobber the user's config.** Anything written into `/home/omarchy/.config` must be
  installed only when absent or when it still equals a version we wrote (keep a marker with a
  hash), never over a file the user has edited. Say how each file is handled.
- **The switch.** `~/.config/omdroid/ui` containing `mobile` or `desktop`; missing = `mobile`.
  `start.sh` reads it each session. `desktop` must give exactly today's session (stock bar,
  stock theme sizes), so it is the escape hatch if the mobile UI breaks.
- **The plugin index decides what loads.** Plugins are linked or copied into the place the
  shell's plugin index reads (research §3) BEFORE `omarchy-plugin-index.sh` runs in `start.sh`;
  extend that script only if it cannot see them as they are.

## Steps

### U1. Mechanism, written down before code
From the research and the guest files: the exact guest paths for the plugin trees, how the
shell selects the bar implementation and its plugin list (`shell.json` or what the guest's
version uses), the theme override files for bar size and font size (`shell.bar.toml`,
`shell.font.toml`) and where a user theme override lives, the Hyprland `looknfeel` values. One
table in the report: what goes where, written when, and how `desktop` undoes it.

### U2. Vendor and adapt the five plugins
Copy them in, plus the helper scripts they call. For each plugin list every external thing it
uses (QML imports, `qs.*` modules, `Quickshell.*` types, IPC calls, processes it runs, services)
and whether the guest provides it: cite the guest file that provides it, or the stub you added.
Check every QML import against the guest's shell tree (`usr/share/omarchy/shell/`) and the
Quickshell 0.3.1 modules; a mismatch is fixed in an Omdroid-side file or the plugin is dropped
from the round with the reason. Services that need systemd, BlueZ, ModemManager, NetworkManager,
sensors or a battery: stub them to "unavailable" in the UI, and list which tiles are stubs.

### U3. Session wiring
`start.sh` (quoting rules in `AGENTS.md`: no apostrophes in comments; `bash -n` after each edit):
read the switch, then for `mobile` install the theme overrides, the Hyprland looknfeel override
and the plugin selection (all under the no-clobber rule), link the plugins, then run the plugin
index as today. For `desktop`, remove only what we installed (by marker) so the stock session
returns. Put the logic in a new overlay script (e.g. `omdroid-ui.sh`) that `start.sh` calls in one
line, so `start.sh` stays short.

### U4. Packaging
Add the new overlay files to the packager's "Applying overlay" block in
`rootfs/package-omarchy-rootfs.sh` AND to `syncGuestOverlay` in `app/build.gradle.kts` (they must
list the same files, `AGENTS.md`). Gate:
`./gradlew :app:mergeDebugAssets :app:test --console=plain` (foreground, 600 s timeout), then
`find app/build -path '*guest-overlay*omamobile*' -type f | wc -l` equals the number of files you
vendored plus your own, and `python3 docs/omarchy/tools/unit-count.py`. Do NOT run `assembleDebug`
and do not touch `app/build/outputs/apk/`.

### U5. Dry run without the device
Run the session wiring against a scratch copy of the guest's home and `/etc/phoshdroid` (extract
the needed members of `app/src/main/assets/rootfs.bin` with `tar -xzf ... <members>` into scratch;
point the script at it with variables, e.g. `OMDROID_ROOT`) for: first start (`mobile`), second
start (nothing rewritten), a user-edited file (left alone), switch to `desktop` (our files removed,
user files kept), back to `mobile`. Then run `omarchy-plugin-index.sh` against that tree and show
the index lists the five plugins. Paste the outputs.

### U6. Report
STATUS TABLE plus: "What Phil will see" (bar, pull-down, launcher, back, switcher, at the
tablet's 1600x985 logical size), "Stubs" (each unavailable tile and why), "The switch",
"Files", "What the device phase must check" (exact steps and the evidence for each), and
"Not verified".

## Hard rules

- No adb, no device tool, no `./install.sh`, no `assembleDebug`. You own
  `rootfs/overlay/etc/phoshdroid/**`, `rootfs/package-omarchy-rootfs.sh`, the `syncGuestOverlay`
  task in `app/build.gradle.kts`, `docs/omarchy/r5-mobile-ui-report.md`. Touch nothing else
  (`app/src/**`, `termux-x11/**`, `rootfs/patches/**`, `rootfs/build-aquamarine.sh` belong to
  others). Never edit `app/src/main/assets/rootfs.bin`.
- No git command that changes anything; the parent commits.
- Never `pkill -f`. No `sleep N; tail` calls.
- If a command is blocked waiting for approval, do not retry or rephrase it; note it, go on.

Final reply, at most 10 lines: U1-U6 with their decisive facts, the plugins that made it and the
ones dropped (why), the stubbed tiles, the switch, files changed.
