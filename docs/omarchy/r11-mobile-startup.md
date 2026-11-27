# R11 S2 — the mobile UI starts about as fast as the desktop UI

Branch `r11/mobile-startup`, worktree `<repo>` (stream S2 of the R11 round), base `90d7494`.
Answers the owner's "mobile UI slow start" item from the R10 report: mobile hand-over
10.7-11.2 s against desktop 3.0-3.5 s on the same build.

**Result in one line:** the mobile shell was waiting ~7 s at every start for
`omamobile.quicksettings`' tile-state pass (nine serial `timeout 3` backend probes), which ran
from `Component.onCompleted`; the pass is now parallel, cached, and off the start-up path, and
the three idle restart loops the same instrument found are closed.

## STATUS

| # | Step | State | Proof |
| --- | --- | --- | --- |
| 1 | Timeline instrument (evlog + process sampler), shell restart vs cold start | PASS | phase 1: two mobile cold starts and one desktop cold start on the R10 build (`p1/`), evlog + procs; `tile-state.sh` 7.13 s / 6.60 s in both mobile arms, absent in the desktop arm |
| 2 | Bisect: one omamobile plugin at a time out of the shell's plugin list | PENDING | phase 2 arm C (quicksettings dropped) |
| 3 | Fix the cause, behind a switch, SOURCE.md updated | PASS (host) | commit `3ae27b9`; `qmlformat` rc=0 on the three QML files, `sh -n` on tile-state.sh; SOURCE.md rows |
| 4 | Prove on an APK: 3 mobile + 3 desktop cold starts, alternating, target mobile within 1.5 s of desktop; gestures still pass | PENDING | phase 3 (APK) and phase 4 (gestures) |
| 5 | Steady state: CPU of every omamobile helper at idle over 60 s | PENDING | phase 2 arm D (60 s birth count) + phase 4 (CPU) |

## What changed

- `rootfs/overlay/etc/phoshdroid/omamobile/plugins/omamobile.quicksettings/tile-state.sh` — the
  nine probes now run at once into per-probe files, printed in a fixed order afterwards, and the
  combined output is written to `~/.cache/omamobile/tile-state` (`OMAMOBILE_TILE_STATE_CACHE`
  overrides). Same commands, same `timeout 3` bound each; only serial became parallel.
- `…/omamobile.quicksettings/QuickSettings.qml:378-400` — the probe no longer runs from
  `Component.onCompleted`. A `FileView` reads the cache at load (a file read, no process) and a
  `Timer` runs the pass 8 s after load. `OMDROID_QS_PROBE_AT_LOAD=1` restores probe-at-load.
  Opening the sheet still re-probes through `runOpenRefresh` (`:99-120`), unchanged.
- `…/omamobile.bar/Bar.qml:95-145` — the cell and call watchers run only while the plugin they
  stream for is vendored (`omamobile.mobilenetwork`, `omamobile.call`), and their 5 s restart is
  gated the same way. Both are Omdroid stubs that exit at once, so upstream's restart-on-exit
  forked a dying process every 5 s for the whole session.
- `…/omamobile.launcher/Launcher.qml:515-548` — `omamobile-osk-watch` (a binary of the unported
  `omamobile.keyboard` plugin) and its 3 s restart run only while that plugin is vendored. It
  could not exec at all, so the timer relaunched a failing exec every 3 s.
- `…/omamobile/SOURCE.md` — one row per changed upstream file, with the measurement that forced it.

## Host proof

- `qmlformat` (host, `/usr/lib/qt6/bin/qmlformat`) rc=0 on `QuickSettings.qml`, `Bar.qml`,
  `Launcher.qml`; `sh -n` clean on `tile-state.sh`.
- The leak gate (build-machine home paths, scratch paths, the device serial, the model number)
  printed nothing before commit `3ae27b9`; this report uses `<repo>`, `<scratch>` and
  `<adb serial>`.

## Device proof (R10 build `0.0.18`, sha256 `bef783d7…`, same hour, `<adb serial>`)

Instrument: `r11-evlog.py` (Hyprland socket2 listener, rebased on a mark file) and
`r11-procs.py` (0.1 s `/proc` poll of the session's own process family), both started from
`session.env`. Fresh scratch copies; the R10 tools are read-only.

| Arm | hand-over | desktop PASS | bar | background | dock | launcher/back | marker |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mobile cold 1 | 10.8 s | 10.3 s | 2.37 (stock bar, closes at 2.43) | 2.63 | 5.55 | 9.55 | 9.80 |
| mobile cold 2 | 10.7 s | 10.2 s | 2.38 (closes at 2.38) | 2.44 | 9.05 | 9.11 | 9.26 |
| desktop cold | 3.5 s | 3.0 s | 2.03 | 2.30 | — | — | 2.50 |

- The two mobile arms ran `tile-state.sh` from 2.51 s to 9.64 s / 9.11 s — **7.13 s / 6.60 s** —
  and the dock, launcher, back strips and the final bar all mapped in the second that pass
  exited. The desktop arm has no `omamobile.quicksettings`, no `tile-state.sh`, and its marker at
  2.50 s. The two arms differ by that plugin alone; the shell binary, compositor and geometry are
  identical.
- A shell restart (`omarchy-restart-shell`) in mobile mode reproduces the delay (layers 10.8 s
  after the surviving shell's start), so this is not a cold-cache effect. Caveat: that command
  starts three shells under proot (one direct, one through `hyprctl dispatch`, one retry), so
  the restart arm is noisier than the cold-start arms; phases 2-3 use it only for A/B.
- Steady state, R10 build: the bar's cell and call watcher stubs each forked every 5 s and the
  launcher's `omamobile-osk-watch` every 3 s for the life of the session (three loops, ~0.5
  forks/s, all failing).

## Switches

- `OMDROID_QS_PROBE_AT_LOAD=1` in `~/.config/omdroid/session.env` → the probe runs at load again
  (the old behaviour, for an A/B on the merged build).
- `OMAMOBILE_TILE_STATE_CACHE` → where the pass caches its output (`~/.cache/omamobile/tile-state`).

## Risks

- The sheet now starts from the previous session's cached state; a tile that changed while no
  session ran (a theme switch, a modem state) shows stale for the first 8 s or until the sheet is
  opened, which re-probes. With no cache the tiles are simply dimmed for those 8 s.
- The deferred pass still runs on the shell's own thread pool; parallel it is bounded by the
  slowest probe (3 s), not by nine serial ones.

## Not done
