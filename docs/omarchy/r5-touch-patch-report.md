# R5 touch patch: give nested Hyprland a touch device (aquamarine `wl_touch`)

Brief: `docs/omarchy/brief-r5-touch-patch.md`. Worker report.
Scratch: `<scratch>/omarchy/r5/touch-patch/` (sources, build trees, the P4 harness).

## STATUS TABLE

| Step | What | Status | Decisive fact |
| --- | --- | --- | --- |
| P1 | Reproduce the installed library from `a79fb21b` + 0001 | DONE | built from the guest image imported as an arm64 container; ABI matches the installed library (SONAME, all 18 NEEDED entries, 47/47 consumer imports, GLIBC max 2.38) |
| P2 | Write `0002-wayland-add-wl_touch-input.patch` | DONE | 137 insertions (107 `Wayland.cpp`, 30 `Wayland.hpp`), 236-line patch, sha256 `48448110…` |
| P3 | Build the patched library, ABI checks | DONE | `libaquamarine.so.0.14.0`, 1 775 168 bytes, sha256 `8514d2a65f2e10bb75d74a97cd3bc97db52f06bc19ecd0a47395aa9fdae66191`; SONAME/NEEDED/GLIBC unchanged, 0 strong symbols lost, 47/47 consumer imports present |
| P4 | Device-free test (cap 20 calls) | PARTIAL | mock parent + client harness: the patched library creates a `wl_touch` device and fires `events.newTouch` (`[aq] New wayland touch wl_touch`, parent sees `get_touch`); the unpatched library never binds it. Positions/up/motion not exercised — the client dies under qemu in aquamarine's frame path |
| P5 | `rootfs/build-aquamarine.sh` | DONE | `bash -n` clean; an end-to-end run built the library and printed the ABI comparison |
| P6 | Report | DONE | this file |

## The patch

`rootfs/patches/aquamarine/0002-wayland-add-wl_touch-input.patch` is a `git format-patch` commit on
top of 0001 (both in `rootfs/patches/aquamarine/`, both sha256-pinned in the build script):
`wayland: add wl_touch input support`.

- `include/aquamarine/backend/Wayland.hpp`: `CWaylandTouch : public ITouch` modelled on
  `CWaylandPointer` (30 lines), `touches` on `CWaylandBackend`, a `friend` on `CWaylandOutput`
  (it reads `waylandState.surfaceSize`), and the `<optional>`/`<vector>` includes.
- `src/backend/Wayland.cpp` (107 lines): the constructor wires
  `wl_touch.down/up/motion/frame/cancel` to `ITouch::SDownEvent` / `SUpEvent` / `SMotionEvent` /
  `events.frame` / `SCancelEvent`; `initSeat()` gains a `WL_SEAT_CAPABILITY_TOUCH` branch that
  creates the device through `wl_seat.get_touch` and emits `events.newTouch` on an idle callback, and
  drops it again when the capability goes away, exactly as the pointer and keyboard branches do.

Two facts decided the mapping, both read from the source rather than assumed:

- **Position space**: `ITouch` positions are 0..1, not pixels — the libinput path produces them with
  `libinput_event_touch_get_x_transformed(te, 1)` (`src/backend/Session.cpp`, the four `TOUCH_*`
  cases), and the pointer's own `emitWarp` divides by `waylandState.surfaceSize` the same way. The
  patch divides `wl_fixed_to_double(x|y)` by the output's surface size.
- **Timestamps**: the same cases pass `libinput_event_touch_get_time_usec(te) / 1000`, so the
  protocol's millisecond `time` argument is passed straight through.

`wl_touch.motion` carries no surface, so a sequence stays bound to the output it started on
(`lastOutput`, set on `down`); `wl_touch.cancel` carries no ids, so every point still down is
cancelled. Both are noted in the code.

