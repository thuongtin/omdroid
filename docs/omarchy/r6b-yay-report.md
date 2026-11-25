# R6b-YAY report: `yay` and `makepkg` in the Omdroid guest

Worker session report. Brief: `docs/omarchy/brief-r6b-yay.md`. Scratch: `<scratch>/omarchy/r6/yay/`.
Head at start: `c8691a5`.

## STATUS TABLE

| Step | What | Status |
|---|---|---|
| Y0 | Premises: yay-bin aarch64, makepkg fakeroot calls, fakeroot IPC mode | PASS (sources below) |
| Y1 | Shared module, refactored sudo, fakeroot shim, yay shim, selftest cases | PASS (34/34 on the build machine) |
| Y2 | End-to-end on aarch64 in the arm64 guest image (qemu, two simulated proots) | PENDING |
| Y3 | Host gate (compile, test, lint, unit-count) | PENDING |
| Y4 | Build APK, sha256 | PENDING |
| Y5 | README | PENDING |
| Y6 | Report + manual test for Phil | PENDING |

## Y0. Premises

PASS. Everything below was read out of the guest image `omdroid-guest:0.0.14` (arm64, run under
qemu-user) or from the upstream package sources; nothing is assumed.

**The guest image.** `uname -m` is `aarch64`, `/etc/os-release` says `Arch Linux ARM`. In it:
`makepkg` (`/usr/sbin/makepkg`, pacman 7.1.0), `git`, `python3`, `binutils 2.46+r70+g155188ea10a7-1`,
`pacman`; and `pacman -Q` finds no `yay`, `paru`, `fakeroot`, `gcc` or `make` (no `base-devel`).
`/etc/pacman.conf` carries `[core]`, `[extra]`, `[alarm]`, `[aur]`. After `pacman -Sy` in the
container: `base-devel 1-2` (architecture `any`) and `fakeroot 2:1.37.2-1` (`aarch64`) both come from
`core`, so the guest can install both — and neither repo carries `yay` or `paru` (`pacman -Si yay`
answers "package not found"). The five scripts that call `yay` are exactly the ones the brief names:
`omarchy-pkg-aur-add`, `omarchy-pkg-aur-install`, `omarchy-pkg-remove`, `omarchy-update-aur-pkgs`,
`omarchy-upgrade-to-quattro`.

**yay-bin ships aarch64.** AUR `yay-bin` 13.1.0 (PKGBUILD fetched into the scratch dir):
`arch=('x86_64' 'aarch64' 'armv7h')`, `source_aarch64=(".../yay_13.1.0_aarch64.tar.gz")` with a
sha256, and `package()` only `install`s the prebuilt binary, man page, completions and locales — no
`build()` at all, so nothing is compiled. `depends=('pacman>6.1' 'git')`; `optdepends` names `sudo`,
which is what the previous round gave the guest.

**How makepkg calls fakeroot** (`/usr/bin/makepkg` 7.1.0, copied out of the image):

- `check_software` only wants the binary to exist: `libmakepkg/executable/fakeroot.sh` does
  `type -p fakeroot` when `SOURCEONLY || BUILDPKG`. No version check.
- The package step is `enter_fakeroot()`: `fakeroot -- bash -$- "${BASH_SOURCE[0]}" -F "${ARGLIST[@]}"`.
  `-F` sets `INFAKEROOT=1`, and line 1239-1249 then **requires `FAKEROOTKEY` to be set in the
  environment** (`Do not use the '-F' option. This option is only for internal use by makepkg.`) while
  the `EUID == 0` refusal (`Running makepkg as root is not allowed...`) is skipped. So the shim must
  set `FAKEROOTKEY` and may run as uid 0.
- `write_pkginfo()` writes `# using $(fakeroot -v)` into `.PKGINFO`, so `-v` must print a line.
- makepkg's own pacman escalation is `run_pacman()`: `PACMAN_AUTH` if configured, else
  `sudo -k pacman ...` when `sudo` is on PATH, else `su root -c`. `makepkg -i` therefore goes through
  the sudo client, and `sudo -k` must be accepted (it is).
