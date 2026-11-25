# R6b-YAY report: `yay` and `makepkg` in the Omdroid guest

Worker session report. Brief: `docs/omarchy/brief-r6b-yay.md`. Scratch: `<scratch>/omarchy/r6/yay/`.
Head at start: `c8691a5`.

## STATUS TABLE

| Step | What | Status |
|---|---|---|
| Y0 | Premises: yay-bin aarch64, makepkg fakeroot calls, fakeroot IPC mode | PASS (sources below) |
| Y1 | Shared module, refactored sudo, fakeroot shim, yay shim, selftest cases | PASS (35/35 on the build machine) |
| Y2 | End-to-end on aarch64 in the arm64 guest image (qemu, two simulated proots) | PASS (3 findings, one a real `sudo -k` bug) |
| Y3 | Host gate (compile, test, lint, unit-count) | PASS (98 tests, 0 failed) |
| Y4 | Build APK, sha256 | PASS (`7a42c3d1…` from tree `6834e6c`) |
| Y5 | README | PASS |
| Y6 | Report + manual test for Phil | PASS |

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
  the request and calls `omdroid_root.relay(..., "sudo")`. One behaviour changed later in the round,
  from a Y2 finding: `-k` alone is still a no-op, but `-k <command>` now runs the command, as sudo
  does (makepkg installs with `sudo -k pacman -U`). The old cases all still pass (27 unchanged, plus
  the new `-k` case and 7 fakeroot ones: 35/35).
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
  cwd, exit code, stdin, `-v`/`--version`, no command, and `-s` refused) on top of the 27 sudo ones,
  plus `reset_timestamp_with_a_command_runs_it` for the `-k` fix found in Y2.

Harness result on this machine (`python3 docs/omarchy/tools/rootd-selftest.py`):

```
PASS argv_passthrough ... broker_absent_fails_fast        (the 27 sudo cases, unchanged)
PASS reset_timestamp_with_a_command_runs_it
PASS fakeroot_full_env_is_passed
PASS fakeroot_cwd_is_the_callers
PASS fakeroot_exit_code_passes_through
PASS fakeroot_stdin_is_streamed
PASS fakeroot_version
PASS fakeroot_no_command_is_a_usage_error
PASS fakeroot_unsupported_option_is_an_error

35/35 passed
```

## Y2. End-to-end on aarch64

PASS, with three findings (one of them a real bug in the round-6 `sudo`).

**Setup.** Container `omdroid-yay-test` from `omdroid-guest:0.0.14` — arm64, running under
qemu-user binfmt, `uname -m` = `aarch64`, Arch Linux ARM. proot cannot run under qemu-user, so
the two proots are simulated with real uids: the broker as the container's root (what `-0`
gives it on the phone) and the client side as `omarchy`, uid 1000. The overlay files were copied
to `/etc/phoshdroid/` and linked into `/usr/local/bin` exactly as the packager and `start.sh`
do. Two harness-only adjustments, neither needed on a device: `--allow-peer-uid 1000` on the
broker (on the phone both proots are one app uid and proot's fake_id0 rewrites `SO_PEERCRED`),
and the socket directory/socket chmod'ed 0755/0666 from the root side (on the phone the
0700/0600 defaults already match the single app uid).

**What ran, as uid 1000** (the container was removed at the end of the round as the brief asks;
the chain scripts are kept in the scratch dir as `chain2.sh`/`chain3.sh`, and everything below is
quoted from that run):

