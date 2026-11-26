# R10 S3: a smaller, faster-to-extract guest image, and 16 KB pages

Worktree `proot-post-r10-image`, branch `r10/image-size`, base `bbf908d`.
Scope and rules: `<scratch>/omarchy/r10/COMMON.md`; brief `<scratch>/omarchy/r10/brief-r10-image.md`.

Switches this round (no rebuild needed to A/B them at packaging time):
`OMDROID_IMAGE_CODEC=gzip` (pack gzip instead of zstd), `OMDROID_ZSTD_LEVEL`,
`OMDROID_ZSTD_EXTRA` (default `--long=26`), `OMDROID_PRUNE=0` (pack unpruned).
The extractor needs no switch: it reads the codec from the stream's magic bytes.

## STATUS TABLE

| # | Step | Status | Proof |
|---|---|---|---|
| 1 | 16 KB LOAD alignment for `libtermux.so` | **PASS** (host) | `readelf -lW` on a fresh ndk-build: all four ABIs `0x4000` (was `0x1000`); submodule `3e3b93a5`; device probe PENDING |
| 2 | Codec measurement table (gzip -6 / zstd -19 / `--long=27`) | **PASS** (host) | 3.995 GB stream measured; chose `zstd -19 --long=26` |
| 3 | Prune rules in the packager + pacman `NoExtract` | **PASS** (host) | 15,523 entries / 418,199,488 B removed, none on the hard-link list |
| 4 | zstd image written by the packager, decoded by `AssetExtractor` | **PASS** (host) | `:app:test` 0 fail (default run 12 pass + 1 skipped; all 13 with `OMDROID_IMAGE` set, ran here); real-image extraction on this host |
| 5 | Repack, equivalence diff, `:app:test`, `:app:lintDebug`, APK build, sizes | **PASS** (host); device rows PENDING | APK 1,124,644,223 B (−34.5 %); image 999,487,241 B (−37.2 %); equivalence: 0 unexplained, 0 added, 0 changed; 13 tests 0 fail; lint 0 errors; every APK lib ≥0x4000 |

## Step 1: 16 KB page alignment for `libtermux.so`

**Measured (host).** The flag was already in the tree and still did nothing:

