# R8 dock input report: the dock's keyboard and mouse drive Omarchy on the monitor

Brief: `docs/omarchy/brief-r8-dock-input.md`. Worker: Paseo agent `5af20376` (parent `f8d5582c`),
working in the main checkout `<repo>` (branch `main`).
Scratch: `<scratch>/omarchy/r8/input/`.

## STATUS TABLE

| Step | What | Verdict | Proof |
| --- | --- | --- | --- |
| I0 | test4 install + repair-links check (ld, gcc, yay cbonsai) | **PASS** | install sha `8e7a7266…a3a8ca2e0` PASS (`lastUpdateTime 14:17:57`); cold start handover +78.7 s (first start after the update: the repair runs), desktop PASS +80.3 s, `probe.sh -q` PASS; `omdroid-repair-links: restored 1830, already present 2, failed 0`; `/usr/bin/ld` 2500416 B present; gcc 16.1.1 hello world `gcc_rc=0`, prints `hello r8`; `yay -S --noconfirm cbonsai` rc 0 (makepkg compiled `cbonsai.c` with cc, installed), `cbonsai -p -L 5` rc 0 (21696 B of curses output), `yay -R --noconfirm cbonsai` rc 0, `pacman -Q cbonsai` then `was not found` (14:21:00-14:21:22, TERM=xterm-256color, run inside the session with `sx.sh`) |
| I1 | reproduce: simulated display + uhid kbd/mouse, Settings focused on display 0 | PENDING | |
| I2 | keys to X while docked (KeyInterceptor) | PENDING | |
| I3 | pointer to X while docked (accessibility motion events) | PENDING | |
| I4 | undock / re-dock / force-stop: Android keeps input | PENDING | |
| I5 | test5 APK for Phil + manual test | PENDING | |
| I6 | gate (unit tests, lint) + README Docking + contract section 8 | PENDING | |
| I7 | cleanup (overlay display, uhid, stay-awake 15, probe PASS) | PENDING | |

## Device state changes (restore commands)

- (none yet)

## Log