```
$ command -v sudo fakeroot yay makepkg
/usr/local/bin/sudo   /usr/local/bin/fakeroot   /usr/local/bin/yay   /usr/sbin/makepkg
$ type -a fakeroot
fakeroot is /usr/local/bin/fakeroot      <- the shim wins over the real package
fakeroot is /usr/sbin/fakeroot
fakeroot is /usr/bin/fakeroot
$ sudo id
uid=0(root) gid=0(root) groups=0(root)
$ sudo pacman -Sy --noconfirm
:: Synchronizing package databases...
 core downloading... extra downloading... alarm downloading... aur downloading...
$ fakeroot -v
fakeroot version 1.37.2 (omdroid shim: fake root through the root broker)
$ fakeroot -- id
uid=0(root) gid=0(root) groups=0(root)
$ fakeroot -- sh -c 'echo FAKEROOTKEY=$FAKEROOTKEY; echo PWD=$PWD; echo MYVAR=$MYVAR'
FAKEROOTKEY=558      PWD=/tmp/yay-test      MYVAR=from-session
$ yay --version                       # first call: the bootstrap
yay: no AUR helper in this guest yet - first run installs yay-bin (base-devel plus a prebuilt
     binary, a few minutes)
yay: progress and the full log: /home/omarchy/.cache/omdroid/yay-bootstrap.log
yay: installing base-devel and git
... error: failed to prepare transaction (could not satisfy dependencies) ...   <- finding 1
yay: base-devel here would upgrade the guest's pacman and sudo; installing the build tools
     directly, the guest's libraries stay as they are
yay: the guest's mirrors do not carry flex right now; installing the rest        <- finding 2
Packages (26) ... Total Installed Size: 452.31 MiB
yay: fetching yay-bin from the AUR
yay: building and installing yay-bin
==> Entering fakeroot environment...
==> Starting package()...
==> Finished making: yay-bin 13.1.0-1
==> Installing package yay-bin with pacman -U...
installing yay-bin...
yay v13.1.0 - libalpm v16.0.1
$ yay -S --noconfirm cbonsai          # an AUR package that compiles
Sync Make Dependency (1): scdoc-1.11.5-1
AUR Explicit (1): cbonsai-1.4.2-1
==> Entering fakeroot environment...
cc -march=armv8-a -O2 ... cbonsai.c -lpanelw -lncursesw -o cbonsai
==> Finished making: cbonsai 1.4.2-1
==> Installing package cbonsai with pacman -U...
installing cbonsai...
$ cbonsai -p                          # the package runs
        &&&& ... &&&&&&&&\&&&&&/&&& ... (tree drawn)
$ yay -Qi cbonsai
Name : cbonsai   Version : 1.4.2-1   Architecture : any   Depends On : gcc ncurses
$ yay -R --noconfirm cbonsai
removing cbonsai...
$ pacman -Q cbonsai
error: package 'cbonsai' was not found
$ time yay --version                  # second call: no bootstrap
yay v13.1.0 - libalpm v16.0.1         real 0m0.613s
```

Why `cbonsai`: it is AUR-only (the repositories have no `cbonsai`), `arch=('any')` so aarch64 is
not refused, it compiles a single C file with gcc in seconds — so the run also proves that the
`base-devel` tools really reached the guest and that `package()` builds inside the fakeroot
shim — and `cbonsai -p` draws one tree and exits, so it can be run without a terminal.
(`yay -S pfetch` was the first choice and installed the *repository* package `pfetch-rs`, which
proves nothing about the AUR path.)

