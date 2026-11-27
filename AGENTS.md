# Omdroid (`proot-post`)

Single Android APK (`com.phoshdroid.app`) that boots Omarchy -- Hyprland plus the Quickshell-based Omarchy shell on Arch Linux ARM -- in a proot guest on unrooted Android 12+, through an in-process Termux:X11 (Xlorie). The chain in one line: Android surface -> `com.termux.x11.MainActivity` (X server, `DISPLAY=:0`) -> cage (wlroots, x11 backend, pixman) -> Hyprland -> Omarchy shell, with no systemd anywhere. Repo dir is `proot-post`; product name is Omdroid.

## Layout

- `app/` — our Kotlin, namespace `com.phoshdroid.app`. `LauncherActivity` owns the launch; `PhoshdroidApp` creates the notification channel; `DisplayShiftMonitor` records display changes; `SettingsFragment` holds the settings screen.
- `app/src/main/kotlin/com/phoshdroid/app/launch/` — the launch logic, one file per decision:
  - `LaunchDecision.kt` — the single WAIT/FORWARD/START rule behind `onCreate`, `onNewIntent` and `onResume`.
  - `LaunchReadiness.kt` — when to hand over: ready marker, 25 s fallback, 120 s cap, dead session.
  - `SessionPrep.kt` — wipes the guest runtime dir and stale sockets before a session.
  - `DisplayGeometry.kt` — predicts the X root and the extra-key bar's bottom gap from the window.
  - `UiScale.kt` — resolves the integer scale from `auto`, `1` or `2`.
  - `GuestOverlay.kt` — copies the APK's guest scripts into the extracted guest when the bytes differ.
  - `KeyCapture.kt` — enables Termux:X11's `KeyInterceptor` accessibility service by merging our component into `enabled_accessibility_services`; needs `WRITE_SECURE_SETTINGS` (granted by `install.sh`).
- `app/src/main/kotlin/com/phoshdroid/app/proot/` — `ProotCommandBuilder.kt` (proot args and env), `ProotService.kt` (session process, notification, exit reporting), `SessionExit.kt` (the retry rule), `ProotDistroManager.kt`.
- `app/src/main/kotlin/com/phoshdroid/app/extraction/AssetExtractor.kt` — untars a gzipped asset stream into the prefix and writes `.extraction_complete`; the launcher opens `assets/bootstrap.bin` and `assets/rootfs.bin` and passes them in.
- `app/src/main/kotlin/com/phoshdroid/app/settings/` — `PhoshdroidPreferences.kt`, `ProotConfigWriter.kt`.
- `termux-x11/` — submodule `zweck/termux-x11` on the `phoshdroid-integration` branch (Gradle `:termux-x11-app`), the X server.
- `termux-app/` — submodule `zweck/termux-app` on the `phoshdroid-integration` branch (`:terminal-emulator`, `:terminal-view`, `:termux-shared`).
- `rootfs/` — the current scripts are `package-omarchy-rootfs.sh` (guest image: pinned upstream bundle, overlay, cage/wlroots/libliftoff, gzipped tar) and `build-bootstrap.sh` (Termux prefix + `jniLibs`, via `fetch-termux-packages.py`). `build-rootfs.sh` and `package-rootfs.sh` are pmOS-era and not part of this build.
- `rootfs/patches/aquamarine/` — two patches on aquamarine 0.14.0: 0001 carries the proven Android KGSL buffer pipeline, 0002 adds `wl_touch` to the Wayland backend. `rootfs/build-aquamarine.sh` applies both in a container under qemu-user and prints an ABI comparison; its output is copied to `rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13`.
- `rootfs/overlay/etc/phoshdroid/` — the files the packager installs and the APK carries:
  - `start.sh` — session entry: env, UI mode, plugin index, resize helper, watcher, `exec cage -- session-child.sh`.
  - `session-child.sh` — bounded wait for cage's geometry, then exec Hyprland.
  - `fit-x11.py` — keeps cage's window equal to the X root, each side rounded down to even.
  - `omarchy-watch.py` — writes the ready marker, then keeps the shell layers in step with the monitor.
  - `omarchy-plugin-index.sh` — builds the plugin index Quickshell reads under proot.
  - `omdroid-ui.sh` — reads `~/.config/omdroid/ui` (`mobile`, the default when missing, or `desktop`) and installs or removes the mobile UI: `shell.toml` sizes, `shell.json` bar and panels, a marked `looknfeel.lua` block, plugin and icon links.
  - `omamobile/` — five Omamobile plugin trees vendored (MIT, upstream commit and every local change in `SOURCE.md`); only the pointer-clean ones, the rest need hardware or systemd.
  - `lib/` — the patched `libaquamarine.so.13`, first in `start.sh`'s `LD_LIBRARY_PATH`, with its README and BSD-3-Clause licence.
  - `fake-proc/` — the `/proc` files bind-mounted over the guest's.
  - `bwrap-shim.sh` and `config.defaults` are Phosh relics; the packager does not install them.
