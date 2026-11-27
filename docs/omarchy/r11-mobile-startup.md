# R11 S2 — the mobile UI starts about as fast as the desktop UI

Branch `r11/mobile-startup`, worktree `<repo>` (stream S2 of the R11 round).
Base `90d7494`. Owner request this answers: "the mobile UI's slow start" from the R10
report, i.e. mobile hand-over 10.7-11.2 s against desktop 3.0-3.5 s on the same build.

## STATUS

| # | Step | State | Proof |
| --- | --- | --- | --- |
| 1 | Timeline instrument (evlog + process sampler), shell restart vs cold start | PENDING | — |
| 2 | Bisect: one omamobile plugin at a time out of the shell's plugin list | PENDING | — |
| 3 | Fix the cause, behind a switch, SOURCE.md updated | PENDING | — |
| 4 | Prove on an APK: 3 mobile + 3 desktop cold starts, alternating, target mobile within 1.5 s of desktop; mobile gestures still pass | PENDING | — |
| 5 | Steady state: CPU of every omamobile helper at idle over 60 s | PENDING | — |

## What changed

(nothing yet)

## Host proof

## Device proof

## Switches

## Risks

## Not done
