# Brief R6b-YAY: `yay` and `makepkg` in the Omdroid guest (on top of the sudo broker)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`. No device in this round (Phil tests the build by hand).

Repo: `<repo>` (branch `main`, read `AGENTS.md`). Read first,
whole: `docs/omarchy/r6-sudo-report.md` (the fake-root broker and the `sudo` client built in the
previous round, untested on a device), `rootfs/overlay/etc/phoshdroid/{sudo,omdroid-rootd.py,start.sh}`,
`docs/omarchy/tools/rootd-selftest.py`.
Report, created in your FIRST calls and updated after every step: `docs/omarchy/r6b-yay-report.md`
(STATUS TABLE Y0-Y6). Scratch: `<scratch>/omarchy/r6/yay/`.

## The problem (Phil): "yay command not found when trying to install deps"

Facts the parent checked (verify the ones you rely on):
- The guest image has `makepkg` and `git` and `binutils`, but no `yay`/`paru`, no `fakeroot`,
  no `gcc`/`make` (no `base-devel`). 5 Omarchy scripts call `yay`
  (`omarchy-pkg-aur-add`, `omarchy-pkg-aur-install`, `omarchy-pkg-remove`,
  `omarchy-update-aur-pkgs`, `omarchy-upgrade-to-quattro`).
- Arch Linux ARM's repos (`core`, `extra`, `alarm`, `aur` in the guest's `pacman.conf`) carry
  `base-devel` and `fakeroot` (core) but no `yay` or `paru`. The AUR package `yay-bin` ships
  aarch64 binaries (verify in its PKGBUILD).