**Finding 1 — `pacman -S --needed base-devel` needs a system upgrade on the shipped image.**
The image has `openssl 3.6.4-1`; Arch Linux ARM's repositories are now on `openssl 4.1.0-1`, so
today's `base-devel` meta package (a real package in ALARM core, `1-2`, `Depends On: ... pacman
... sudo ...`) cannot be installed without replacing the base system:

```
error: failed to prepare transaction (could not satisfy dependencies)
:: installing openssl (4.1.0-1) breaks dependency 'libcrypto.so=3-64' required by cryptsetup
:: installing openssl (4.1.0-1) breaks dependency 'libcrypto.so=3-64' required by curl
:: installing openssl (4.1.0-1) breaks dependency 'libssl.so=3-64' required by curl
:: installing openssl (4.1.0-1) breaks dependency 'libcrypto.so=3-64' required by libarchive
:: installing openssl (4.1.0-1) breaks dependency 'libssl.so=3-64' required by libngtcp2
:: installing openssl (4.1.0-1) breaks dependency 'libcrypto.so=3-64' required by libsasl
:: installing openssl (4.1.0-1) breaks dependency 'libcrypto.so=3-64' required by openssh
:: installing openssl (4.1.0-1) breaks dependency 'libcrypto.so=3-64' required by pacman
:: installing openssl (4.1.0-1) breaks dependency 'libssl.so=3-64' required by socat
```

Resolving each of base-devel's dependencies on its own (`pacman -Sp --print-format '%n' <dep>`)
shows that only two of them drag `openssl 4` in: `pacman` (the package manager itself) and
`sudo`. Every other one — `archlinux-keyring autoconf automake binutils bison debugedit
fakeroot file findutils flex gawk gcc gettext grep groff gzip libtool m4 make patch pkgconf sed
texinfo which` — resolves without touching an installed package. So the bootstrap installs that
list instead (minus `pacman` and `sudo`: the guest has pacman, and its sudo is the broker
client), and the transaction really is "new packages only": the log shows `warning: binutils …
is up to date -- skipping` and the same for file, findutils, gawk, gettext, grep, libtool, sed
and which. **No system upgrade, ever**: the guest's Hyprland/aquamarine/Mesa in `/opt` are
pinned against the image's libraries. (Before that rule existed I did try one `pacman -Syu` in
the container, allowed by the parent for the container only; it died on mirror retrieval
errors and upgraded nothing — `pacman -Q openssl` still says `3.6.4-1`.)

**Finding 2 — the mirrors did not carry `flex-2.7.6-1`.** The synced `core` database lists
`flex 2.7.6-1`; `mirror.archlinuxarm.org` redirects to `va.us.mirror…` which 404s, and
`de/eu/dk/tw/sg/us` mirrors, `mirror.umd.edu`, `ftp.osuosl.org` and `mirror.rackspace.com` 404
it too (checked with `curl -r 0-100`). One failed transaction is the whole bootstrap failing
over a package the build does not need, so `install_pacman()` retries once with `--ignore` for
exactly the package names pacman reported as `failed retrieving file`, and prints which ones it
skipped. `flex` was the only casualty; `gcc`, `make`, `fakeroot` and `git` all installed, which
is why `cbonsai` could compile.

**Finding 3 — `sudo -k <command>` did nothing, and that silently broke every install.** makepkg
installs what it builds with `run_pacman -U` → `sudo -k pacman -U <pkg>` (makepkg line 242).
The round-6 client treated *any* `-k` as "reset the timestamp, exit 0", so makepkg printed
`==> Installing package yay-bin with pacman -U...` and returned success while nothing was
installed: `/usr/bin/yay` was missing, `pacman -Q yay-bin` empty, and `pacman.log` had no `-U`
line at all — the only visible symptom was the shim's own `pacman finished but /usr/bin/yay is
missing`. sudo's own meaning is "-k with a command: run the command, ignore the cached
credentials", so `-k` is now a no-op only when it stands alone; `sudo -k echo installed` is a
new selftest case (35/35). On a tablet this would have made every `yay -S` and every
`omarchy-pkg-aur-add` appear to succeed without installing anything.

**What this does NOT prove.** The two-proot setup on the phone (the shared `/tmp` bind, proot's
`SO_PEERCRED` rewriting, one real uid under both), Android's kernel under all of it (this ran on
the host's `7.2.15-1-omarchy`), that the real `fakeroot` fails in the guest with an IPC error
(that is inference from `CONFIG_SYSVIPC` and this project's own `shmget` ENOSYS measurement —
the container never ran the real one), the device's network and mirror set, what a *very* old
guest pacman database does (`pacman -Sy` is part of the bootstrap, which covers it), and every
ownership question (the container's root really is uid 0, proot's fake root is not).

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

PASS.

Built from a **separate worktree at `6834e6c`**, not from the round's checkout: a parallel session
was committing the dock work in that same checkout (`d1bd409`, `dbb3f71`) and had `app/src` edits
uncommitted at build time, so assembling the working tree would have baked half-finished,
uncommitted code into the APK Phil installs.

```
git worktree add --detach <scratch>/omarchy/r6/yay/build-tree 6834e6c
git submodule update --init --recursive
ln -s <repo>/app/src/main/assets/rootfs.bin    app/src/main/assets/rootfs.bin
ln -s <repo>/app/src/main/assets/bootstrap.bin app/src/main/assets/bootstrap.bin
cp <repo>/local.properties .
rm -f app/build/outputs/apk/debug/app-debug.apk
./gradlew :app:assembleDebug --console=plain
BUILD SUCCESSFUL in 1m 49s
134 actionable tasks: 134 executed
```

- APK: **1,715,756,194 bytes**, sha256
  **`7a42c3d1fdf0acf4e05f0b0cf147a4fdac7e45a33521b6d06f384cbc689028fc`**, tree `6834e6c`.
  Copy: `<scratch>/omarchy/r6/yay/omdroid-sudo-yay-test.apk` (same sha256).
- The overlay is really inside it (`unzip -l app-debug.apk | grep guest-overlay`):
  `fakeroot` 4,422 B, `yay` 8,886 B, `omdroid_root.py` 6,348 B, `sudo` 7,642 B,
  `start.sh` 6,913 B, `omdroid-rootd.py` 18,373 B — byte counts identical to the committed files.
  `GuestOverlay` walks the asset tree, so the three new files reach an existing install on the
  next cold start even though `rootfs.bin` was not repacked.
- `omdroid-0.0.15-alpha.apk` was already gone from the main checkout's
  `app/build/outputs/apk/debug/` when this step began (a parallel session's `assembleDebug`
  clears that directory; it had built at 12:54). Restored from the published release asset with
  `gh release download v0.0.15-alpha -p omdroid-0.0.15-alpha.apk`: sha256
  `c188e365…5032`, the value in the release notes, so the restored file is the published one.
- The APK also carries the dock work that was committed to `main` before `6834e6c`
  (`d1bd409`); that is expected — the parent asked for the combined test build.

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
- `docs/omarchy/launch-contract.md` section 7 gained one bullet naming the two extra clients of
  the same broker (`fakeroot`, `yay`). The host/guest interface itself is unchanged — same socket,
  same request format, same three-difference broker command — so this is documentation of the
  guest side, not a contract change.

## Y6. Report

PASS. The sections below are the deliverable: the manual test, the design as built, what still
fails, the commits and the APK.

## Manual test for Phil

This extends "Manual test for Phil" in `docs/omarchy/r6-sudo-report.md`; steps 1-10 there (install,
`sudo id`, pipes, pacman, the interactive prompt, Ctrl+C, `omarchy-pkg-add/remove`, ownership, the
broker log, broker death) still apply unchanged and are not repeated. These are the yay/makepkg
steps on top of them.

1. Install this build and cold start — the same three commands as sudo step 1, with
   `<scratch>/omarchy/r6/yay/omdroid-sudo-yay-test.apk`
   (sha256 `7a42c3d1fdf0acf4e05f0b0cf147a4fdac7e45a33521b6d06f384cbc689028fc`, ~1.7 GB).
   Must see `INSTALL: PASS` with that sha256 and `VERDICT: PASS` from `probe.sh -q`.
2. `fakeroot` resolves to the shim, not the package:
   ```
   command -v fakeroot     # /usr/local/bin/fakeroot
   fakeroot -v             # fakeroot version 1.37.2 (omdroid shim: fake root through the root broker)
   fakeroot -- id          # uid=0(root) gid=0(root) groups=0(root)
   ```
   If it says the root broker is not running, the second proot died: sudo step 10 has the log
   commands.
3. `yay --version` — **the first call bootstraps**, so let it run in a terminal and read the
   progress lines. Expected, in order: `yay: no AUR helper in this guest yet …`, then
   `yay: installing base-devel and git`, then today's expected twist
   `yay: base-devel here would upgrade the guest's pacman and sudo; installing the build tools
   directly, the guest's libraries stay as they are`, then ~85 MiB of downloads / ~450 MiB
   installed (several minutes on the tablet), `yay: fetching yay-bin from the AUR`,
   `yay: building and installing yay-bin`, and finally `yay v13.1.0 - libalpm v16.0.1`.
   The whole log is `~/.cache/omdroid/yay-bootstrap.log`. A second `yay --version` must return
   immediately — that is the proof the bootstrap did not re-run.