- Nothing else in the tree mentions fakeroot (`grep -rn fakeroot /usr/share/makepkg/` finds only that
  one executable check), so `fakeroot [--] cmd...` and `fakeroot -v` are the whole surface makepkg
  uses.

**fakeroot's IPC mode is SysV.** Arch's `fakeroot` PKGBUILD (1.37.2, fetched) configures
`--with-ipc=sysv`; Arch Linux ARM ships `core/fakeroot 2:1.37.2-1` (aarch64) built from that recipe.
SysV IPC needs `CONFIG_SYSVIPC`: AOSP's GKI `android14-6.1` `gki_defconfig` has no `CONFIG_SYSVIPC`
line at all, and `init/Kconfig` declares `config SYSVIPC` as a plain `bool` with no default, so it is
off in Android's kernel. The guest has already measured the consequence: `start.sh`'s header records
weston dying with `x11shm: failed to allocate SHM segment` because `shmget` returns `ENOSYS` in the
app sandbox. A stock `fakeroot` therefore cannot work in the guest, which is what the shim replaces.

**One premise of my own that I checked, because the broker depends on it.** The broker only accepts a
peer whose `SO_PEERCRED` uid equals its own `getuid()`. Under proot both proots are the same real (app)
uid but the broker's `getuid()` is the fake 0. termux/proot's `fake_id0` extension intercepts
`getsockopt(SOL_SOCKET, SO_PEERCRED)` (`src/extension/fake_id0/getsockopt.c`) and rewrites the reported
uid/gid to the peer's fake ids — and when the peer is under *another* PRoot instance it falls back to
the tracee's own fake ids when the real uid matches. So on the tablet the check passes; in the
container simulation there is no proot, so the broker grew `--allow-peer-uid` (below).

## Y1. Code

PASS.

- `rootfs/overlay/etc/phoshdroid/omdroid_root.py` (new) — the client side of the broker protocol,
  lifted out of `sudo` so both clients share it: frame constants, `socket_path()` (`OMDROID_ROOTD_SOCK`,
  then the old `OMDROID_SUDO_SOCK`, then `/tmp/omdroid-root/sock`), `terminal_size()`, `tty_spec()`,
  the raw-mode `Screen`, and `relay(request, prog)`, which connects (one line and exit 1 when the
  broker is absent), sends the JSON request, pumps stdin from a thread, relays stdout/stderr/error
  frames, tracks `SIGWINCH`, restores the terminal on every exit path and returns the broker's exit
  code.
- `rootfs/overlay/etc/phoshdroid/sudo` — same options, same environment, same messages; it now builds
  the request and calls `omdroid_root.relay(..., "sudo")`. Nothing else changed, which the old cases
  confirm (all 27 still pass).
- `rootfs/overlay/etc/phoshdroid/fakeroot` (new) — `fakeroot [--] cmd...` sends the command to the
  broker with `keep_env: true`, the caller's cwd, its stdio (pty when stdin is a tty) and
  `FAKEROOTKEY` set (`setdefault`, so a nested call keeps the outer key); target user `root`
  (`OMDROID_ROOTD_DEFAULT_USER` overrides it for the host harness only). `-v`/`--version` prints
  `fakeroot version 1.37.2 (omdroid shim: fake root through the root broker)`, `-h`/`--help` prints
  usage, no command is a usage error. `-s/-i` (saved/loaded fake state) and the IPC-selection flags
  `-x/-t/-P/-l` are refused with `not supported here (<reason>)`: a saved fake state cannot survive
  the broker, which runs one process per request. makepkg uses none of them.
