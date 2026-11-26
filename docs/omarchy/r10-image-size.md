# R10 S3: a smaller, faster-to-extract guest image, and 16 KB pages

Worktree `proot-post-r10-image`, branch `r10/image-size`, base `bbf908d`.
Scope and rules: `<scratch>/omarchy/r10/COMMON.md`; brief
`<scratch>/omarchy/r10/brief-r10-image.md`.
Scratch: `<scratch>/omarchy/r10/image/`.

## STATUS TABLE

| # | Step | Status | Proof |
|---|---|---|---|
| 1 | 16 KB LOAD alignment for `libtermux.so` | **PASS** (host) | `readelf -lW` on the fresh ndk-build output: all four ABIs `0x4000` (was `0x1000`); submodule commit `3e3b93a5`; ADB probe on a 16 KB device PENDING |
| 2 | Codec measurement table (gzip -6 / zstd -19 / zstd -19 --long=27) | PENDING | — |
| 3 | Prune rules in the packager + pacman `NoExtract` | PENDING | — |
| 4 | zstd image written by the packager, decoded by `AssetExtractor` | PENDING | — |
| 5 | Repack, equivalence diff, `:app:test`, `:app:lintDebug`, APK build, sizes | PENDING | — |

## Step 1: 16 KB page alignment for `libtermux.so`

**Measured (host).** The flag was already in the tree and still did nothing:

- `termux-app` pinned commit `3274badd` ("terminal-emulator: link with 16KB max page
  size") added `-Wl,-z,max-page-size=16384` to `externalNativeBuild.ndkBuild.cFlags` in
  `termux-app/terminal-emulator/build.gradle`.
- A fresh `:terminal-emulator:externalNativeBuildDebug` with that commit reproduced
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
(`flock … ./gradlew :terminal-emulator:externalNativeBuildDebug`, `BUILD SUCCESSFUL in 1s`,
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

## What changed

(filled in per step)

## Host proof

(per step)

## Device A/B plan (the parent runs it)

(see the section at the end)

## Risks

(tbd)

## What I did not do

(tbd)