4. An AUR package that actually compiles:
   ```
   yay -S --noconfirm cbonsai    # one C file through gcc, then package() in the fakeroot shim
   cbonsai -p                    # draws a tree and exits
   yay -Qi cbonsai               # Name: cbonsai  Version: 1.4.2-1
   yay -R --noconfirm cbonsai
   pacman -Q cbonsai             # error: package 'cbonsai' was not found
   ```
   If `cbonsai -p` answers `ncurses: cannot initialize terminal type`, `TERM` is unset in that
   window — not a package problem.
5. Omarchy's own AUR scripts (this is the user-facing case):
   ```
   omarchy-pkg-aur-add cbonsai   # calls yay -S --noconfirm --needed
   omarchy-pkg-remove cbonsai
   ```
   No `yay: command not found`, no password prompt, and the package is there and then gone
   (`pacman -Q cbonsai`).
6. Where to look when it fails:
   - `~/.cache/omdroid/yay-bootstrap.log` — every step's output; the last line of a failed run
     names the step.
   - `tail -20 /tmp/omdroid-root/rootd.log` — one line per request, `<time> <argv[0]> exit=<code>`;
     `pacman` lines with `exit=0` around a `bash` line are the `makepkg -U` install.
   - `sudo pacman -Q gcc make fakeroot git` — did the build tools land? (all four must be there)
   - `ls -l /usr/bin/yay; command -v yay` — is the real binary installed, and is the shim first?
   - If the message says the guest image cannot install the build tools without a system upgrade,
     the repositories have moved past the image again: the bootstrap stops there on purpose and
     never upgrades the guest, whose Hyprland/aquamarine/Mesa are pinned builds.