- `docs/omarchy/` — `launch-contract.md` (the host/guest interface), `ARCHITECTURE.md`, the round reports (`r2-host`, `r2-guest`, `r3-host`, `r3-device`, `r4-touch`, `r4-input`, `r5-mobile-ui`, `r5-mobile-ui-device`, `r5-touch-patch`, `r5-touch-device`), `device-bringup-report.md`, `payload-findings.md`, and `tools/` (adb helpers, `build-chain.sh`, `install.sh`).
- `docs/brand/` — the logo generator, the SVGs, the contact sheets and the staged Android icon resources.

## Dev environment

Java 17, Gradle 8.11.1, AGP 8.7.3, Kotlin 2.1.0. `compileSdk`/`targetSdk` 35, `minSdk` 31, NDK `27.2.12479018`. Clone with submodules:

```bash
git clone --recursive https://github.com/zweck/omdroid.git
git config core.hooksPath .githooks   # pre-push runs unit tests
```

`local.properties` is gitignored (SDK path). `gradle.properties` sets `-Xmx32g` so asset packaging does not OOM.

## Build & test

CI (`.github/workflows/ci.yml`) is the gate — checkout `--recursive`, Temurin 17:

```bash
./gradlew :app:lintDebug
./gradlew :app:test
```

`docs/omarchy/tools/build-chain.sh` is the local build: repack unless `--no-repack`, verify the overlay inside the image, delete the old APK, `:app:assembleDebug`, `:app:test`; log `/tmp/omarchy-build-chain.log`. By hand:

```bash
./rootfs/package-omarchy-rootfs.sh   # guest image -> app/src/main/assets/rootfs.bin
./rootfs/build-bootstrap.sh          # Termux prefix -> jniLibs + assets/bootstrap.bin
./gradlew :app:assembleDebug
docs/omarchy/tools/install.sh        # sideload; HyperOS refuses adb install
```

Bump `versionCode` + `versionName` together in `app/build.gradle.kts`. A release is a `release: 0.0.N-alpha` commit on `main`, the tag `v0.0.N-alpha`, and a GitHub pre-release titled `Omdroid 0.0.N-alpha` with the debug APK attached as `omdroid-0.0.N-alpha.apk` and its sha256 in the notes.

## Conventions

- **Every change lands through a pull request.** No direct pushes to `main`, releases included: a release PR carries the version bump, the `release: 0.0.N-alpha` commit and the round report, and the tag goes on `main` after the merge. Inside a round, each stream's branch is a PR into that round's integration branch (`r11/integration`, `r12/integration`, …) and the integration branch is a PR into `main`. Draft while the work is unfinished; ready when its gates pass.
- Conventional commits: `feat(scope):`, `fix(scope):`, `perf(…)`, `build:`, `chore(scope):`, `release: 0.0.N-alpha`. Scopes in use: `rootfs`, `launcher`, `proot`.
- Own code lives under `app/src/main/kotlin/com/phoshdroid/app/`. JUnit 5 tests sit in the same package; method names are backtick sentences (`writes default config`).
- Lint only our app (`:app:lintDebug`). `abortOnError = false`; do not lint Termux submodule sources. Root `build.gradle.kts` forces all Android subprojects to compileSdk 35 — do not fight the Groovy Termux files.
- Keep `android.nonTransitiveRClass=false` (Termux uses transitive `R.style.*`). Keep the guava `listenablefuture` → `9999.0-empty-to-avoid-conflict-with-guava` pin.
- `docs/omarchy/launch-contract.md` is the host/guest interface: neither side changes it alone, and a change that alters it updates it in the same round.

