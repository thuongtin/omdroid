# R10 S4 (damage): send the real damage to the parent compositor

Branch `r10/aquamarine-damage`, from `bbf908d`. Stream owner: aquamarine patch series only
(`rootfs/patches/aquamarine/`, `rootfs/build-aquamarine.sh`, the rebuilt library under
`rootfs/overlay/etc/phoshdroid/lib/`, this file). No device was available: every device claim
below is PENDING.

Evidence labels: **measured** (host command given), **read** (file:line), **estimated** (basis).

## Status table

| # | Step | Status | Proof |
|---|---|---|---|
| 1 | Facts (damage chain, wlroots, Present) with citations | PENDING | |
| 2 | Patch 0003 + build script edit | PASS (patch applies to the pinned revision, `Wayland.cpp` compiles); not yet built whole | `rootfs/build-aquamarine.sh --no-build` prints `patch series checksums verified` and `applied: ... send the committed damage ...`; the changed TU built under clang in the guest image (host, qemu-user) with no new warning |
| 3 | Build, ABI comparison, copy to overlay, lib README | PENDING | |
| 4 | VFR analysis (no code) | PENDING | |
| 5 | Device A/B plan | PENDING | |
