# R10 S4 (damage): send the real damage to the parent compositor

Branch `r10/aquamarine-damage`, from `bbf908d`. Stream owner: aquamarine patch series only
(`rootfs/patches/aquamarine/`, `rootfs/build-aquamarine.sh`, the rebuilt library under
`rootfs/overlay/etc/phoshdroid/lib/`, this file). No device was available: every device claim
below is PENDING.

Evidence labels: **measured** (host command given), **read** (file:line), **estimated** (basis).
Upstream revisions read: Hyprland `5c9377c` (0.56.1, `manifest/components.lock` of
BlackFireAlex/omarchy-android v0.1.1), aquamarine `a79fb21` (0.14.0) with this repo's 0001 and
0002, wlroots 0.20.2 (`d783533`), cage 0.3.1 (`b7b774a`), Xlorie from the `termux-x11` submodule.
All paths below are relative to those trees.

## Status table

| # | Step | Status | Proof |
|---|---|---|---|
| 1 | Facts (damage chain, wlroots, Present) with citations | PASS, every link holds (two corrections to the brief, below) | section "Facts" |
| 2 | Patch 0003 + build script edit | PASS | commit `2e2831f`; `rootfs/build-aquamarine.sh --no-build` prints `patch series checksums verified` and applies all three patches on `a79fb21` |
| 3 | Build, ABI comparison, copy to overlay, lib README | PASS | `build-aquamarine.sh` exit 0, `ABI OK` (SONAME and NEEDED identical, 0 of 47 consumer imports missing, GLIBC 2.38 <= 2.43); sha256 `35a9ffd4...1562`, 1 775 920 bytes; README updated |
| 4 | VFR analysis (no code) | PASS (analysis; mechanism NOT proven, experiment given) | section "Stretch: why VFR drops the last frame" |
| 5 | Device A/B plan | PASS (written, PENDING on the device) | section "Device A/B plan" |

## What changed

`rootfs/patches/aquamarine/0003-wayland-send-committed-damage.patch` (sha256
`61dc6fc6176ef9013a05b6c19694e77fecdac9a678dc6c0f84b1d80741687daf`), on top of 0001 and 0002:

- `src/backend/Wayland.cpp`, `CWaylandOutput::commit()`: the unconditional
  `sendDamageBuffer(0, 0, INT32_MAX, INT32_MAX)` is replaced by `sendSurfaceDamage()`. It sends
  - the whole surface, in the old wire form, when the pending state carries no damage
    (`AQ_OUTPUT_STATE_DAMAGE` unset), when the buffer size differs from the previous commit's
    (`waylandState.surfaceSize` still holds it at that point), or when this `wl_buffer` has not
    been sent to the parent before (new `CWaylandBuffer::attached` flag);
  - nothing when the committed damage is empty or lies outside the buffer. The buffer is still
    attached and committed with its frame callback, so the frame loop keeps running (the
    wlroots side of this is fact 4);
  - otherwise the rectangles of `state->internalState.damage`, clipped to the buffer; more than 32
    rectangles collapse to their bounding box (only ever adds area).
- `AQ_WAYLAND_FULL_DAMAGE=1` (read once, `envEnabled` semantics: exactly `1`) sends the whole
  surface on every commit in the old wire form. Under `AQ_TRACE=1` (already set by `start.sh`
  in debug mode) each commit logs `commit damage N rect(s)` or `(whole surface)`.
- `include/aquamarine/backend/Wayland.hpp`: `bool attached` on `CWaylandBuffer`. Hyprland never
  builds this class, and the consumer-imports gate below covers the rest.
- `rootfs/build-aquamarine.sh`: pins and verifies the third patch's sha256 and applies it.

## Facts (step 1)

Every link of the chain was read in source; none was measured on a device.

