# R10 S1: guest diet (watcher, malloc, mobile session)

Stream S1 of the R10 memory round. Worktree `proot-post-r10-guest`, branch
`r10/guest-diet`, base `bbf908d`. Every host number in this file was measured on
this machine; every device claim is PENDING with the command the parent should
run and what PASS looks like.

## STATUS

| # | Step | Status | Proof |
|---|---|---|---|
| 1 | Hyprland queries over the IPC socket, not `hyprctl` forks | PENDING | |
| 2 | Poll Hyprland only when something can have changed | PENDING | |
| 3 | Host test harness `docs/omarchy/tools/watch-ipc-test.py` | PENDING | |
| 4 | Session environment knobs in `start.sh` (arenas, shader cache, `session.env`) | PENDING | |
| 5 | No Hyprland animations in the mobile UI | PENDING | |
| 6 | voxtype only when a model exists | PENDING | |

## What changed

(filled per step)

## Host proof

(filled per step)

## Device A/B plan (the parent runs it)

(filled at the end)

## Risks

(filled at the end)

## What I did not do

(filled at the end)
