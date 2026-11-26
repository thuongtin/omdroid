# Release 0.0.16-alpha

Built from `3e68f9d`. APK `omdroid-0.0.16-alpha.apk`, 1,715,791,466 bytes, sha256
`894953bc625f6d1a5568115e8c02240d4e7afeaf312caff269b5b016e1e474c6`.

Verified on the tablet from a fresh guest (the guest an earlier system upgrade broke was
moved aside to `installed-rootfs/omarchy-upgraded-20261126` and the app extracted a new one
from the image):

| Item | Result |
| --- | --- |
| Install over 0.0.16 test builds | `pm install` PASS, sha matches, `lastUpdateTime` new |
| Cold start, unaided | hand-over 11.3 s, desktop drawn 11.9 s, no relaunch, nothing foreign on top |
| `probe.sh -q` | PASS |
| Hard-link repair on the fresh guest | `/usr/bin/ld` present; `gcc` links a hello world |
| `sudo id` | `uid=0(root)` |
| `sudo pacman -Q pacman` | `pacman 7.1.0.r9.g54d9411-2`, exit 0 |
| `sudo pacman -Syu` | refused with the pinned-desktop message, exit 1 |
| bare `yay` | refused with the same message, exit 1 |
| `yay --version` bootstrap | **blocked upstream**: the Arch Linux ARM mirrors advertise packages their file lists do not serve (`patch-2.8-1`, `flex-2.6.4-6`, `automake-1.18.1-1`, `pkgconf-3.0.6-1`, `groff-1.24.1-1`, `texinfo-7.3-1` all 404 on every mirror, `mirror.archlinuxarm.org` included, checked from the host). The same bootstrap installed `yay-bin` in 1 min 28 s and built, ran and removed `cbonsai` earlier the same day, so this is the mirrors lagging, not the shim; the shim now retries unreachable mirrors and skips only packages a reachable mirror really does not carry. Re-run `yay --version` once the mirrors catch up. |

Known limit recorded in the README: a bare `yay` is `yay -Syu`, and a full upgrade moves the
libraries the patched Hyprland/aquamarine/Mesa were built against. That is what broke the
tablet's earlier guest: `libhyprgraphics.so.4` went missing, then the newer library wanted a
newer `libjxl`, then Hyprland aborted in `loadGLProc`. No library alias reproduces that
dependency closure, so the guards refuse the upgrade instead, with
`OMDROID_ALLOW_UPGRADE=1` as the escape hatch.