- `termux-app` pinned commit `3274badd` ("terminal-emulator: link with 16KB max page
  size") added `-Wl,-z,max-page-size=16384` to `externalNativeBuild.ndkBuild.cFlags` in
  `termux-app/terminal-emulator/build.gradle`.
- A fresh `:terminal-emulator:externalNativeBuildDebug` at that commit reproduced
  `libtermux.so` with **every LOAD segment Align = 0x1000** for all four ABIs
  (`readelf -lW`), i.e. the flag was inert: AGP's ndkBuild `cFlags` reach the compiler
  invocation only, and `-Wl,` options are meaningless there.
- The shipped APK agrees: `lib/arm64-v8a/libtermux.so` in
  `app/build/outputs/apk/debug/app-debug.apk` (1,715,790,990 B) measures `0x1000`, while
  every other arm64 library in the same APK is `0x4000` or `0x10000`.

**Change (submodule `termux-app`, branch `r10/16k-pages`, commit `3e3b93a5`):**

- `terminal-emulator/src/main/jni/Android.mk`: `LOCAL_LDFLAGS := -Wl,-z,max-page-size=16384`,
  with a comment saying why it must be a link flag.
- `terminal-emulator/build.gradle`: dropped the dead `-Wl,-z,max-page-size=16384` entry from
  `cFlags` (the `-Wl,--gc-sections` entry next to it is the same class of no-op; left alone,
  out of scope).
- Why `LOCAL_LDFLAGS` and not the AGP `arguments "--LDFLAGS=…"`: `LOCAL_LDFLAGS` is a
  per-module link flag in ndk-build, so it cannot leak into other modules' link steps, and it
  is the form the NDK documents for ndk-build projects.

**Proof (host, measured).** After the change, a forced rebuild
(`flock … ./gradlew :terminal-emulator:externalNativeBuildDebug`, `BUILD SUCCESSFUL in 7s`,
9 tasks executed) gives, for
`termux-app/terminal-emulator/build/intermediates/ndkBuild/debug/obj/local/*/libtermux.so`:

```
arm64-v8a 0x4000   armeabi-v7a 0x4000   x86 0x4000   x86_64 0x4000
```

(`readelf -lW … | awk '/LOAD/{print $NF}' | sort -u`.)

**Still PENDING (device):** the real check is that a 16 KB-page kernel loads the library —
see the device plan below. `libtermux.so` is the only library in the APK that fails it;
`jniLibs.useLegacyPackaging` stays `true` on purpose (COMMON.md correction 2: the app
executes `libproot.so`/`libproot-loader.so`/`libbash.so` from
`applicationInfo.nativeLibraryDir`, which requires extracted libraries).

## Step 2: codec measurement and the setting chosen

Measured on this host (24 CPUs, 30 GB RAM), `gzip 1.15`, `zstd CLI v1.5.7`. Sample = the
first 600,000,000 B of the guest tar stream; whole = the full 3,995,125,760 B stream
(`gzip -dc` of the shipped `rootfs.bin`). Compressors limited to `-T8`; decodes run three
times each on the whole stream, single-threaded, warm page cache.

| setting | window | sample size (B) | sample ratio | sample compress | whole size (B) | whole compress | whole decode (3 runs) |
|---|---|---|---|---|---|---|---|
| gzip -6 (today) | 32 KiB | 210,342,072 | 2.85x | 10.3 s | 1,591,865,510 | 90.2 s | 9.60 / 8.54 / 8.43 s |
| zstd -19 -T8 | 8 MiB | 161,116,721 | 3.72x | 27.5 s | 1,141,912,976 | 164.2 s | 3.05 / 3.05 / 2.70 s |
| zstd -19 --long=24 -T8 | 16 MiB | 157,076,782 | 3.82x | 37.8 s | — | — | — |
| **zstd -19 --long=26 -T8** | **64 MiB** | **150,056,174** | **4.00x** | 39.4 s | — (see note) | — | — |
| zstd -19 --long=27 -T8 | 128 MiB | 149,254,207 | 4.02x | 37.6 s | 1,062,412,459 | 200.0 s | 3.18 / 2.84 / 2.92 s |

Note: the whole-stream figures are on the **unpruned** stream, so the packed image's size
is not one of them. The packed image (pruned + `--long=26`) is **999,487,241 B**; applying
the sample's ratio to the unpruned stream puts `--long=26` at ~1.06 GB, i.e. within 0.5 %
of `--long=27`.

Decoder memory need is the window plus a few MB of block buffers and tables: gzip ~0.3 MB;
zstd -19 8 MiB; `--long=26` 64 MiB (~70 MB); `--long=27` 128 MiB (~140 MB).

**Decision: `zstd -19 --long=26`.**

- Against plain `-19` (8 MiB) the 64 MiB window saves 6.9 % of the size — over the brief's
  3 % threshold, so the larger window is preferred.
- Against `--long=27` the extra 64 MiB of window buys **0.5 %**, under the same threshold,
  and it would push the decoder to ~140 MB, above the 128 MB cap for a 4 GB phone. So 26 is
  the setting: ~70 MB of decode memory, ~2.9 s to decode the whole stream (2.9x faster than
  gzip -6's 8.4-9.6 s).

The packager exposes level and window as `OMDROID_ZSTD_LEVEL` / `OMDROID_ZSTD_EXTRA`.

## Step 3: prune rules

`rootfs/package-omarchy-rootfs.sh` (after the overlay is applied, before the archive is
written; `OMDROID_PRUNE=0` skips it for the baseline):

- `rm -rf` `usr/share/{doc,man,info,gtk-doc,help}`.
- `find usr/share/locale -name '*.mo'` not under `en`/`en_*` → delete, then remove the
  now-empty `LC_MESSAGES` directories. `locale.alias` and the language directories stay.
- `find usr/share/qt6/translations -maxdepth 1 -name '*.qm' ! -name '*_en.qm'` → delete.
- `rm -rf usr/lib/python3*/test` (already absent from this image: 0 files).
- `etc/pacman.conf`: the `#NoExtract   =` line is replaced in place with

  ```
  NoExtract   = usr/share/doc/* usr/share/man/* usr/share/info/* usr/share/gtk-doc/* usr/share/help/* usr/share/locale/*/LC_MESSAGES/*.mo usr/share/qt6/translations/*.qm usr/lib/python3*/test/*
  ```

  so a later `pacman -S` does not put the bulk back. pacman's globs cannot say "everything
  except en", so a new install also skips English catalogs; nothing reads one (the session
  runs `LC_ALL=C.UTF-8`). **`pacman -Qk` will now list the pruned paths as missing** —
  expected, not corruption.

Measured from the shipped image's own listing (`tar -tvzf`, 83,316 entries):

| rule | entries | files | bytes | of the image |
|---|---|---|---|---|
| `usr/share/{doc,man,info,gtk-doc,help}` | 9,687 | 9,214 | 155,464,598 | 3.95 % |
| locale `*.mo` not `en*` | 5,545 | 5,545 | 246,809,960 | 6.27 % |
| `usr/share/qt6/translations/*.qm` not `*_en` | 291 | 291 | 15,924,930 | 0.40 % |
| `usr/lib/python3*/test/` | 0 | 0 | 0 | absent |
| **total (unique paths)** | **15,523** | **15,050** | **418,199,488** | **10.6 %** |

Regular-file bytes go from 3,933,489,665 B to 3,515,290,177 B (89.4 % of today).
`usr/share/man` holds only `cage.1.gz` (1,012 B) in this image and `python3.14` ships
without its test suite, so those two rules are cheap insurance, not size wins.

**Never pruned, checked:** `usr/include` (15,765 files / 133.5 MB), `usr/share/i18n`
(604 / 15.8 MB), `usr/lib/locale` (13 / 3.4 MB), `var/lib/pacman` (1,697 / 20.1 MB),
`opt/`, `etc/phoshdroid/`, `home/`, every `*.a`, every font.
**Hard-link cross-check:** `rootfs/overlay/etc/phoshdroid/hardlinks.txt` has 2,863 paths;
**0** fall under any pruned prefix (they are terminfo aliases), so no repair-list member
loses its target.

**Fonts (measured; nothing changed, per the brief):** 695.2 MB total, 841 files.

| directory | size | note |
|---|---|---|
| `usr/share/fonts/noto-cjk` | 313.3 MB | 11 `.ttc` collections of 20-27 MB each (NotoSerifCJK Black/Bold/Medium/Regular/Light/ExtraLight …) |
| `usr/share/fonts/TTF` | 243.2 MB | six JetBrainsMono Nerd Font families, ~40 MB each (Mono, Propo, NL variants) |
| `usr/share/fonts/noto` | 122.7 MB | emoji and symbol families |
| `Adwaita` / `liberation` / `gsfonts` / `encodings` / `WOFF2` | 7.6 / 4.4 / 3.2 / 0.6 / 0.3 MB | |

Recommendation for a later round: the largest reachable win is `noto-cjk` (dropping the
Serif weights and unused `.ttc` members saves ~200 MB) and keeping one JetBrainsMono family
instead of six saves ~200 MB more. Both change glyph coverage the bar, panels and terminal
use, so each needs a screenshot pass (tofu = missing glyph) and a decision on CJK text.

## Step 4: zstd image, decoded by the app

**Packager** (`rootfs/package-omarchy-rootfs.sh`): `( cd stage && tar -cf - . ) | zstd -19
--long=26 -T8 -q --force -o "$OUTPUT"`; gzip stays available through
`OMDROID_IMAGE_CODEC=gzip`; the member-count line picks `tar --zstd`/`tar -z` from the same
magic bytes. `bootstrap.bin` is untouched (still gzip).

**Extractor** (`app/src/main/kotlin/com/phoshdroid/app/extraction/AssetExtractor.kt`):
`decompress()` marks the first four bytes of the buffered stream and picks
`GZIPInputStream` for `1f 8b`, `ZstdInputStream` for `28 b5 2f fd`, and throws
`IOException("unknown image compression: …")` otherwise. The stream reaches the extractor
unchanged from `LauncherActivity` (no host change), so an APK that carries a zstd image
still extracts an old gzip image and the gzip bootstrap.

**Dependency** (`app/build.gradle.kts`, dependencies only):

- `implementation("com.github.luben:zstd-jni:1.5.7-9@aar")` — the AAR is 1,144,140 B and
  carries `jni/{arm64-v8a,armeabi-v7a,x86,x86_64}/libzstd-jni-1.5.7-9.so`. Evidence: **every
  one of those `.so` has all LOAD segments `0x4000`** (`readelf -lW`), their only `NEEDED`
  entries are `libc.so`, `libm.so`, `libdl.so` (no `libc++_shared` to ship), and the app's
  four ABIs are exactly the four the AAR provides.
- `testImplementation("com.github.luben:zstd-jni:1.5.7-9")` — the plain jar, so the JVM unit
  tests get the same decoder with a `linux/amd64` native (the AAR has Android natives
  only). It is test-scope, so it never enters the APK.

**Tests** (`app/src/test/.../AssetExtractorTest.kt`): the existing gzip tests stay, plus a
shared mixed archive (regular file with the executable bit, nested paths, a symlink, a hard
link) asserted in **both** formats, an unknown-magic rejection, and a real-image test that
is **skipped unless `OMDROID_IMAGE` names an image** (`OMDROID_IMAGE_TARGET` for ~4 GB of
scratch, `OMDROID_IMAGE_ENTRIES` to assert the member count).

**`docs/omarchy/tools/build-chain.sh`**: the overlay verification picks `tar --zstd`/`tar -z`
from the image's magic bytes instead of hard-coded `-tzf`/`-xzOf`/`-tvzf`. Nothing else in
the repo opens `rootfs.bin` (grep for `rootfs.bin`, `gzip`, `GZIPInputStream`, `-tzf`).

## Step 5: repack, equivalence, gates, sizes

**The shipped `rootfs.bin` is stale relative to the tree**: repacking `bbf908d` adds 75
entries (all `etc/phoshdroid/{lib,omamobile,fakeroot,hardlinks.txt}`), and `start.sh`
(5,502 → 7,512 B) and `omarchy-watch.py` (10,667 → 19,706 B) differ. So "the old image minus
exactly the pruned paths" cannot hold against the shipped asset; the equivalence check uses
a **same-tree baseline** instead — the packager run with
`OMDROID_PRUNE=0 OMDROID_IMAGE_CODEC=gzip`.

| check | result |
|---|---|
| image codec | `28 b5 2f fd` (zstd); `tar --zstd -tvf` lists it |
| members | **68,343** (6,435 dirs, 54,811 files, 5,265 symlinks, 1,832 hard-link entries); shipped image 83,316 |
| `rootfs.bin` | **999,487,241 B** vs the shipped 1,591,865,500 B → **−592,378,259 B (−37.2 %)** |
| same-tree baseline (`OMDROID_PRUNE=0 OMDROID_IMAGE_CODEC=gzip`) | 83,391 members, 1,592,571,977 B |
| **equivalence** (baseline vs new: name, type, size, mode, link target) | **missing 15,048 — all under the pruned prefixes, 0 unexplained; added 0; changed 0; 418,199,488 B removed** |
| `:app:test` | 13 tests per variant, **0 failures** (debug and release), real-image test included |
| real-image extraction on this host | **61,908 non-directory members + the marker = 61,909**, `skippedLinks = 0`, 3,528,857,433 B on disk under `<scratch>/omarchy/r10/image/extracted-real` |
| `:app:lintDebug` | **0 errors, 37 warnings** (pre-existing resource/localisation set; none mention the extractor or zstd) |
| APK | **1,124,644,223 B** vs 1,715,790,990 B → **−591,146,767 B (−34.5 %)** |
| APK `assets/rootfs.bin` | 999,487,241 B, magic `28 b5 2f fd` |
| `readelf -lW` on every APK library | arm64-v8a 13 files and x86_64 3 files, **all LOAD segments `0x4000` or `0x10000`**, including `libtermux.so` (`0x4000`, was `0x1000`) and `libzstd-jni-1.5.7-9.so` (`0x4000`, 603,960 B on arm64) |

The gates ran as one command under the shared Gradle lock:
`flock … ./gradlew :app:assembleDebug :app:lintDebug :app:test --no-daemon
-Dorg.gradle.jvmargs="-Xmx10g -Dfile.encoding=UTF-8"`, the old APK deleted first
(AGENTS.md pitfall). The real-image test needs `OMDROID_IMAGE`, `OMDROID_IMAGE_TARGET`
(~4 GB of scratch) and `OMDROID_IMAGE_ENTRIES`; with `--no-daemon` so the test JVM
inherits them.

## Device A/B plan (the parent runs it)

The tablet is a 4 KB-page device and every row here is **PENDING**.

1. Clean install (uninstall first; `docs/omarchy/tools/install.sh`), one cold start on a
   wiped app: extraction time from the `launch: rootfs-extracted` log line. Baseline
   (0.0.17): **283,904 ms**. PASS = at least 20 s shorter, no new error in logcat.
2. Extracted guest size: `adb shell run-as com.phoshdroid.app du -sh
   files/usr/var/lib/proot-distro/installed-rootfs/omarchy`. Baseline **3.8 G**;
   PASS = ~0.4 G smaller.
3. `probe.sh` PASS and the session reaches the shell.
4. One AUR build that compiles C (`yay -S <small package>`): PASS = it links (headers and
   `*.a` intact, `libc_nonshared.a` still found).
5. Visual pass over the bar, panels and terminal: no tofu, clock and launcher text intact.
6. A/B the codec: the same tree packed with `OMDROID_IMAGE_CODEC=gzip`, compare step 1's
   number — zstd must not be slower.
7. 16 KB pages: the evidence is the `readelf` row above plus `adb shell getconf PAGE_SIZE`
   on any 16 KB device (the tablet is 4 KB, so hardware stays unproven).

## Risks

- **The zstd decode allocates a 64 MiB window** on first start. If extraction is OOM-killed
  on a 4 GB phone, `OMDROID_ZSTD_EXTRA=""` (8 MiB window, ~0.5 % bigger image) is the
  one-variable fallback.
- **zstd-jni is a new native dependency**; it is loaded only by `AssetExtractor`, so a failed
  `System.loadLibrary` shows up as an extraction error on device, not at build time.
- **Pruning is destructive for `pacman -Qk`** and for packages that expect their own docs
  or locales; `NoExtract` keeps new installs slim but also means a reinstalled package will
  not restore English catalogs.
- **The stale shipped asset** means main's `rootfs.bin` predates several overlay files; the
  parent should repack on merge rather than keep the current asset.

## What I did not do

- No device work: no adb, no install, no launch (the parent's round).
- No font pruning (measured and recommended only, per the brief).
- `AGENTS.md`, `README.md`, `docs/omarchy/ARCHITECTURE.md` and
  `docs/omarchy/payload-findings.md` still describe the image as gzip; they are not mine
  this round.
- Not addressed: the duplicated Hyprland/Mesa under `/opt` and `/usr` (~135 MB, a packaging
  decision), and `usr/include` + `*.a` (kept on purpose).
- `pacman -Qk` output after pruning was not captured (it needs a guest, not this host).
