# Brief R6-SUDO: give Omdroid's guest a working `sudo` (fake root through a broker)

You are the WORKER for this brief. Do the work yourself in this session: never create agents,
never call `delegate_task`.

Repo: `<repo>` (branch `main`, read `AGENTS.md` first, then
`docs/omarchy/launch-contract.md`). Report, created in your FIRST calls and updated after every
step: `docs/omarchy/r6-sudo-report.md` (STATUS TABLE S0-S7, `PENDING` until proven).
Scratch: `<scratch>/omarchy/r6/sudo/`.

## The problem (Phil, the owner)

"Sudo command not found." In the Omdroid guest terminal `sudo` does not exist: the image has no
`sudo` package (only `su`, `run0`, `pkexec`, none of which work here), and the session runs under
proot as uid 1000 (`ProotCommandBuilder.kt`: `-i 1000:1000`; read the class), so nothing in the
guest can become root. 70 of Omarchy's 441 scripts in `/usr/share/omarchy/bin` call `sudo`
(`omarchy-pkg-add`, `omarchy-pkg-remove`, `omarchy-refresh-pacman`, timezone, ...): the most
common uses are `sudo pacman`, `sudo tee`, `sudo sed`, `sudo rm`, `sudo cp`, `sudo mkdir`,
`sudo env`, `sudo -n`, and `sudo systemctl` (systemd is absent; that one may keep failing).
`/etc/pacman.conf` in the guest is already set up for proot (`DisableSandboxSyscalls`,
`DisableSandboxFilesystem`, `DownloadUser = root`), so pacman works as fake root.

## The design (decided by the parent; verify its premises in S0 before building)

Fake root is harmless here: everything runs as the Android app's own uid inside its private
storage, so "root" in the guest grants no real privilege. Keep the desktop session exactly as it
is (`-i 1000:1000`; with `-0` files would appear root-owned to the user, which breaks git, ssh and
apps that check ownership). Add a **root broker**:

1. **Host**: when the session starts, `ProotService` also starts a second proot on the same
   rootfs with the same binds but `-0` instead of `-i 1000:1000`, running a small broker
   (`/etc/phoshdroid/omdroid-rootd.py`); it stops with the session (same lifecycle, same
   `--kill-on-exit`). `ProotCommandBuilder` gets a pure `buildRootBrokerCommand(...)` next to
   `buildLoginCommand`, with unit tests (args equal the login command except `-0` for
   `-i 1000:1000`, `-w /root`, and the broker as the program). Log `session: root-broker started`
   / `exited <code>`. A broker death must never end or fail the desktop session.
2. **Guest broker** (Python 3, stdlib only): listens on a Unix socket that both proot instances
   see (under the shared `/tmp`, e.g. `/tmp/omdroid-root/sock`, directory mode 0700), runs each
   request as fake root with the client's argv, cwd, a filtered environment, and either a pty
   (when the client's stdin is a tty: relay bytes both ways, window size and resizes, Ctrl+C/Z as
   bytes) or plain pipes (stdin streamed, stdout/stderr kept separate), and returns the exit code
   (128+signal for a signal). One request per connection, concurrent requests allowed.
3. **Guest client** `/etc/phoshdroid/sudo` (Python, stdlib), installed as `/usr/local/bin/sudo`
   (a symlink made at image time by the packager AND at session start, so updated installs get
   it): supports `sudo cmd...`, `--`, `-n` (never prompts anyway), `-E` (keep env), `-u root`,
   `-u <user>` (run as that user via `setpriv`/`runuser` inside the broker, which fake_id0
   emulates; verify), `-i` and `-s` (root shell), `-v`/`-k` (no-ops, exit 0), `-l` (print that
   everything is allowed), `-h`, `-V`; an unknown flag is an error with sudo's usage text. No
   password, ever. If the broker is not running: a clear one-line error and exit 1, never a hang.
   Environment by default: `HOME=/root`, `USER=LOGNAME=root`, `SUDO_USER`, `SUDO_UID`,
   `SUDO_GID`, `SUDO_COMMAND`, the session's `PATH`, `TERM`, `LANG`, `WAYLAND_DISPLAY`,
   `XDG_RUNTIME_DIR`, `DISPLAY`.
   Do not install the real `sudo` package (setuid does not work under proot).
4. **Overlay plumbing**: the two new files live in `rootfs/overlay/etc/phoshdroid/`; add them to
   `syncGuestOverlay` (`app/build.gradle.kts`) and the packager's "Applying overlay" block
   (`rootfs/package-omarchy-rootfs.sh`), which must list the same files (`AGENTS.md`); the
   session-start link goes in `start.sh` (one line, no apostrophes in comments, `bash -n` after).
   Update `docs/omarchy/launch-contract.md` in the same round (the host now starts a second guest
   process and the guest relies on it).

## Steps

