# R6-SUDO report: fake root for the Omdroid guest through a broker

Worker session report. Brief: `docs/omarchy/brief-r6-sudo.md`. Scratch: `<scratch>/omarchy/r6/sudo/`.
Head at start: `cf872ed`.

## STATUS TABLE

| Step | What | Status |
|---|---|---|
| S0 | Premises on device: second proot `-0`, pacman, session survives | PENDING (Phil's manual test) |
| S1 | Broker + client + host-side harness | PASS (27/27 on the build machine) |
| S2 | Host side: `buildRootBrokerCommand` + `ProotService` + gate | PASS |
| S3 | Overlay plumbing (files, lists, start.sh, launch contract) | PENDING |
| S4 | Build APK, sha256 | PENDING |
| S5 | Device proof (all sudo paths) | PENDING (Phil's manual test) |
| S6 | README paragraph | PENDING |
| S7 | Report + cleanup | PENDING |

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

PENDING

## S4. Build

PENDING

## S5. Device proof

PENDING

## S6. README

PENDING

## S7. Cleanup

PENDING

## Design

TBD after S0.

## What still fails under sudo

TBD.

## Commits

TBD.

## Final APK sha256

TBD.
