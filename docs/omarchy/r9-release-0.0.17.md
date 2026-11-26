# Release 0.0.17-alpha

Supersedes 0.0.16-alpha, which shipped a `yay` bootstrap that could not refresh the guest's
package databases. Built from `release: 0.0.17-alpha` on `main`.

## What changed since 0.0.16

- The `yay` bootstrap syncs with `pacman -Syy`. The guest's databases come from image build
  time, and a plain `-Sy` keeps them when a lagging mirror answers with an old copy: on a
  fresh guest it listed `patch 2.8-1` while the mirrors served `2.8.1-1`, so every package
  fetch 404ed and the bootstrap could not install its build tools. Measured before and
  after on the tablet: with `-Sy` the bootstrap failed in 19 s; with `-Syy` it finished in
  53 s and `yay v13.1.0 - libalpm v16.0.1` ran.
- `debugedit`, `groff` and `texinfo` are no longer installed as part of the build tools.
  `debugedit` needs `gdb`, which the mirrors 404ed, and `makepkg` here runs with `!debug`
  and needs neither man-page tool.
- An unreachable mirror is retried instead of being read as a missing package. The
  mirrorlist ships dead hosts (`vn`, `pt`, `za`, `au`, `br2`, `sg` do not resolve on this
  image); only a package a reachable mirror really does not carry is skipped.

## Verified on the tablet

| Item | Result |
| --- | --- |
| Install | `pm install` PASS, sha256 `88322a12…7be71501`, `lastUpdateTime` new |
| Cold start, unaided | hand-over 12.5 s, desktop drawn 11.9 s, no relaunch, nothing foreign on top |
| `probe.sh -q` | PASS |
| `yay --version`, clean guest | bootstrap 53 s, then `yay v13.1.0 - libalpm v16.0.1` |
| `yay --version`, second call | 0.19 s, no bootstrap |
| `yay -S cbonsai` (AUR) | built and installed in 22 s |
| Running it | `/usr/bin/cbonsai -p` exit 0, 22,728 bytes of ANSI tree with `TERM=xterm-256color` |
| `yay -R cbonsai` | removed, `pacman -Q` reports it gone |
| `sudo id` | `uid=0(root)` |
| `sudo pacman -Syu` | refused with the pinned-desktop message, exit 1 |
| bare `yay` | refused with the same message, exit 1 |

Guests extracted before the hard-link fix still repair themselves on the first start
(`omdroid-repair-links.sh`); this release was checked on a guest extracted earlier the same
day, so `/usr/bin/ld` and `gcc` were already repaired.

## Not verified

- A clean install (no earlier guest on the device).
- The interactive `sudo` password prompt; every check above used the broker non-interactively.
- DeX and a real phone dock.
