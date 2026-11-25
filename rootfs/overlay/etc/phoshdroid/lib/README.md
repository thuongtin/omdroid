# /etc/phoshdroid/lib: aquamarine with touch

`libaquamarine.so.13` is aquamarine 0.14.0 with this project's two patches. The second one
adds `wl_touch` to the Wayland backend, which the nested Hyprland uses for its input under
cage. Without it Hyprland lists no touch device and a finger reaches no surface
(`docs/omarchy/r4-touch-report.md`, `docs/omarchy/r5-touch-patch-report.md`). The device
proof is in `docs/omarchy/r5-touch-device-report.md`.

| | |
|---|---|
| File | `libaquamarine.so.13`, named by its SONAME, a regular file (not a link) |
| Size | 1 775 168 bytes |
| sha256 | `8514d2a65f2e10bb75d74a97cd3bc97db52f06bc19ecd0a47395aa9fdae66191` |
| Source | https://github.com/hyprwm/aquamarine at `a79fb21b2e2a82dd061a6d071802bcf38bd5c383` (0.14.0) |
| Patch 1 | `rootfs/patches/aquamarine/0001-wayland-carry-proven-Android-KGSL-buffer-pipeline.patch`, sha256 `86ff2be2254760fde311d3adf0e0a416028922fe51b9004dd00e5ea93042196e` |
| Patch 2 | `rootfs/patches/aquamarine/0002-wayland-add-wl_touch-input.patch`, sha256 `48448110cf8e15ba43abdd9650f5c7093d8ee2f6dd8724dc7613528404d9d787` |
| Build | clang, aarch64, inside the guest image under qemu-user (`rootfs/build-aquamarine.sh`) |
| Licence | BSD-3-Clause, `LICENSE` beside this file |

## How it reaches the guest

- An updated install: the APK carries this directory (`syncGuestOverlay` in
  `app/build.gradle.kts`, `lib/**`), and `GuestOverlay` writes it to `/etc/phoshdroid/lib/`
  on every start when the bytes differ.
- A fresh image: `rootfs/package-omarchy-rootfs.sh` copies it in its "Applying overlay" block.
- `start.sh` puts `/etc/phoshdroid/lib` first in `LD_LIBRARY_PATH`. Hyprland has no
  `RPATH`/`RUNPATH`, so this copy wins over the image's
  `/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0`, which stays untouched.
- A new library is loaded by a session start, not by the shell-only restart a size change uses.

## Rebuild

```sh
./rootfs/build-aquamarine.sh
cp ~/.cache/omdroid/aquamarine/out/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0 \
   rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13
sha256sum rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13
```

The script applies both patches to the pinned revision, builds in the `omdroid-aquamarine:0.0.14`
image and prints an ABI comparison against the image's library (SONAME, NEEDED, strong symbols,
the symbols Hyprland and hyprctl import, highest GLIBC version). Its run on 2026-11-25 printed
the sha256 above, so the build reproduced these exact bytes.