- `makepkg` refuses to run as root and runs `package()` under `fakeroot`. Arch's `fakeroot` uses
  SysV IPC, which Android kernels normally lack (verify what you can: Arch's fakeroot build
  options; Android's kernel config requirements for SysV IPC), so a stock `fakeroot` is expected to
  fail in the guest with an IPC error.
- The guest already has a fake-root broker (a second proot `-0`) and a `sudo` client that talks to
  it (previous round). Fake root is harmless here (everything is the app's own uid).

## The design (decided by the parent)

1. **`fakeroot` shim** `rootfs/overlay/etc/phoshdroid/fakeroot` (Python, stdlib), linked as
   `/usr/local/bin/fakeroot` (it must win over `/usr/bin/fakeroot` if the package gets
   installed): runs its command through the broker as fake root with the FULL environment, the
   cwd and the stdio passed through (reuse the `sudo` client's code; factor shared code into a
   small module both import, e.g. `/etc/phoshdroid/omdroid_root.py`, rather than copy). Support
   what `makepkg` uses (`fakeroot -- cmd...`, `fakeroot -v`/`--version`; read `makepkg` in the
   guest image or Arch's pacman source for every call it makes and any `FAKEROOTKEY` / environment
   checks it does) and say in the report what is not supported.
2. **`yay` bootstrap shim** `rootfs/overlay/etc/phoshdroid/yay`, linked as `/usr/local/bin/yay`:
   if `/usr/bin/yay` exists, `exec` it with the same args. Otherwise, once, with clear progress
   lines: `sudo pacman -S --needed --noconfirm base-devel git`, clone
   `https://aur.archlinux.org/yay-bin.git` into a temp dir as the user, `makepkg -si --noconfirm`
   (which uses the fakeroot shim and `sudo pacman -U`), then `exec /usr/bin/yay "$@"`. On any
   failure: a one-line reason, where the log is, exit non-zero, nothing half-installed left on PATH.
   Note: `/usr/local/bin` comes before `/usr/bin` in the session PATH (`ProotCommandBuilder`).
3. Both links are made at image time by the packager AND at session start in `start.sh` (same
   pattern as `sudo`, no apostrophes in its comments, `bash -n` after); both files are added to
   `syncGuestOverlay` (`app/build.gradle.kts`) and the packager overlay block, which must list the
   same files.
4. Many AUR packages declare `arch=('x86_64')` only. Do not hide that; document `yay --mflags
   --ignorearch` in the README paragraph as the escape hatch, with the warning that it only works
   for packages whose sources build on aarch64.

## Steps

**Y0. Premises.** Verify the facts above you rely on (yay-bin aarch64 source, makepkg's fakeroot
calls, fakeroot's IPC mode), with sources. Write them in the report.

**Y1. Code.** Shared module, the refactored `sudo`, `fakeroot` shim, `yay` shim. Extend
`docs/omarchy/tools/rootd-selftest.py` (it must still pass all its old cases) with fakeroot
cases: full env passed, cwd, exit code, stdin, `fakeroot -v`. Commit.

**Y2. End-to-end on aarch64 without the device.** The machine has qemu-user binfmt and the docker
image `omdroid-guest:0.0.14` (the guest image itself, arm64). proot cannot run under qemu-user,
so simulate the two proots: in an arm64 container of that image (name it `omdroid-yay-test`),
run the broker as the container's root and the client side as a normal user `omarchy` (uid 1000,
create it if needed) with the same `/tmp` socket path, the session PATH and the overlay files
copied to `/etc/phoshdroid/` with the links in `/usr/local/bin`. Then, as `omarchy`: `sudo id`,
`sudo pacman -Sy`, `yay --version` (the bootstrap: base-devel, yay-bin build, install), then
`yay -S --noconfirm <a small AUR package that builds on aarch64, pick one and say why>`, run it,
`yay -R --noconfirm` it. Expect qemu to be slow: run long steps detached (`docker exec -d` plus a
log file) and read the log between other work; never a foreground call over 400 s. Paste the
outputs. Remove the container by name at the end (`docker rm -f omdroid-yay-test`), keep the image.
State clearly what this does NOT prove (the two-proot setup on the phone, Android's lack of SysV
IPC, the device kernel).

**Y3. Host gate.** `./gradlew :app:compileDebugKotlin :app:test :app:lintDebug --console=plain`
(foreground) and `python3 docs/omarchy/tools/unit-count.py` (expect `unit tests 69 failed 0`).
Commit the plumbing.

**Y4. Build.** `rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug
--console=plain` (foreground, 600 s timeout). Copy the APK to
`<scratch>/omarchy/r6/yay/omdroid-sudo-yay-test.apk`, record sha256 and the commit.
Do not touch `app/build/outputs/apk/debug/omdroid-0.0.15-alpha.apk`; if `assembleDebug` removes
it, restore it from the published release asset (sha256 must be `c188e365…5032`) as the previous
round did.

**Y5. README.** Extend the previous round's sudo paragraph: `yay` installs itself on first use
(what it installs, roughly how long, the `--ignorearch` note), `makepkg` works through the
fakeroot shim. Under "Not verified yet": everything Y2 could not prove.

**Y6. Report** with a "Manual test for Phil" section that EXTENDS the sudo one in
`docs/omarchy/r6-sudo-report.md` (do not repeat it; reference it) with 5-7 steps: `yay --version`
(first run bootstraps; what he must see), `yay -S` of the package you chose, run it, remove it,
`omarchy-pkg-aur-add <pkg>`, and where to look when it fails.

## Hard rules

- Files you may change: `rootfs/overlay/etc/phoshdroid/{sudo,fakeroot,yay,omdroid_root.py,omdroid-rootd.py,start.sh}`
  (only what the design needs in the last two), `app/build.gradle.kts` (`syncGuestOverlay` only),
  `rootfs/package-omarchy-rootfs.sh` (overlay block only), `docs/omarchy/tools/rootd-selftest.py`,
  `README.md` (Y5 only), `docs/omarchy/launch-contract.md` (only if the guest contract changes),
  your report. Nothing in `app/src/**`.
- **Commit each finished step at once** with exactly its paths; never `git add -A`. No push, tag,
  release or GitHub writes. Docker: only containers named `omdroid-yay-test`; never `prune`.
- Never `pkill -f`; kill only PIDs you started, by exact PID. No `sleep N; tail` poll loops.
- If a command waits on an approval, do not retry or rephrase it; note it and go on.
- If your call budget runs low, write the report state and commit before anything else.

Final reply, at most 8 lines: Y0-Y6 with the decisive fact each, the AUR package used, what Y2
did not prove, the commits, the APK path and sha256.
