# R6-SUDO report: fake root for the Omdroid guest through a broker

Worker session report. Brief: `docs/omarchy/brief-r6-sudo.md`. Scratch: `<scratch>/omarchy/r6/sudo/`.
Head at start: `cf872ed`.

## STATUS TABLE

| Step | What | Status |
|---|---|---|
| S0 | Premises on device: second proot `-0`, pacman, session survives | PENDING (Phil's manual test) |
| S1 | Broker + client + host-side harness | PASS (27/27 on the build machine) |
| S2 | Host side: `buildRootBrokerCommand` + `ProotService` + gate | PASS |
| S3 | Overlay plumbing (files, lists, start.sh, launch contract) | PASS |
| S4 | Build APK, sha256 | PASS |
| S5 | Device proof (all sudo paths) | PENDING (Phil's manual test) |
| S6 | README paragraph | PASS |
| S7 | Report + cleanup | PASS |

## S0. Premises

PENDING (Phil's manual test). The tablet was not on adb in this round (`adb devices` listed
nothing for `<tablet serial>`), and the parent's amendment moved every device step to a manual test on
the tablet. Manual steps: see "Manual test for Phil".

## S1. Broker + client

PASS.

- `rootfs/overlay/etc/phoshdroid/omdroid-rootd.py` — the fake-root broker. Runs as the program of
  a second proot (`-0`), listens on `/tmp/omdroid-root/sock` (dir 0700, socket 0600), one JSON
  line then framed channels per connection; a thread per connection so one install never blocks
  another `sudo`. Pipe mode streams stdin and keeps stdout/stderr apart; pty mode allocates a pty,
  sets the caller's window size, relays bytes both ways (Ctrl+C/Z travel as bytes) and resizes on
  `SIGWINCH`. Exit code 128+signal for a killed child. `-u <user>` runs the request with that
  user's uid/gid (`Popen(user=, group=)` — proot's fake_id0 emulates the setuid), its home as
  `HOME`. Whitelisted environment unless the client asks to keep it; `VAR=value` assignments from
  the client's command line are applied on top. Requests are logged one line each to
  `<socket dir>/rootd.log` (time, argv[0], exit code).
- `rootfs/overlay/etc/phoshdroid/sudo` — the client. `sudo cmd...`, `--`, `-n`, `-E`,
  `-u USER`, `-i`, `-s`, `-v`, `-k`, `-l`, `-h`, `-V`, `VAR=value cmd`; unknown option → sudo's
  usage text and exit 1; no command → usage and exit 1. No password ever. When stdin is a tty it
  sets raw mode on the caller's terminal and restores it on every exit path; when it is not, it
  streams stdin and keeps stdout/stderr separate. Broker absent → one line on stderr and exit 1
  (measured 0.02 s).
- `docs/omarchy/tools/rootd-selftest.py` — host harness: broker and client as the current user,
  no proot, no guest.

Harness result on this machine (`python3 docs/omarchy/tools/rootd-selftest.py`):

```
PASS argv_passthrough, cwd_is_the_callers, stdin_is_streamed, tee_writes_the_file,
     stdout_and_stderr_stay_apart, exit_code_passes_through, false_returns_one,
     signal_exit_is_128_plus_signal, missing_command_is_127, pty_reads_a_line,
     pty_window_size, pty_ctrl_c_kills_the_child, noninteractive_flag,
     preserve_env_flag, run_as_another_user, unknown_user_fails,
     login_shell_runs_root_shell, plain_shell_runs_shell,
     validate_and_reset_are_noops, list_says_everything_is_allowed,
     help_and_version, double_dash_ends_options, unknown_flag_is_a_usage_error,
     assignment_before_the_command, no_command_is_a_usage_error, concurrent_requests,
     broker_absent_fails_fast
27/27 passed
```

The pty cases run the client with its stdin on a real pty: `read x` answered through the broker's
pty, `stty size` answering `40 100`, and Ctrl+C on `sleep 100` exiting 130 in 0.5 s. The
concurrency case holds a `sleep 1.5` request in flight while a second `sudo echo` returns in
0.03 s.

## S2. Host side

PASS.

- `ProotCommandBuilder.buildRootBrokerCommand()` sits next to `buildLoginCommand()` and both go
  through one private `buildCommand(identityArgs, workDir, program, bindSdcard)`, so the only
  differences are exactly the documented three: `-0` for `-i 1000:1000`, `-w /root` for
  `-w /home/omarchy`, and `/usr/bin/python3 /etc/phoshdroid/omdroid-rootd.py` for
  `/bin/bash /etc/phoshdroid/start.sh`. The shared `$prefix/tmp:/tmp` bind is what puts the
  broker's socket where the session's `sudo` can reach it. `BROKER_SCRIPT` is a constant on the
  class so the name lives in one place.
- `ProotService`: `startBroker()` runs before `startProot()` in `startSession()`, with the same
  environment the session gets (so `PROOT_LOADER`, `LD_LIBRARY_PATH` and `PROOT_TMP_DIR` are the
  session's), and logs `session: root-broker started`. A `RootBrokerMonitor` thread drains its
  output, logs `session: root-broker exited <code>: <output>` and mirrors it to
  `<prefix>/tmp/root-broker.log`. `stopSession()` (and so `onDestroy`) destroys it and logs
  `session: root-broker stopped`. A broker that fails to start or dies later only logs: nothing
  in the session's lifecycle depends on it.
- `RootBrokerCommandTest` (6 cases): the broker command equals the login command after exactly
  the three substitutions, carries `-0` and never `-i`/`1000:1000`, shares `/prefix/tmp:/tmp`,
  keeps the same rootfs and fake-proc shadows, follows the sdcard bind, and the login command
  still runs the session script as uid 1000.

Gate (`./gradlew :app:compileDebugKotlin :app:test :app:lintDebug --console=plain`):
`BUILD SUCCESSFUL in 13s`; `python3 docs/omarchy/tools/unit-count.py` -> `unit tests 69 failed 0`
(was 63 before this round).

## S3. Overlay plumbing

PASS.

- `app/build.gradle.kts` `syncGuestOverlay`: `include("omdroid-rootd.py", "sudo")`, so both files
  reach the APK's `assets/guest-overlay/etc/phoshdroid/` and `GuestOverlay` re-syncs them into an
  existing install on the next cold start. (`GuestOverlay` marks `.py` files 755; `sudo` has no
  suffix, which is why `start.sh` chmods it — see below.)
- `rootfs/package-omarchy-rootfs.sh` overlay block: copies both files, adds them to the
  `chmod 755` list, and creates `/usr/local/bin/sudo -> /etc/phoshdroid/sudo` at image time, next
  to the omamobile helper links.
- `rootfs/overlay/etc/phoshdroid/start.sh`: `chmod 755 /etc/phoshdroid/sudo` then
  `ln -sfn /etc/phoshdroid/sudo /usr/local/bin/sudo` before the session starts, so an updated
  install whose overlay sync only rewrote `/etc/phoshdroid` still gets the command. No
  apostrophes in the added comments. `bash -n` on both scripts: SYNTAX_OK.
- `docs/omarchy/launch-contract.md`: section 5 step 2 now names the second proot, and the new
  section 7 is the interface: the host starts the broker proot, the socket path and modes, the
  request log, the guest link, and that it is fake root with no real privilege and no systemd.

## S4. Build

PASS.

```
rm -f app/build/outputs/apk/debug/app-debug.apk
./gradlew :app:assembleDebug --console=plain
BUILD SUCCESSFUL in 21s
```

- `app/build/outputs/apk/debug/app-debug.apk`: 1,715,714,706 bytes, sha256
  `f7d2db15cf871a539942b328115f31dd408cb1219e1f8443eb25de2f957be6e1`, built from the tree of
  commit `4528cc3` (the build ran just before that commit landed; no file changed in between).
- The overlay really is inside it: `unzip -l app-debug.apk | grep guest-overlay` lists
  `assets/guest-overlay/etc/phoshdroid/omdroid-rootd.py` (17,726 B), `.../sudo` (12,176 B) and
  `.../start.sh` (6,374 B).
- Copy for Phil: `<scratch>/omarchy/r6/sudo/omdroid-sudo-test.apk`, same sha256.
- `assembleDebug` clears `app/build/outputs/apk/debug/`, and the release's local copy
  `omdroid-0.0.15-alpha.apk` sat in that directory. It was restored from the published asset
  (`gh release download v0.0.15-alpha`): 1,715,700,378 bytes, sha256
  `c188e3657282c99797de65a7f1287121bc5bbde74484a3d7e40996d392995032`, which is the sha256 in the
  release notes, so the restored file is byte-identical to the published one.

## S5. Device proof

PENDING (Phil's manual test). The tablet was not on adb this round (`adb devices` listed nothing
for `<tablet serial>`), and the parent's amendment moved every device step to a manual test. Each item
of the original list is a step in "Manual test for Phil" below, in the same order; nothing in
that list has been run on a device.

Two premises the harness cannot cover, both caught by manual step 2:

- `sudo id` assumes the broker proot itself starts: `-0` on the same rootfs, `-w /root` (0750,
  root-owned — enterable only as fake root), and `/usr/bin/python3` present (the image has
  python3.14). If any of those fails, the desktop still runs and `sudo` answers with its one-line
  error; `session: root-broker exited <code>` in logcat names the failure.
- `sudo -u omarchy` assumes proot's fake_id0 emulates `setuid`/`setgid` for the child
  (`Popen(user=, group=)`). Plain `sudo` never calls setuid — the broker already has fake id 0, so
  the code passes no ids when they equal `os.getuid()` — so only this path depends on it. If it
  is refused, `sudo -u omarchy id` fails cleanly with `sudo: id: Permission denied` (exit 126).

## S6. README

PASS.

- `Known limits`: a `sudo` paragraph — it exists, never asks for a password, is fake root inside
  the app's sandbox with no real privilege, the desktop stays uid 1000 so written files read as
  `omarchy`, and `systemctl` still fails.
- `Not verified yet`: a `sudo` bullet — the 27-case host harness passes, but no tablet has run
  `sudo id`, a pacman install, the interactive prompt or `omarchy-pkg-add`; it points at this
  report for the closing steps.

## S7. Report + cleanup

PASS. No session was started this round, so nothing of mine is running; no test windows were
opened; the repo tree is clean apart from the parent's amended brief
(`docs/omarchy/brief-r6-sudo.md`, not mine to commit). The runnable artefact for the manual test
is the scratch APK named in S4.

## Design

Two proots of the same guest, one socket between them.

**Host.** `ProotService.startSession()` starts the broker before the desktop:
`buildRootBrokerCommand()` = the login command with `-0` for `-i 1000:1000`, `-w /root` and
`/usr/bin/python3 /etc/phoshdroid/omdroid-rootd.py` as the program, same rootfs and binds, same
`--kill-on-exit`, same environment (`PROOT_LOADER`, `LD_LIBRARY_PATH`, `PROOT_TMP_DIR`). A monitor
thread logs `session: root-broker started` / `session: root-broker exited <code>` and mirrors the
output to `<prefix>/tmp/root-broker.log`; `stopSession()` destroys it. Nothing in the session's
lifecycle depends on it: a broker that cannot start, or dies, is a log line.

**Socket.** `/tmp/omdroid-root/sock` inside the guest. Both proots bind `<prefix>/tmp` as `/tmp`,
so the client in the session and the broker in the root proot see the same file. Directory 0700,
socket 0600; `SO_PEERCRED` must name this app's uid. One request per connection, a thread per
connection, so a long `pacman -S` never blocks another `sudo`. One line per request in
`/tmp/omdroid-root/rootd.log`.

**Protocol.** One JSON line (`argv`, `cwd`, `env`, `env_extra`, `user`, `tty`, `keep_env`), then
frames `">BI"` channel+length: 0 stdin, 1 stdout, 2 stderr, 3 exit code, 4 window size,
5 error text. Pipe mode streams stdin and keeps stdout/stderr apart; pty mode allocates a pty,
sets the caller's window size, relays bytes both ways (Ctrl+C/Z travel as bytes and the pty's
line discipline turns them into signals; when proot refuses `setsid` the broker signals the child
itself), and resizes on `SIGWINCH`. Exit code is `128+signal` when the child was killed.

**Guest.** `/etc/phoshdroid/sudo` is linked to `/usr/local/bin/sudo` at image time and again by
`start.sh` every session (the overlay sync only chmods `.sh`/`.py`, so start.sh chmods this one).
It parses sudo's options, builds the default environment (`HOME=/root`, `USER=LOGNAME=root`,
`SUDO_USER`, `SUDO_UID`, `SUDO_GID`, `SUDO_COMMAND`, the session's `PATH`, `TERM`, `LANG`,
`WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, `DISPLAY`), puts its own terminal in raw mode when stdin is
a tty, and prints one line and exits 1 when the broker is not there.

**Why the desktop keeps uid 1000.** With `-0` on the session, every file the desktop wrote would
read as root and tools that check ownership (git's safe.directory, ssh's key permissions, apps
that refuse to run as root) would break. Fake root only where a script asked for it.

## Manual test for Phil

Install the scratch APK, then run these in a foot window. 1 is on the build machine; 2-10 are in
the guest.

1. Install, cold start, size probe:
   ```bash
   cd ~/Development/personal/proot-post
   export TABLET_SERIAL=<tablet serial>
   docs/omarchy/tools/install.sh <scratch>/omarchy/r6/sudo/omdroid-sudo-test.apk
   docs/omarchy/tools/coldstart.sh 1
   docs/omarchy/tools/probe.sh -q
   ```
   Must see `INSTALL: PASS` with sha256 `f7d2db15...`, the mobile desktop, `VERDICT: PASS`.
2. Identity, no password:
   ```
   sudo id                # uid=0(root) gid=0(root) groups=0(root)
   sudo -u omarchy id     # uid=1000(omarchy) gid=1000(omarchy)
   sudo false; echo $?    # 1
   ```
   No password prompt anywhere. If `sudo id` prints the one-line "root broker is not running"
   error, the broker proot did not start: see the log commands below.
3. Pipes and separate streams:
   ```
   echo hi | sudo tee /etc/omdroid-sudo-test
   cat /etc/omdroid-sudo-test        # hi
   sudo rm /etc/omdroid-sudo-test
   ls /etc/omdroid-sudo-test         # No such file or directory  (this is the pass)
   ```
4. pacman through fake root:
   ```
   sudo pacman -Sy
   sudo pacman -S --noconfirm sl && sl -h
   sudo pacman -R --noconfirm sl
   ```
   Sync without a lock error, `sl -h` prints usage, `sl` removed. This also proves the second
   proot `-0` can run pacman at all.
5. The interactive prompt through the pty: `sudo pacman -S sl`, answer `n` and Enter at
   `Proceed with installation? [Y/n]`. Your `n` must be echoed once, the transaction must abort,
   and the prompt must come back — that is the pty path from a real terminal.
6. Ctrl+C: `sudo sleep 100`, then Ctrl+C. The prompt comes back at once (exit 130) and typing
   still echoes (the terminal is restored).
7. Omarchy's own scripts:
   ```
   omarchy-pkg-add sl
   omarchy-pkg-remove sl
   ```
   Both succeed, no `sudo: command not found`.
8. Ownership: `sudo touch ~/from-root; ls -l ~/from-root` must read `omarchy omarchy`, never
   `root root`.
9. Broker log: `tail -5 /tmp/omdroid-root/rootd.log` — one line per request above,
   `<time> <argv[0]> exit=<code>`.
10. Broker death and recovery: `ps -eo pid,args | grep [o]mdroid-rootd` for the PID, `kill <pid>`,
    then `sudo id` must print exactly
    `sudo: the root broker is not running (start the Omdroid session)` and exit 1 while the
    desktop keeps working (`probe.sh -q` still PASS). Restart the session (`coldstart.sh 1`) and
    `sudo id` must be root again.

If something fails, in this order: `adb -s $TABLET_SERIAL logcat -d -s ProotService:* | grep
root-broker` (host: started / exited), `adb -s $TABLET_SERIAL shell run-as com.phoshdroid.app cat
files/usr/tmp/root-broker.log` (the broker's own output), `... cat
files/usr/tmp/omdroid-root/rootd.log` (the request log), and `sudo -i` if you need a root shell
to look around.

## What still fails under sudo

- `systemctl ...` — no systemd in the guest. Expected message (not measured this round):
  `System has not been booted with systemd as init system (PID 1). Can't operate.` Fake root does
  not create a PID 1, so every Omarchy script that calls `systemctl` keeps failing.
- Anything that needs a real kernel capability or a real root uid from Android's point of view:
  `mount`, opening `/sys/devices` (Android denies it to the app — `sudo btop` aborts exactly as
  it does without sudo), changing a file's owner to a real uid, hostname changes.
- `su`, `run0`, `pkexec` remain unusable; the sudo client is the only root path.
- setuid binaries in the guest still do not work under proot; `sudo` never uses setuid.

## Commits

- `d9b9e61` feat(rootfs): fake-root broker and sudo client for the guest
- `83d9e25` feat(proot): start a fake-root broker proot with the session
- `7e0960b` feat(rootfs): ship the sudo client and link it into PATH
- `4528cc3` fix(rootfs): retry the broker pty without a controlling terminal
- the docs commit that carries this report (README S6 + this report)

## Final APK sha256

`f7d2db15cf871a539942b328115f31dd408cb1219e1f8443eb25de2f957be6e1` (1,715,714,706 bytes), built
from the tree of `4528cc3`; copy at
`<scratch>/omarchy/r6/sudo/omdroid-sudo-test.apk`.
