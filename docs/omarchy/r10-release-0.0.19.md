# Omdroid 0.0.19-alpha release

The R10 round merged (idle CPU, first start, APK size, the software GPU fallback, 16 KB page
alignment), plus the session-end fix from R11: ending the session from inside no longer leaves
the launcher blank with an "isn't responding" dialog.

## What changed

- **Idle CPU.** The nested Hyprland now sends the damage it committed instead of the whole screen
  (`rootfs/patches/aquamarine/0003-wayland-send-committed-damage.patch`, built with
  `rootfs/build-aquamarine.sh` and shipped as `lib/libaquamarine.so.13`). On the tablet, two cold
  starts of each build in the same hour, same guest, CPU over 60 s starting 30 s after the start:
  the session went from 154-159 % of one core to 12 %, the app's own process from 130-134 % to
  2.5-2.6 %. With full damage forced on the same build (`AQ_WAYLAND_FULL_DAMAGE=1`) the app was
  at 135 % again. Measurements and the arm table: `docs/omarchy/r10-integration.md` runs 1 and 3.
- **First start.** The guest image is zstd instead of gzip, and it leaves out documentation, man
  pages, non-English message catalogs and Qt translations (15,523 entries, 418,199,488 bytes of
  the old image). Extraction on the tablet: 104.1 s, against 283.9 s for the 0.0.17-era image
  (`launch: rootfs-extracted 104112ms`). `pacman -Qk` now lists the pruned paths as missing, and
  a later `pacman -S` skips them too (`NoExtract` in the image's `pacman.conf`).
- **APK size.** 1,124,728,775 bytes for the R10 build against 1,715,790,990 for 0.0.18
  (34.4 %). The image is 999,547,702 bytes and unpacks to 68,343 members, every one owned `0/0`
  (the old images carried the builder's user name on all 83,316 members).
- **The watcher** asks Hyprland over its request socket instead of starting `hyprctl` every tick:
  0 `hyprctl` processes in 10 s, against 54 on 0.0.18 and 49 with `OMDROID_WATCH_LEGACY=1`.
- **Software GPU setting.** Settings, Graphics: Auto, Adreno GPU (KGSL) or Software. Auto follows
  the device (`launch/GpuMode.kt`); with Auto, a start that fails early on the GPU path retries
  once with software (`session-child.sh`, host-tested with a fake Hyprland). Forced on the tablet:
  llvmpipe draws the desktop, hand-over 13.8 s against 11.0 s, Hyprland 445.6 MB against about
  205-212 MB at idle, and typing into a terminal used 496 % of a core in Hyprland against 31 %.
- **16 KB pages.** Every 64-bit library in the APK is linked for 16 KB pages: 14 at `0x4000`, 2 at
  `0x10000` (`readelf` on `lib/arm64-v8a` and `lib/x86_64`). No 16 KB device has run it.
- **Smaller changes.** Hyprland animations are off in the mobile UI (`OMDROID_ANIMATIONS=1` keeps
  them); `MALLOC_ARENA_MAX=2` in the guest (`session.env` can override it); `onTrimMemory` and
  `onLowMemory` are logged; a new setting, "Lift Android's child-process limit", turns Android
  12+'s phantom-process killer off through `WRITE_SECURE_SETTINGS`.
- **The session-end fix** (three commits from R11, cherry-picked onto `r10/integration`):
  `ProcessStop` runs every stop on its own thread (SIGTERM, bounded wait, SIGKILL, bounded wait,
  outcome logged) instead of an unbounded `Process.waitFor()` on the main thread; `ProcTree`
  signals the broker proot's descendants, so the fake-root broker ends on every guest-exit path;
  `FailedLaunch` shows the ended screen with the exit code when a launch's guest died, instead of
  "did not start: session_died". The cause, the device phases and the numbers are in
  `r11/completeness:docs/omarchy/r11-completeness.md` section 6.
- **APK withdrawals.** The Phoshdroid APKs of 0.0.1 to 0.0.12 were withdrawn on 2026-11-27 and
  those of 0.0.13 to 0.0.17 on 2026-11-26. Their notes stay up; the 0.0.1-0.0.12 notes say only
  that the APK is withdrawn and point here, because it was not established that those APKs
  embedded a build-machine path.

## Verified on the tablet

| Item | Result |
| --- | --- |
| Install over the R10 build | sha256 `2d10847e…032c`, `versionCode=19`, `versionName=0.0.19-alpha`, `install.sh` PASS |
| Cold starts, unaided | hand-over 11.3 and 12.4 s, desktop PASS 2/2, no foreign activity on top; `probe.sh` PASS |
| Idle, 30 s after the start | X server threads 1.3 % and 1.2 % of a core over 10 s; app PSS 184.9 MB, Hyprland 186.7 MB |
| Exit from inside, twice | `proot exited (0)` and `proot exited (139)`; the ended screen 38 and 37 ms later, "Start again" on screen; no ANR |
| Start again | desktop back and `probe.sh` PASS after 16 s |
| Guest dies at launch (`session.env`: `exit 7`) | "The desktop session stopped unexpectedly (exit 7)" within 2 s; no ANR |
| Start again after that | desktop back and `probe.sh` PASS after 18 s |
| Restore | R10 build back (`pm install -r -d -t`), sha `bef783d7…`, cold start 11.3 s, `probe.sh` PASS |

Unit tests 195, 0 failed. Lint 0 errors, 37 warnings.

APK: `omdroid-0.0.19-alpha.apk`, 1,124,748,147 bytes, sha256
`2d10847e8522fdf24bc6ab326e1ecd47fa73a624f17bf81bbce50479269c032c`.

## Limits

- Cold start is about 1 s slower than 0.0.18 (hand-over 10.7-11.2 s against 9.7-10.0 s in the same
  hour): the CPU clocks up later when the X server is idle. The mobile UI starts about 7 s later
  than the desktop UI, which was already so in 0.0.18; a fix is in progress.
- Hyprland segfaults as it exits, on every exit observed so far (9dae471b: 3 of 3 clean
  exits; `Segmentation fault -- "HYPRLAND" --config ...` in the session log), while the exit code
  the app receives may read 0 (0, 139 and 0 were seen). The desktop is not affected: the session
  was already ending. On 0.0.19 two exit-from-inside runs drew the ended screen 38 and 37 ms after
  the app logged the session's exit (its own field read 5 and 6 ms), Start again brought a passing
  desktop back in 16 s, and a launch whose guest died with exit 7 showed "stopped unexpectedly
  (exit 7)" within 2 s; no case raised an ANR. The exit code under-reports what happened.
- **Software GPU mode is heavy** (numbers above).
- **Idle memory did not change** (689-697 MB total PSS against 695-714 MB for 0.0.18 in the
  same hour).
- **Man pages, documentation and message catalogs are gone from the guest** (see APK size).
- Software GPU mode is heavy (numbers above).
- Not verified: a clean install, any 16 KB-page device, any phone, the interactive `sudo` password
  prompt, docking from the phone, memory pressure (`onTrimMemory` was never triggered).
