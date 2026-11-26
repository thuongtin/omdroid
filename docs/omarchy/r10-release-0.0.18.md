# Omdroid 0.0.18-alpha release

The 0.0.17 desktop rebuilt without the build machine's file paths, after a full scrub of the
repository and its forks. No guest change: `etc/phoshdroid` is byte-identical to 0.0.17.

## What changed

- `termux-x11/app/src/main/cpp/CMakeLists.txt`: `-ffile-prefix-map` for the source and build
  directories, so `assert()` and the BUG/log macros in `libXlorie.so` record relative names
  (`xserver/dix/devices.c`) instead of absolute ones. Every earlier APK carried 18 absolute
  paths per ABI; this one has 0 in all four ABIs (`strings -a`, checked per ABI).
- History: the main repository and the two submodule forks were rewritten with
  `git filter-repo` to remove personal data (a device serial, a private address, build-machine
  paths, a mail address) from file contents, commit messages and tag annotations, and to set
  every author and tagger to the GitHub noreply address. In the forks only our own commits were
  rewritten; upstream history is untouched. Commit ids before this release changed.
- The APKs of releases 0.0.13 to 0.0.17 are withdrawn (their notes stay): each embedded the
  build path above.

## Verified on the tablet

| Item | Result |
| --- | --- |
| Install over 0.0.17 | sha256 `6ce57d0e…f06d1a`, `versionName=0.0.18-alpha`, `install.sh` PASS |
| Cold start, unaided | hand-over 8.7 s, desktop drawn 8.1 s, no relaunch |
| `probe.sh -q` | PASS |
| Build machine paths in the APK | 0 in `libXlorie.so` for arm64-v8a, armeabi-v7a, x86, x86_64; 0 in every entry except the two image assets |

Unit tests 138, 0 failed. Lint: 0 errors, 32 warnings (lint does not fail the build here,
`abortOnError = false`, so the count comes from `lint-results-debug.xml`).

APK: `omdroid-0.0.18-alpha.apk`, 1,715,790,990 bytes, sha256
`6ce57d0ed013bd6e8ddb2f397ceb7646619bb591cdc0c1e963fa7900ccf06d1a`.

## Limits of the scrub

- GitHub keeps serving the old commits by id until GitHub Support purges them, and the
  read-only ref of a merged pull request still points at the old branch tip.
- Clones and forks made before the rewrite keep the old history.
- The guest image inside the APK was scanned separately; the only device model string in it
  belongs to a vendored browser driver's emulation presets, not to us.