## Pitfalls

- Submodules are required. CI checks them out recursively; a bare clone will not compile.
- Do not hand-edit `app/src/main/assets/{rootfs,bootstrap}.bin` (gitignored, generated). Overlay edits live in `rootfs/overlay/` and reach an install two ways: `etc/phoshdroid/` is re-synced from the APK on every cold start, the rest only through an image repack.
- **The X root is the size authority, and odd sizes are normal** (3200x1971 on the tablet). The host passes a prediction as a hint; the guest ignores it and derives everything from the root, rounding each side down to even for cage's window.
- `<prefix>/tmp/omarchy-runtime/` (the guest's `XDG_RUNTIME_DIR`) must be wiped before a session. A stale `omarchy-plugin-scan.txt` makes the shell load the previous session's plugins.
- A live size change (rotation, fold, extra-key bar) recovers by restarting only the shell — the bar and wallpaper blink for 2-3 s. Do not restart the session for a size change.
- Delete the output APK before assembling after an asset change; the package step otherwise appends to it and doubles the size. Run gradle in the foreground — an assemble takes minutes.
- The device tools in `docs/omarchy/tools/` need `TABLET_SERIAL` (the adb serial) and refuse to run without it, so a second attached device is never picked by accident.
- `adb install` is refused on HyperOS/MIUI (`INSTALL_FAILED_USER_RESTRICTED`); `docs/omarchy/tools/install.sh` tries `pm install -r -t` from `/data/local/tmp` first, falls back to the on-device installer, grants `POST_NOTIFICATIONS` + `WRITE_SECURE_SETTINGS` (the key interceptor needs the second), and verifies the installed sha256.
- `GuestOverlay` re-syncs every `etc/phoshdroid` file from the APK on each cold start when the bytes differ, so a fix pushed into the guest by hand (`gpush.sh`) is reverted on the next start until the APK carries it. The `syncGuestOverlay` list in `app/build.gradle.kts`, the packager's "Applying overlay" block and `rootfs/overlay/etc/phoshdroid/` must name the same files — now including `lib/`, `omamobile/` and `omdroid-ui.sh` — or a fresh install and an updated install run different guests. The three per-feature trees `mem/`, `share/` and `complete/` are already named in both places: a new file inside one of them needs no list edit, and `start.sh` runs each tree's optional `session-start.sh` right after `session.env` is read.
- Quickshell's `ScreencopyView` kills the shell under proot: Hyprland offers `zwp_linux_dmabuf_v1` at version 3 and a `ScreencopyView` asks for version 4, so the shell exits with a Wayland protocol error the moment any app maps. The vendored switcher draws each card as the app's icon and window title instead.
- In-process Termux:X11: `conn_fd` is split into `server_conn_fd` / `client_conn_fd` on purpose. Merging them again makes the desktop render into a void. Touch path: direct touch (`touchMode` `3`) only works with the patched aquamarine in `lib/`, and `2` (tap → cursor move + click) is the fallback; keep identical `XI_TouchUpdate` dedup (zero-motion dupes kill swipe-unlock).
- `start.sh` quoting is fragile — an apostrophe in a comment has already broken the script. Prefer no single quotes in comments inside that file.
- `LauncherActivity` is `singleTask`; the `bootstrapCompleted` / `bootstrapInProgress` flags must stay process-scoped or a second instance races the X server.
- CI does not assemble the APK (asset too large). A green `:app:test` is not a bootable image.