## Design as built

From the outside, nothing changed for the user: `sudo`, `fakeroot` and `yay` are plain commands in
`/usr/local/bin`, all three links to `/etc/phoshdroid/…` that the image makes and `start.sh`
refreshes every session, and all three reach the broker ProotService already starts.

- `omdroid_root.py` is the client half of the broker protocol (request, frames, stdin pump, pty
  window size, raw mode, exit code) that `sudo` and `fakeroot` both import, so the wire format
  lives in one file.
- `fakeroot` sends its command to the broker as `root` with `keep_env: true`, the caller's cwd,
  the caller's stdio (pty when stdin is a tty) and `FAKEROOTKEY` set, which is exactly what
  makepkg's `-F` re-entry checks for. `-v` prints a fakeroot-shaped line, `-h` prints usage,
  `-s/-i` and the IPC-selection flags are refused by name rather than silently ignored.
- `yay` execs `/usr/bin/yay` once it exists; otherwise it takes a `flock`, syncs the databases,
  installs the build environment (the base-devel meta package, or its dependency list minus
  `pacman`/`sudo` when the meta package would upgrade the base system; skipping only packages
  some mirror cannot serve), clones `yay-bin` into `~/.cache/omdroid/`, runs `makepkg -si`, and
  execs the result. Every step is echoed and appended to one log, and a failure is one line plus
  that log's path.
- The guest's `sudo` fix: `-k` alone stays a no-op (`sudo -k` in a `.logout` file must not break),
  `-k <command>` runs the command, which is what makepkg does when it installs a built package.

## What still fails or is missing

- The real `/usr/bin/fakeroot` from `base-devel` is installed but unusable: run it directly
  (`/usr/bin/fakeroot ls`) and it should die on SysV IPC, because Android's kernel has
  `CONFIG_SYSVIPC` off. Not measured on a device; the shim is what makepkg calls, so nothing
  needs it.
- AUR packages that declare only `arch=('x86_64')` are refused; `yay --mflags --ignorearch` skips
  the check and then only works if the sources really build on aarch64.
- `yay -S` of anything that would need a base-system upgrade hits the same dependency conflict and
  stops; Omdroid does not upgrade the guest for you.
- `systemctl`, `mount` and everything else from the sudo report's "What still fails under sudo"
  is unchanged.

## Commits

- `5562ea5` feat(rootfs): fakeroot and yay shims on the fake-root broker
- `baf7b40` feat(rootfs): ship the fakeroot and yay shims and link them into PATH
- `ceb51dc` docs: yay and makepkg in the guest
- `6834e6c` fix(rootfs): run the command after sudo -k, and keep yay off a system upgrade
- the docs commit that carries this report's final sections

## Final APK

`7a42c3d1fdf0acf4e05f0b0cf147a4fdac7e45a33521b6d06f384cbc689028fc` (1,715,756,194 bytes), built
from tree `6834e6c`; copy at
`<scratch>/omarchy/r6/yay/omdroid-sudo-yay-test.apk`.