**S0. Premises, on the device.** `export TABLET_SERIAL=<tablet serial>` (never write the serial into a
repo file). If `adb devices` does not list it, do S1-S4 first, then wait with bounded checks
(`timeout 380 bash -c 'until adb devices | grep -q "<tablet serial>.device"; do sleep 10; done'`, at
most 4 times) and write `BLOCKED (tablet not connected)` if it never appears. Keyguard rule: never
enter a PIN; `BLOCKED (keyguard)` and bounded waits. Record `stay_on_while_plugged_in`, set `2`,
restore and read back at the end. Then prove by hand, with the live session running, that a
second proot `-0` on the same rootfs (built from the same args the app uses: read the running
proot's cmdline under `/proc` via `run-as com.phoshdroid.app`) can run `id` (uid 0),
`pacman -Sy` and a small `pacman -S --noconfirm` + `pacman -R --noconfirm` (pick a tiny package,
e.g. `sl`), while the desktop keeps running (`probe.sh -q` PASS before and after). If a premise
fails, write it down with the evidence and adapt the design; tell the parent in your final reply.

**S1. Broker + client.** Write both, plus a host-side test harness that runs them on this
machine (x86 Python, no proot: broker as the current user, client against it) covering argv,
cwd, stdin piping (`echo x | sudo tee f`), separate stdout/stderr, exit codes, a signal exit,
the pty path (`script`/`pty`-driven: a program that reads a line from the tty), window size,
`-n -E -u -i -s -v -k -l -h -V --`, unknown flag, broker absent (error within 2 s). Commit.

**S2. Host side.** `ProotCommandBuilder.buildRootBrokerCommand` + tests, `ProotService`
start/stop + log lines. Gate:
`./gradlew :app:compileDebugKotlin :app:test :app:lintDebug --console=plain` (foreground) and
`python3 docs/omarchy/tools/unit-count.py` (expect more than `unit tests 63 failed 0`). Commit.

**S3. Overlay plumbing** (files, lists, `start.sh`, launch contract). `bash -n`. Commit.

**S4. Build.** `rm -f app/build/outputs/apk/debug/app-debug.apk && ./gradlew :app:assembleDebug
--console=plain` (foreground, 600 s timeout, never in the background). Record the sha256.

**S5. Device proof** (install with `docs/omarchy/tools/install.sh <apk>`, cold start with
`coldstart.sh 1`, `probe.sh -q` PASS), each with output in the report, run inside the session
(`docs/omarchy/tools/sx.sh` or a foot window): `sudo id`; `sudo -u omarchy id`; `sudo pacman -Sy`;
`sudo pacman -S --noconfirm sl && sl -h; sudo pacman -R --noconfirm sl`; `echo hi | sudo tee
/etc/omdroid-sudo-test && cat /etc/omdroid-sudo-test && sudo rm /etc/omdroid-sudo-test`;
`sudo false; echo $?` (1); an interactive `sudo pacman -S sl` answered `n` through the tty;
Ctrl+C on `sudo sleep 100`; `omarchy-pkg-add sl` and `omarchy-pkg-remove sl` (Omarchy's own
scripts); the file a fake-root command creates in `$HOME` shows owner `omarchy` to the user
session; the desktop still passes `probe.sh -q`; after killing the broker by exact PID, `sudo id`
fails with the one-line error and the desktop is unaffected; a session restart (cold start) brings
the broker back.

**S6. README.** One short paragraph (How it works or Known limits): `sudo` exists, has no
password, is fake root inside the app's sandbox with no real privilege, and `systemctl` still does
not work (no systemd). Add `sudo` to the "Not verified yet" list only for what S5 did not prove.

**S7. Report + clean up.** STATUS TABLE, a section per step with commands and output, "Design"
(what runs where, the socket, the lifecycle), "What still fails under sudo" (with the measured
error for each, e.g. `systemctl`), commits, the final APK sha256. Leave the session running in
mobile mode, no test windows, stay-awake restored, `probe.sh -q` PASS.

## Hard rules

- Files you may change: `app/src/main/kotlin/com/phoshdroid/app/proot/{ProotCommandBuilder,ProotService}.kt`
  and their tests (add new test files in the same package), `app/build.gradle.kts`
  (`syncGuestOverlay` only), `rootfs/package-omarchy-rootfs.sh` (overlay block only),
  `rootfs/overlay/etc/phoshdroid/{start.sh,omdroid-rootd.py,sudo}`,
  `docs/omarchy/launch-contract.md`, `README.md` (S6 only), `docs/omarchy/tools/**` (new tools),
  your report. Nothing else.
- **Commit each finished step at once** with exactly its paths (`git add <paths> && git commit`,
  conventional messages: `feat(proot): ...`, `feat(rootfs): ...`, `docs: ...`); never
  `git add -A`. No `git push`, no tag, no release, no GitHub writes.
- Never `pkill -f`; kill only PIDs you started, by exact PID. No `sleep N; tail` poll loops.
- If a command waits on an approval, do not retry or rephrase it; note it and go on.
- If your call budget runs low, write the report state and commit before anything else.

Final reply, at most 10 lines: S0-S7 with the decisive fact each, what still fails under sudo,
the commits, the final APK sha256.