- `rootfs/overlay/etc/phoshdroid/yay` (new) — `os.execv("/usr/bin/yay", ...)` when the package is
  installed. Otherwise, under an `flock` on `~/.cache/omdroid/yay.lock` (a second `yay` waits, then
  execs the result instead of building twice): progress lines on stderr, then
  `sudo pacman -S --needed --noconfirm base-devel git`, `git clone --depth 1
  https://aur.archlinux.org/yay-bin.git`, `makepkg -si --noconfirm` in the clone, a
  `/usr/bin/yay` existence check, and `exec` of it with the caller's arguments. Every step's output is
  echoed and appended to `~/.cache/omdroid/yay-bootstrap.log`. A failure prints one line
  (`yay: could not install yay-bin: <step> failed (exit N); log: <path> (build dir <dir>)`), exits 1
  and leaves nothing on PATH: `/usr/local/bin/yay` is the shim and `/usr/bin/yay` only appears when
  pacman has installed the package.
- `rootfs/overlay/etc/phoshdroid/omdroid-rootd.py` — only the peer check changed: the accepted uids are
  a set (`PEER_UIDS = {os.getuid()}`) and a new `--allow-peer-uid UID` (repeatable) adds to it. The
  device never passes it; the container test needs it because it has no proot to rewrite
  `SO_PEERCRED` (Y0). Comment in the file says exactly that.
- `docs/omarchy/tools/rootd-selftest.py` — 7 new fakeroot cases (full env passed, `FAKEROOTKEY` set,
  cwd, exit code, stdin, `-v`/`--version`, no command, and `-s` refused) on top of the 27 sudo ones.

Harness result on this machine (`python3 docs/omarchy/tools/rootd-selftest.py`):

```
PASS argv_passthrough ... broker_absent_fails_fast        (the 27 sudo cases, unchanged)
PASS fakeroot_full_env_is_passed
PASS fakeroot_cwd_is_the_callers
PASS fakeroot_exit_code_passes_through
PASS fakeroot_stdin_is_streamed
PASS fakeroot_version
PASS fakeroot_no_command_is_a_usage_error
PASS fakeroot_unsupported_option_is_an_error

34/34 passed
```

## Y2. End-to-end on aarch64

PENDING

## Y3. Host gate

PASS.

```
$ ./gradlew :app:compileDebugKotlin :app:test :app:lintDebug --console=plain
BUILD SUCCESSFUL in 2s
325 actionable tasks: 19 executed, 306 up-to-date
$ python3 docs/omarchy/tools/unit-count.py
unit tests 98 failed 0
```

98, not the brief's 69: while this round was running, a parallel session committed the dock
work (`d1bd409 feat(launcher): dock state, UI-mode pin and target-display geometry`, which
added `DockStateTest` with 10 cases and grew `DisplayGeometryTest`/`UiModeTest`), so the
tree the gate ran on carries 29 more tests than the r6-sudo report's 69. `unit-count.py`
counts only `testDebugUnitTest`, so the number is the tree's, not a double count.

One flake on the first attempt, unrelated to this change: `:app:lintDebug` died with
`Cannot access output property 'partialResultsDirectory' ... NoSuchFileException:
app/build/intermediates/android_test_lint_partial_results/debug/lintAnalyzeDebugAndroidTest/out/lint-partial.xml`
— a stale Gradle intermediates directory. Removing that directory and re-running the same
command turned it green.

## Y4. Build

PENDING

## Y5. README

PASS.

- `Known limits`: the `sudo` paragraph is followed by a `yay` paragraph — the shim, what the
  first call installs (`yay-bin`, a prebuilt aarch64 binary, plus `base-devel` and `git` from
  `core`), that it needs the network and takes a few minutes, where the log is, that `makepkg`
  works because `fakeroot` is a shim to the same broker (real fakeroot needs SysV IPC Android
  does not have), and the `arch=('x86_64')` refusal with `yay --mflags --ignorearch` as the
  escape hatch and its warning.
- `Not verified yet`: the sudo bullet's harness count is now 34 (7 fakeroot cases), and a new
  bullet says exactly what the container run does not prove.

## Y6. Report

PENDING