1. **What Hyprland hands aquamarine.** Per render, `IHyprRenderer::renderMonitor` takes
   `damage = m_damage.getBufferDamage(bufferAge)` (`src/render/Renderer.cpp:1753`), i.e. the
   current frame's damage plus the previous `age - 1` frames', where `age` comes from
   `swapchain->next(&bufferAge)` (`:1737`). The ring keeps 3 frames
   (`src/output/DamageRing.hpp:7`; `getBufferDamage` returns the whole monitor for an age beyond
   4 and collapses more than 8 rectangles to their extents, `src/output/DamageRing.cpp:44-63`),
   and the swapchain length is 3 (`src/output/Monitor.cpp:2695`). With `damage_tracking = 2`
   (image `looknfeel.lua`) the damage is real; modes 0 and 1 would set the whole monitor
   (`Renderer.cpp:2117-2118, 2210-2211`). At the end of the render the region is turned back by
   the inverse monitor transform into buffer space and added to the output state:
   `frameDamage.transform(invertTransform(m_transform), m_transformedSize...)` then
   `m_output->state->addDamage(frameDamage)` (`Renderer.cpp:2205-2221`). So the coordinate space
   is **buffer pixels** (mode size, after transform and scale), the space `damage_buffer`
   wants, and `addDamage` is called on every render, empty or not. It sets
   `AQ_OUTPUT_STATE_DAMAGE` (`aquamarine src/output/Output.cpp:66-69`) and `onCommit()` clears it
   (`:161-164`). A full redraw uses `{0, 0, 10 W, 10 H}` (`Renderer.cpp:2118`), which is why the
   patch clips to the buffer.
2. **Hyprland's own patches do not touch this.** The upstream bundle's Hyprland patch
   (`patches/hyprland/0001-render-carry-proven-Android-KGSL-presentation-path.patch` in
   BlackFireAlex/omarchy-android v0.1.1) changes `render/gl/GLRenderbuffer.*`, `OpenGL.*`,
   `LinuxDMABUF.cpp`, `ImageCopyCapture.cpp` and `ProtocolManager.cpp` only: no damage,
   scheduling or commit code. The image's `Hyprland` reports `0.56.1`, the pinned revision's version.
3. **The SHM readback agrees with the damage.** With `HYPRLAND_SHM_DAMAGE=1`, `CGLRenderbuffer::unbind`
   skips the readback when `m_renderData.damage` is empty and otherwise reads back the bounding
   box of that same region into the SHM buffer (patch lines 378-431). The region sent to the
   parent is the same region, so the readback always covers it.