Hyprland needs no change: `src/Compositor.cpp` already listens for `aquamarine->events.newTouch` →
`g_pInputManager->newTouchDevice`, and cage already forwards touch (`wlr_seat_touch_notify_down`) —
the device simply never existed.

## ABI checks

Reference: the library inside `app/src/main/assets/rootfs.bin`
(`/opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0`, 1 661 600 bytes, built with gcc).

| Check | Installed (gcc) | P1: base + 0001 (clang) | P3: + 0002 (clang) |
| --- | --- | --- | --- |
| SONAME | `libaquamarine.so.13` | same | same |
| NEEDED | 18 entries | identical | identical |
| strong (T/D/B/R) symbols | 972 | 1095, 0 lost | 1106, 0 lost |
| all defined symbols | 1673 | 1769 | 1788 |
| Hyprland + hyprctl imports resolved | 47/47 | 47/47 | 47/47 |
| highest GLIBC requirement | 2.38 | 2.38 | 2.38 |

The image's glibc is `2.43+r22`, so the 2.38 requirement is unchanged and satisfied.

The raw "all defined symbols" count is not comparable between a gcc and a clang build of the same
source: the difference is weak template and destructor instantiations (the `D1`/`D2` destructor
variants, `Hyprutils::Memory::CWeakPointer<T>::decrementWeak`, `__gnu_cxx::__stoa`), which no
consumer imports. The check that matters is therefore the strong-symbol set (0 lost) **and** the
consumer's own undefined-symbol list, both green. The patched library exports 17 new
`CWaylandTouch` symbols and nothing disappeared.

Why clang: the image's gcc 16 builds everything else, but its `cc1plus` segfaults under this box's
qemu-user 11.1.2 on `src/backend/drm/DRM.cpp` — reproducible at `-O0`, `-O1`, `-O2` and `-O3` and on
a preprocessed translation unit, so it is the emulator, not the source. On a native aarch64 host the
script's `OMDROID_AQUAMARINE_COMPILER=gcc` uses the bundle's own compiler; the ABI table above is
what decides whether a build is usable.

## Test

`<scratch>/omarchy/r5/touch-patch/out/p4/` holds a device-free harness:

- `mock-parent.c` — a minimal Wayland *parent* built on libwayland-server that advertises
  `wl_compositor`, `wl_shm`, `xdg_wm_base`, `wl_seat` **with TOUCH**, and 2 s after the client binds
  `wl_touch` sends `down(id 3, 128.5, 72.0)` → `motion(3, 640, 360)` → `frame` → `up(3)`, then
  `down(id 4)` → `cancel`.
- `p4-touch-client.cpp` — creates aquamarine's `CBackend` with only the Wayland implementation,
  listens for `events.newTouch` and the `ITouch` events, and asserts the normalised positions
  (128.5/1280, 72/720; 0.5, 0.5; 32/1280, 36/720).

Result, same harness, same parent, only the library swapped:

| Library | Parent sees `get_touch` | `events.newTouch` | ITouch events |
| --- | --- | --- | --- |
| P1 (base + 0001) | no | never fires | none |
| P3 (+ 0002) | `[parent] client bound wl_touch` | `P4 newTouch name=wl_touch`, PASS | not delivered — see below |

So the half the device's `hyprctl -j devices` reports (`touch: []`) is proven device-free: without
0002 no touch device exists, with it `CWaylandTouch` is created from the seat capability and
`events.newTouch` reaches a consumer.

Limitation, stated plainly: the down/motion/up mapping itself was **not** exercised. The client dies
with a SIGSEGV under qemu-user in aquamarine's frame path (right after `Swapchain: Clearing`, with
and without a buffer), before the parent's touch sequence arrives, so the positions and the
cancel-per-id path have no passing run here. The same qemu instability is what kills `cc1plus`; it is
an emulator artefact rather than a fault line in the patch — but it is unproven code until the
device run.

## How it gets onto the device

