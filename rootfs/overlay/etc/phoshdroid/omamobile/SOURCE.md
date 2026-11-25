# Omamobile plugins vendored into Omdroid

Upstream: https://github.com/derekross/omamobile
Commit ported: `b5baaea7a96733a587b53e8669fde4301769fd5f` (shallow clone, 2026-11-24)
Licence: MIT (`LICENSE` in this directory is upstream's, unchanged).

## What was copied

From `packages/omamobile-shell/`:

- `plugins/omamobile.bar/` — phone status bar (bar kind)
- `plugins/omamobile.quicksettings/` — pull-down quick settings sheet (panel, keepLoaded)
- `plugins/omamobile.launcher/` — dock, home pill and app drawer (panel, keepLoaded)
- `plugins/omamobile.back/` — edge-swipe back gesture (panel, keepLoaded)
- `plugins/omamobile.switcher/` — recent apps as cards (panel, keepLoaded)
- `bin/omamobile-launch` — launches an app, a command or a URL on a new workspace
- `bin/omamobile-home` — the back gesture's "go home"

Not copied: `omamobile.home`, `omamobile.keyboard`, `omamobile.fingerprint`,
`omamobile.call`, `omamobile.mobilenetwork`, `omamobile.voice`, `omamobile.access`,
`omamobile.update`, `omamobile-settings`, `omamobile-owl-widgets`, `omamobile-apps`,
the squeekboard layouts, the OMARCHY patch series and the systemd units. Each one
stands on hardware, systemd or a service proot does not have (see the R5 research,
`docs/omarchy/r5-omamobile-research.md` section 1).

## Local changes

**Upstream files are byte-identical to the commit above, except the ones listed under
"Changed upstream files".** Everything else Omdroid needed was added beside them:

| Added file | Why |
|---|---|
| `bin/omamobile-browser-setup` | stub; upstream fits a phone browser's window, there is no browser profile to fit here. Runs at every bar load, must not fail. |
| `bin/omamobile-cell-watch` | stub; no modem and no ModemManager inside proot. Prints nothing, so the bar shows no carrier icon instead of a restarting process that errors. |
| `bin/omamobile-call-watch` | stub; no `omatel-agent` and no systemd user units. Same reason. |
| `SOURCE.md` | this file |

### Changed upstream files

One line per upstream file Omdroid edits, with the device evidence that forced it
(`docs/omarchy/r5-mobile-ui-device-report.md`).

| File | Change | Why |
|---|---|---|
| `plugins/omamobile.switcher/Switcher.qml` | A card's `ScreencopyView` sits in a `Loader` and is created only when `OMARCHY_PROOT` is not `1`; under proot the card shows the app's icon and the window's title instead (`liveCopies`, `iconFor`). | Hyprland under proot offers `zwp_linux_dmabuf_v1` at version 3. Creating a `ScreencopyView` (one per open window, even with the switcher closed) makes Quickshell send `get_default_feedback`, a version 4 request: `wl_display` error, "Wayland connection experienced a fatal error", and the whole shell exits the moment any app opens. |

Two upstream frictions were resolved without touching upstream code:

- `omamobile-launch` starts apps through `uwsm-app`. The guest image already ships
  `/usr/local/bin/uwsm-app`, which drops the `--` and execs the rest when
  `OMARCHY_PROOT=1` (it is Omarchy-Android's own shim), so the app path works
  unchanged. No shim was added.
- `omamobile-launch` is `#!/usr/bin/python3`; the image has python3.

## How they reach the guest

`rootfs/overlay/etc/phoshdroid/omamobile/` is copied into the image by
`rootfs/package-omarchy-rootfs.sh` and into an existing install by the APK's
`syncGuestOverlay` task (both list it). At session start `omdroid-ui.sh` symlinks
the five plugin directories into `~/.config/omarchy/plugins/` and symlinks the
`bin/` scripts into `/usr/local/bin/`, then `omarchy-plugin-index.sh` builds the
plugin index the shell reads under proot.