4. **Correctness of "aged" damage as a commit-to-commit delta.** The region sent is the
   buffer-age union (up to 3 frames), a superset of what changed between the buffer attached
   before and this one, so it is safe. It also stays correct when the ring is NOT strictly
   rotating: `CSwapchain::next` always reports `age = options.length` and skips locked buffers
   (`aquamarine src/allocator/Swapchain.cpp:87`), which understates the true age of a buffer that
   was skipped for a while. That stale-pixel risk exists today inside Hyprland's staging
   framebuffers. For the picture the parent shows, the root keeps frame k-1 and receives
   `D_k` re-rendered in full, and the true change of frame k is inside `D_k`, so the screen stays
   right whatever the stale rest of that buffer holds. A rejected commit (the "refusing to reuse
   a non-released buffer" path, `Wayland.cpp commit()`) makes Hyprland roll the swapchain back and
   `damageEntire()` (`Renderer.cpp:2453-2459`), and aquamarine keeps the pending damage because
   `onCommit()` is skipped, so the next commit is a superset too.
5. **wlroots 0.20.2 delivers the frame callback for a commit with no damage.**
   `handle_scene_surface_surface_commit` calls `wlr_output_schedule_frame` whenever the commit
   leaves a frame callback pending and the surface is on an enabled output
   (`types/scene/surface.c:360-378`). That sets `output->needs_frame` and queues an idle frame
   (`types/output/output.c:848-862`). cage's frame handler then runs
   `wlr_scene_output_commit` and **always** `wlr_scene_output_send_frame_done`
   (`cage output.c:136-149`), and `wlr_scene_output_needs_frame` is true because `needs_frame`
   is set (`types/scene/wlr_scene.c:2183-2193`), so an idle frame is committed (a Present with an
   empty update region, below) rather than skipped. The callback therefore still comes back, with
   no pixels copied.
6. **Damage reaches the X server as the Present update region.** The scene's accumulated
   damage goes into the output state (`wlr_scene.c:2439`). A client buffer's `damage_buffer`
   becomes `surface->buffer_damage` (`types/wlr_compositor.c:248-285`) and is passed to the
   scene unchanged (`types/scene/surface.c:344-352`); an empty region means no damage while a
   NULL one means the whole buffer (`wlr_scene.c:964-969`). The x11 backend turns the state's
   damage plus any Expose region into an XFixes region and passes it as the `update` of
   `xcb_present_pixmap` (`backend/x11/output.c:358-393`; the backend asks for the whole window
   only when the state has no damage at all). cage's pixman renderer keeps the client buffer by
   reference with no copy (`render/pixman/renderer.c:263-272`, no `update_from_buffer`), and
   the scene can scan out the client's SHM buffer directly when it is still locked
   (`wlr_scene.c:2149-2153`; the x11 backend accepts SHM buffers whose stride is the minimum,
   `backend/x11/output.c:176-183`). Either path (direct scan-out or the scene's own pixman
   composite, which re-renders only the damage ring region, `wlr_scene.c:2534-2536`) is
   damage-driven. Which one this device takes is not known from source; `WLR_DEBUG` prints
   `Direct scan-out enabled/disabled` if the parent wants to know.
7. **Xlorie copies only the update region.** `present_execute_copy` calls
   `present_copy_region(window, pixmap, vblank->update, ...)` (`termux-x11/app/src/main/cpp/xserver/present/present_execute.c:82`),
   which installs `update` as the scratch GC's clip region and runs `CopyArea` of the whole
   pixmap through it (`present/present.c:66-96`); an empty region clips everything away. The
   copy is damage-tracked into `pvfb->damage`, and `lorieRedraw` only wakes the renderer thread
   when that region is non-empty or the cursor changed (`termux-x11/app/src/main/cpp/lorie/InitOutput.c:412-444`).
   So empty-damage frames should also stop waking the renderer thread (the parent measured
   about 8 % of a core there): an expectation to confirm, not a measurement. Present does not
   flip for these pixmaps: `loriePresentFlip` declines a pixmap without an
   AHardwareBuffer/FD buffer (`InitOutput.c:796-804`), and a root-size change recreates the root
   pixmap and copies the old contents (`InitOutput.c:515-555`).

Corrections to the brief's premises, both small: (a) the frame callback is delivered by cage
*committing an idle frame* (a Present with an empty region), not by skipping it, so a 60 Hz
idle loop of cheap Presents remains with VFR off; (b) with the pixman renderer the scene may
composite instead of scanning out, which changes who copies but not the damage contract.

## Host proof

- Patch applies on the pinned revision and the whole library builds under clang in the guest
  image (host, qemu-user): `rootfs/build-aquamarine.sh` run in a fresh work dir
  (`OMDROID_AQUAMARINE_WORK=<scratch>/work`), exit 0, `ABI OK`. Its printed table (**measured**, host):

  ```
  SONAME:        libaquamarine.so.13 -> libaquamarine.so.13
  NEEDED:        identical (18 entries)
  strong symbols: 972 -> 1106 (+134)
  all symbols:   1673 -> 1789 (weak instantiations differ by compiler)
  consumer:      Hyprland + hyprctl import 47 aquamarine symbols, 0 missing
  GLIBC max:     2.38 -> 2.38 (the image has 2.43)
  sha256:        35a9ffd4c565364900a13c53fee935898c5885bd2508c527228b752d316d1562
  size:          1775920 bytes
  ```

  The build log has no `error` line and no warning from the lines patch 0003 adds (the two
  `Wayland.cpp` warnings are the existing unused lambda captures in `initDmabuf`).
- The library carries the feature: `strings` finds `AQ_WAYLAND_FULL_DAMAGE`, `commit damage {} rect(s){}`
  and ` (whole surface)`; `readelf -d` shows SONAME `libaquamarine.so.13` and no RPATH/RUNPATH.
- Installed as `rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13` (mode 644, 1 775 920 bytes,
  sha256 as above, 752 bytes larger than the 0002-only library `8514d2a6...`). The overlay
  file name is unchanged, so `syncGuestOverlay`, the packager's overlay block and the overlay
  directory still name the same files.
- **Not run:** a functional test of the damage rectangles. The mock-parent harness of
  `references/guest-library-builds.md` (a libwayland-server parent that logs `wl_surface.damage_buffer`)
  would need a render path, which the qemu-user client cannot give (it segfaults once the swapchain is
  touched). The rectangle logic was checked by reading and by compiling, not by running; the device
  A/B below is the first run of it.

## Device A/B plan (the parent runs it, PENDING)

(filled in below)

## Stretch: why VFR drops the last frame

(filled in below)

## Risks

(filled in below)

## What I did not do

No adb, no device, no Kotlin, no `start.sh`, no packager, no Hyprland or cage change.