Two options for the parent to choose; both use the same artefact from
`rootfs/build-aquamarine.sh` (library sha256 `8514d2a…`, 1 775 168 bytes).

**A. The packager installs it into the image (recommended, no new sync path).** After the bundle
rootfs is extracted and the overlay applied, copy the install tree over the guest prefix:

```sh
./rootfs/build-aquamarine.sh                       # writes ~/.cache/omdroid/aquamarine/out
cp -a ~/.cache/omdroid/aquamarine/out/. <work>/stage/opt/omarchy-android/aquamarine/
./rootfs/package-omarchy-rootfs.sh                 # repack -> app/src/main/assets/rootfs.bin
```

The library keeps its SONAME (`libaquamarine.so.13`), so the existing `.so`/`.so.13` symlinks keep
resolving and nothing else in the image changes. Cost: one rootfs repack plus an APK rebuild/install,
and the image grows by 1.78 MB (roughly 0.9 MB once gzipped).

**B. The APK carries it and `GuestOverlay` syncs it into an existing install.** The sync mechanism is
`syncGuestOverlay` in `app/build.gradle.kts` (an include list under `rootfs/overlay/etc/phoshdroid`,
copied into `assets/guest-overlay/etc/phoshdroid/…`) plus `GuestOverlay.sync()`, which writes each
asset into the guest when the bytes differ. Shipping a library this way means a new include for
`opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0` and a sync target outside
`etc/phoshdroid` — files another agent owns this round, so this report only names the change.
Caveats: the 1 775 168-byte asset lands in the APK; `GuestOverlay` must be given the guest root for
that path; and the new library is only loaded by a **session** restart, not the shell-only restart a
size change uses (`docs/omarchy/launch-contract.md`).

## What the device phase must prove

1. The device exists now:
   ```sh
   hyprctl -j devices | python3 -c 'import json,sys; d=json.load(sys.stdin); print("touch:", [t["name"] for t in d["touch"]])'
   # expect ["wl_touch"]; an empty list means the new library is not loaded
   grep -i "aquamarine touch" "$XDG_RUNTIME_DIR"/hypr/*/hyprland*.log   # needs /etc/phoshdroid/trace
   ```
2. A finger reaches the shell: with `touchMode = "3"` (direct touch, the app's current default) tap a
   workspace number in the bar — the workspace must switch, and with `WAYLAND_DEBUG=1` running on the
   shell the layer surface must receive `wl_touch.down`.
3. Positions are sane: tap all four corners and the bar's far right. A systematic offset or a
   mirrored axis means the normalisation is against the wrong size — the X root is the size
   authority, and odd sizes are normal.
4. Multi-touch, which pointer emulation could never do: two fingers dragging in a Qt view (kinetic
   scroll) and Hyprland's own `gestures:workspace_swipe_touch` (off by default,
   `hyprctl getoption gestures:workspace_swipe_touch`).
5. Regression: the pointer path still works (`hyprctl -j devices` still lists the `wl_pointer`
   device), and a session restart after a size change still recovers.

## Not verified

- The patched library has **never been loaded on the device**: no device, no adb, no gradle in this
  round, and no Hyprland run against it. Everything above is source, ABI numbers and a mock-parent
  harness.
- The `wl_touch.down/motion/up/cancel` → `ITouch` mapping and the 0..1 normalisation are **unproven
  end to end**; only device creation and `events.newTouch` were observed.
- `SCancelEvent` on `wl_touch.cancel` is emitted per remembered id — the protocol carries none there,
  so this is an interpretation, and Hyprland's reaction to it is untested.
- The gcc build path is unproven in this environment (qemu `cc1plus` segfault on `drm/DRM.cpp`); the
  shipped artefact is a clang build of the same source.
- The patch is not upstreamed; aquamarine upstream may want a different shape (e.g. per-output touch
  devices) before it accepts one.
- The 0001 patch was taken from the bundle as delivered; its own content was not reviewed.
