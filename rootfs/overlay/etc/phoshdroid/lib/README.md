# /etc/phoshdroid/lib: aquamarine with touch and real damage

`libaquamarine.so.13` is aquamarine 0.14.0 with this project's three patches. The second one
adds `wl_touch` to the Wayland backend, which the nested Hyprland uses for its input under
cage. Without it Hyprland lists no touch device and a finger reaches no surface
(`docs/omarchy/r4-touch-report.md`, `docs/omarchy/r5-touch-patch-report.md`). The device
proof is in `docs/omarchy/r5-touch-device-report.md`. The third one sends the damage Hyprland
committed instead of the whole surface on every commit, so cage and the X server copy only what
changed (`docs/omarchy/r10-damage.md`).

| | |
|---|---|
| File | `libaquamarine.so.13`, named by its SONAME, a regular file (not a link) |
| Size | 1 775 920 bytes |
| sha256 | `35a9ffd4c565364900a13c53fee935898c5885bd2508c527228b752d316d1562` |
| Source | https://github.com/hyprwm/aquamarine at `a79fb21b2e2a82dd061a6d071802bcf38bd5c383` (0.14.0) |
| Patch 1 | `rootfs/patches/aquamarine/0001-wayland-carry-proven-Android-KGSL-buffer-pipeline.patch`, sha256 `86ff2be2254760fde311d3adf0e0a416028922fe51b9004dd00e5ea93042196e` |
| Patch 2 | `rootfs/patches/aquamarine/0002-wayland-add-wl_touch-input.patch`, sha256 `48448110cf8e15ba43abdd9650f5c7093d8ee2f6dd8724dc7613528404d9d787` |
| Patch 3 | `rootfs/patches/aquamarine/0003-wayland-send-committed-damage.patch`, sha256 `61dc6fc6176ef9013a05b6c19694e77fecdac9a678dc6c0f84b1d80741687daf` |
| Build | clang, aarch64, inside the guest image under qemu-user (`rootfs/build-aquamarine.sh`) |
| Licence | BSD-3-Clause, `LICENSE` beside this file |

## Switches

- `AQ_WAYLAND_FULL_DAMAGE=1` in the environment of the session (Hyprland reads it once) sends
  the whole surface with every commit, the behaviour of the previous library (patch 3 off).
  Any other value, or none, sends the committed damage.
- `AQ_TRACE=1` (the `/etc/phoshdroid/trace` debug switch in `start.sh`) logs
  `commit damage N rect(s)` for every commit, with `(whole surface)` when the whole surface was sent.

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

The script applies all three patches to the pinned revision, builds in the `omdroid-aquamarine:0.0.14`
image and prints an ABI comparison against the image's library (SONAME, NEEDED, strong symbols,
the symbols Hyprland and hyprctl import, highest GLIBC version). Its run on 2026-11-26 printed
the sha256 above, so the build produced these exact bytes.
