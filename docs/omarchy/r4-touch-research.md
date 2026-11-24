# R4 touch research: where a tap on the Omarchy bar is lost

Read-only source study of every hop between an Android `MotionEvent` and a Quickshell bar item.
Every claim names what I read (file:line, or a URL pinned to the version in use). Anything I did not
read is marked **guess**.

**Verdict: the tap survives Android and X, reaches cage, and dies in aquamarine.** Under `cage` the
guest's Hyprland is a *Wayland client*, so its input comes from aquamarine's **Wayland** backend — and
aquamarine 0.14.0's Wayland backend has no touch support at all. Hyprland therefore has **no touch
device**, so the tap is dropped before Qt or QML ever see it. Nothing downstream (Hyprland's layer
routing, Qt's touch→mouse synthesis, the QML items) is at fault, and nothing above cage is either.

Versions in use: cage **0.3.1-1**, wlroots0.20 **0.20.2-1**, libliftoff 0.5.0-1
(`rootfs/package-omarchy-rootfs.sh:101-118` — these three are downloaded, not in the guest's package
DB); Hyprland **0.56.1-3**, aquamarine **0.14.0-2**, qt6-base **6.11.2-3**, qt6-declarative
**6.11.2-1**, qt6-wayland **6.11.2-1**, quickshell **0.3.1-1**, wayland 1.26.0-1, libinput 1.31.3-1,
xorg-xwayland 24.1.13-1 (`/tmp/omarchy-members.txt`, `./var/lib/pacman/local/`).

---

## Ranked hypotheses

### H1 — LEADING: aquamarine's Wayland backend never creates a touch device, so the nested Hyprland has none

The chain, each link read:

1. Xlorie delivers the tap as **XI2 touch**, not as a click. `lorie/InitInput.c:145-179` builds
   `lorieTouch` as `XI_TOUCHSCREEN` / "Lorie touch" with
   `InitTouchClassDeviceStruct(device, 20, XIDirectTouch, 2)`; `InitInput.c:284` attaches it to
   `inputInfo.pointer`.
2. Xlorie's server does have pointer emulation on (`xserver/dix/touch.c:45`
   `Bool touchEmulatePointer = TRUE;`, and `touch.c:147`
   `emulate_pointer = touchEmulatePointer && (t->mode == XIDirectTouch)`), **but** the emulated
   ButtonPress/Motion is only delivered to the touch *owner*:
   `xserver/Xi/exevents.c:1455-1456` — *"We don't deliver pointer events to non-owners"*, returning
   early unless `TouchResourceIsOwner(ti, listener->listener)`. Cage selects `XI_TouchBegin` on its
   window (next link), so cage is the owner: it gets touch events and **not** clicks. A tap does not
   reach the guest as a mouse press.
3. wlroots 0.20.2's X11 backend does produce a real touch device:
   `backend/x11/output.c:644-657` selects
   `XCB_INPUT_XI_EVENT_MASK_TOUCH_BEGIN | …_TOUCH_END | …_TOUCH_UPDATE` on the output window;
   `output.c:684-690` does `wlr_touch_init(&output->touch, &x11_touch_impl, "x11-touch")`,
   sets `output->touch.output_name`, and emits `events.new_input`;
   `backend/x11/input_device.c:221-277` translates `XCB_INPUT_TOUCH_BEGIN/END/UPDATE` into
   `wlr_touch` down/up/motion (`send_touch_down_event` etc., lines 70-105).
4. cage 0.3.1 forwards it: `seat.c:449` (`wlr_touch_from_input_device` → `handle_new_touch`),
   `seat.c:173-189` (attach to `seat->cursor`, map to the touch's `output_name`),
   `seat.c:501-521` (`handle_touch_down` → `wlr_cursor_absolute_to_layout_coords` → `view_at` →
   `wlr_seat_touch_notify_down`), and `seat.c:124` gates the seat's touch capability on
   `!wl_list_empty(&seat->touch)`. Cage's only client is Hyprland, fullscreen.
5. **aquamarine 0.14.0's Wayland backend has no touch code.**
   `src/backend/Wayland.cpp` at tag `v0.14.0` (878 lines, fetched from
   `raw.githubusercontent.com/hyprwm/aquamarine/v0.14.0/`): **0** occurrences of the string `touch`.
   `include/aquamarine/backend/Wayland.hpp` (197 lines): **0**. It declares `CWaylandBuffer`,
   `CWaylandOutput`, `CWaylandKeyboard`, `CWaylandPointer` — no `CWaylandTouch`. The payload's patched
   copy `<scratch>/omarchy/aq/Wayland.cpp` (930 lines) also has **0** (its patch,
   `patches/aquamarine/0001-wayland-carry-proven-Android-KGSL-buffer-pipeline.patch`, is
   buffer/presentation only). Touch exists in aquamarine only for the libinput/DRM path:
   `src/backend/Session.cpp` has 31 `touch` hits. `include/aquamarine/backend/Backend.hpp:20,153`
   declares `class ITouch` and the `newTouch` signal, so the interface exists — the Wayland backend
   simply never instantiates one.
6. Hyprland's only ingress is that signal: `src/Compositor.cpp:491-493`
   (`m_aqBackend->events.newTouch.listenStatic(... g_pInputManager->newTouchDevice(dev))`). Nothing on
   the nested path emits it, so no `CTouchDevice` is ever created.
7. That the **Wayland** backend is the one in use is not in doubt: aquamarine's default implementation
   options are `backendType(AQ_BACKEND_WAYLAND), backendRequestMode(AQ_BACKEND_REQUEST_IF_AVAILABLE)`
   (`src/backend/Backend.cpp:52`), and under cage `WAYLAND_DISPLAY` is set (`start.sh:20`) while there
   is no DRM/GBM node inside an Android app — `start.sh:48` sets `AQ_NO_KMS_REQUIREMENT=1` for exactly
   that reason.

Cheapest confirming test (the shell/session must be up). Note on tools: the guest image has
`hyprctl`, `jq`, `python3`, `xprop` and `xkbcli`, but **not** `xinput`, `xdotool`, `wayland-info`,
`wev`, `xev` or `libinput` (checked against the image's file list, `/tmp/omarchy-members.txt`) — so
do not plan an `xinput list` check, it is not installable without network work.

```sh
# A. Does Hyprland have a touch device? (empty "touch" array = H1 confirmed)
hyprctl -j devices | python3 -c 'import json,sys; d=json.load(sys.stdin); print("touch:", [t["name"] for t in d["touch"]]); print("mice:", [m["name"] for m in d["mice"]])'
#   the JSON always carries a "touch" key, filled from g_pInputManager->m_touches
#   (Hyprland v0.56.1 src/debug/HyprCtl.cpp:833-845) — expect empty
# B. Did the signal ever fire? Hyprland logs "New aquamarine touch with name {}" from
#    src/Compositor.cpp:492 on every newTouch (DEBUG level, so /etc/phoshdroid/trace must exist —
#    start.sh:72-75 turns on HYPRLAND_TRACE=1 AQ_TRACE=1). Its log file is
#    $XDG_RUNTIME_DIR/hypr/<instance>/hyprland.log (src/debug/log/Logger.cpp:29; hyprlandd.log on
#    debug builds):
grep -i "aquamarine touch" "$XDG_RUNTIME_DIR"/hypr/*/hyprland*.log 2>/dev/null; echo "(empty = never fired)"
# C. Is the guest side of the config off? (the only Omarchy-side touch kill switch)
hyprctl getoption input:touchdevice:enabled
ls ~/.local/state/omarchy/toggles/hypr/   # only a *-disabled-name file here disables a device (H2)
```

Refuting observation: `hyprctl devices` lists a touch device. Then go to H2.

Fix implied, cheapest first:

- **(a) Patch aquamarine's Wayland backend to bind `wl_seat.get_touch` and emit `newTouch`.** Mirror
  what `CWaylandPointer` already does in `src/backend/Wayland.cpp` (bind, `setMotion`/`setButton`/
  `setAxis` handlers) with a `CWaylandTouch : public ITouch` (down/up/motion/frame → `ITouch::SDownEvent`
  /`SUpEvent`/`SMotionEvent`, which is what `onTouchDown` consumes, see hop 4). The payload already
  carries an aquamarine patch and re-pins the package in `rootfs/package-omarchy-rootfs.sh:101-118`,
  so this fits the existing build. Cost: a C++ change + a repack, no host/guest contract change.
- **(b) Switch the host to simulated touch** — `touchMode = "2"`, and note the current code is
  `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt:543`
  (`.putString("touchMode", "3")`), rewritten into shared preferences on **every** launch, so a user
  cannot pick mode 2 from the app's own settings; the line has to change. Then the tap arrives in the
  guest as X pointer events, which cage → Hyprland → Qt already handle today. This is the only
  no-repack route, and it is what the sibling can A/B on the device in minutes.
- **(c) Guest-side workaround: none exists.** A device that was never created cannot be enabled with
  `hyprctl`/`input:touchdevice`. Do not spend time there.

### H2 — refuted by source (only reachable if H1 is): Hyprland would not route a bar tap

Hyprland 0.56.1 does handle layer surfaces on touch-down:
`src/managers/input/Touch.cpp:17-118` (`onTouchDown`) resolves `m_foundLSToFocus` and, when the point
is on a layer surface, computes `local = TOUCH_COORDS - m_touchData.touchFocusLS->m_geometry.pos()`
(line 111) and calls `g_pSeatManager->sendTouchDown(touchFocusSurface, e.timeMs, e.touchID, local)`
(line 117). It also checks `layerPopupSurfaceAt` first (line 106). Two gotchas worth ruling out on the
device if a touch device ever appears:

- `gestures:workspace_swipe_touch` (`Touch.cpp:20`) can turn an edge-originating touch into a
  workspace swipe — but only for `m_foundLSToFocus->m_layer <= 1` (`Touch.cpp:57`), i.e. background/
  bottom layers, so a **top-layer** bar (the Omarchy bar is `WlrLayershell.layer: WlrLayer.Top`,
  `shell/plugins/bar/Bar.qml:1024`) is not swiped away. Check anyway:
  `hyprctl getoption gestures:workspace_swipe_touch`.
- The Omarchy config *can* disable a touchscreen, but only by stored device name:
  `default/hypr/toggles.lua:19-21` calls `disabled_input_device("touchscreen")`, which
  (`default/hypr/disabled-input-device.lua:10-20`) returns immediately unless
  `~/.local/state/omarchy/toggles/hypr/touchscreen-disabled-name` exists and then does
  `hl.device({ name = <that>, enabled = false })`. So it is **not** off by default. Cheap check:
  `ls ~/.local/state/omarchy/toggles/hypr/`.

### H3 — refuted by source (only reachable if H1/H2 are): Qt/Quickshell never turns the touch into a click

Qt Quick does its own touch→mouse synthesis. `qtdeclarative` v6.11.2
`src/quick/util/qquickdeliveryagent.cpp:1791` — *"We generally don't want OS-synthesized mouse events,
because Qt Quick does its own touch->mouse synthesis"* — and `:2594` — *"If the touch event wasn't
accepted, synthesize a mouse event and see if the item wants it"*. The bar items are plain
`MouseArea`s: `shell/Ui/WidgetButton.qml:95-101` (`acceptedButtons: Qt.LeftButton | Qt.RightButton |
Qt.MiddleButton`, `hoverEnabled: true`), and the widgets that matter wire `onPressed`
(`plugins/bar/widgets/Workspaces.qml:68` `onPressed: function() { root.focusWorkspace(modelData) }`,
`plugins/bar/widgets/Tray.qml:826`, `plugins/bar/indicators/*.qml`). Hover only drives tooltips and
reveal visuals (`WidgetButton.qml:61 tooltipHovered = … mouseArea.containsMouse`), not the click. So a
synthesized left press lands on `onPressed` and the workspace switches / the menu opens.

### H4 — no relay inside X drops it

Cage's X11 output window selects the touch masks (`backend/x11/output.c:644-657`), so cage is a touch
listener and `handleTouchEvent` delivers (`lorie/cmdentrypoint.c:236-268`). The guest image has no
XI2-listing tool (`xinput` is not installed), so this hop is checked indirectly: an empty
`hyprctl -j devices` touch array **plus** the pointer path proven healthy by the `touchMode = "2"` A/B
(see the end) leaves no other candidate than the touch handoff.

### H5 — no separate fifth suspect: whatever H1's tests show names the hop

If `hyprctl -j devices` has no `touch` entry and the mode-2 A/B proves the pointer path healthy, the
drop is exactly hop 4 (aquamarine) and nothing else needs looking at. If a touch device *is* listed,
look at H2 (config/toggle) and then hop 5 (Qt/QML) — both are already refuted at source, so a listed
device would most likely mean a different build than the one documented here, not a hidden bug.

---

## Per hop

### Hop 1 — Android `MotionEvent` → Termux:X11 (runs in-process)

- `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt:543` writes
  `.putString("touchMode", "3")` on every launch (forced, not a default — see H1 fix (b)).
  `3` is `InputMode.TOUCH` (`TouchInputHandler.java:60-67`), and `setInputMode` maps TOUCH →
  `InputStrategyInterface.NullInputStrategy` (`TouchInputHandler.java:377-390`).
- For a finger event with the null strategy, the handler sends the raw `MotionEvent` as touch and
  skips the strategy: `TouchInputHandler.java:314-317`
  (`mInjector.sendTouchEvent(event, mRenderData)`).
- `InputEventSender.sendTouchEvent` (`InputEventSender.java:107-158`) emits, per Android event:
  - `ACTION_MOVE` → one `XI_TouchUpdate` (19) per pointer **whose position changed**; identical
    positions are skipped (lines 124-133) and the phantom upstream `XI_TouchEnd` loop was removed
    (comment lines 136-140) — the AGENTS.md dedup note.
  - `ACTION_DOWN` / `ACTION_POINTER_DOWN` → one `XI_TouchUpdate` first, then `XI_TouchBegin` (18)
    (lines 149-152).
  - `ACTION_UP` / `ACTION_POINTER_UP` / `ACTION_CANCEL` → `XI_TouchUpdate`, then `XI_TouchEnd` (20).
  - **No mouse button, cursor move or wheel event is sent anywhere in this path.**
- A tap therefore reaches X as TouchBegin+TouchEnd only, and the tap the gesture detectors recognise
  is thrown away: `NullInputStrategy.onTap(int)` is an empty body
  (`InputStrategyInterface.java:50-56`).
- The AGENTS.md "`moveCursorToScreenPoint` disabled on Direct-Touch" note is
  `TouchInputHandler.java:561-568` (it acts only for `TrackpadInputStrategy` /
  `SimulatedTouchInputStrategy`) plus the explanatory comment at `TouchInputHandler.java:656-663`.
- JNI: `termux-x11/app/src/main/cpp/lorie/activity.c:316-321` (`sendTouchEvent` → `EVENT_TOUCH` on
  `client_conn_fd`), i.e. the app hands the event to Xlorie inside the APK.

### Hop 2 — Xlorie X server → X clients

- Device: `lorie/InitInput.c:272-284` (`AssignTypeAndName(lorieTouch, … XI_TOUCHSCREEN …, "Lorie touch")`,
  `AttachDevice(NULL, lorieTouch, inputInfo.pointer)`), class at `InitInput.c:145-179`
  (`InitTouchClassDeviceStruct(device, 20, XIDirectTouch, 2)`, 2 absolute axes over 0..0xFFFF, one
  button). Direct touch, normalised to the screen.
- Delivery: `lorie/cmdentrypoint.c:236-268` — drops a `TouchUpdate` whose position equals the stored
  one (247-252), promotes a `TouchUpdate` with no active point to `TouchBegin` (254-256), drops an
  orphan `TouchEnd` (258-259), then `QueueTouchEvents(lorieTouch, …)` (263).
- Pointer emulation: on (`dix/touch.c:45`, `:147`), but delivered **only to the touch owner**
  (`Xi/exevents.c:1455-1456`), and the touch owner here is the client that selected `XI_TouchBegin`
  on the window — cage. Consequence: cage receives touch events instead of clicks; a tap is not
  duplicated as a pointer press.
- Expected on the device: no tool in the image can list XI2 devices, but the device is built
  unconditionally (`InitInput.c:272-284`), so its existence is not in question; what the A/B below
  tests is whether a tap arrives in the guest as a click (mode 2) or not at all.

### Hop 3 — cage (wlroots 0.20.2, `WLR_BACKENDS=x11`) as an X client

- cage is launched by `rootfs/overlay/etc/phoshdroid/start.sh:69` `export WLR_BACKENDS=x11`
  (renderer pixman, line 70), `exec cage -- /etc/phoshdroid/session-child.sh` (line 110).
- wlroots creates the touch: `backend/x11/output.c:684-690`
  (`wlr_touch_init(&output->touch, &x11_touch_impl, "x11-touch")`, `output_name`, emit `new_input`);
  event masks selected at `output.c:644-657`.
- Translation: `backend/x11/input_device.c:70-105` (send_touch_down/motion/up) and `:221-277`
  (XCB_INPUT_TOUCH_BEGIN/END/UPDATE dispatch, with a `wlr_x11_touchpoint` map between the X touch id
  and the Wayland touch id; coordinates `ev->event_x >> 16` relative to the output window).
- cage consumes it: `seat.c:449`, `:173-189`, `:501-521` (see H1 link 4). `wlr_seat_touch_notify_down`
  needs the client to have bound `wl_touch` — Hyprland's aquamarine does not, so the touch is offered
  and not taken.
- Cage does **not** filter, disable or reinterpret touch. `map_input_device_to_output`
  (`seat.c:189`) only binds it to an output by name.

### Hop 4 — Hyprland 0.56.1 nested (aquamarine 0.14.0 Wayland backend), and what it would do with a touch

- Ingress is single: `src/Compositor.cpp:491-493` (`newTouch` → `g_pInputManager->newTouchDevice(dev)`);
  `hypr/Compositor.cpp` in the payload scratch is the same file, same lines.
- aquamarine 0.14.0's Wayland backend provides only `CWaylandBuffer`, `CWaylandOutput`,
  `CWaylandKeyboard`, `CWaylandPointer` (`include/aquamarine/backend/Wayland.hpp:19-119`); the pointer
  handlers in `src/backend/Wayland.cpp` (`pointer->setMotion/setButton/setAxis`) are the template a
  touch implementation would follow. There is no `wl_touch` binding anywhere in it, so
  `events.newTouch` is never emitted: **the nested Hyprland has no touch device at all.**
- If it had one, the routing to a bar tap is correct:
  `src/managers/input/Touch.cpp:17-118` — `onTouchDown` refocuses at the touch point (line 44),
  resolves the layer surface under it (line 87, 106-113) and sends `wl_touch.down` to it (line 117);
  `onTouchUp` at line 120. Top-layer surfaces are exempt from the workspace-swipe path (line 57).
- Hyprland's `input:touchdevice:*` options and the Omarchy config: `default/hypr/input.lua:64` only
  configures `touchpad`, and nothing under `default/hypr/` disables touch unless the state file from
  H2 exists. `hyprctl getoption input:touchdevice:enabled` for the live value.

### Hop 5 — Quickshell 0.3.1 (Qt 6.11.2) and the bar QML

- The bar is a Quickshell `PanelWindow` on the top layer: `shell/plugins/bar/Bar.qml:989`, `:1024`
  (`WlrLayershell.layer: WlrLayer.Top`).
- Items are `WidgetButton` (`shell/Ui/WidgetButton.qml:95-101`: `MouseArea` filling the parent,
  `acceptedButtons: Left|Right|Middle`, `hoverEnabled: true`), and the actions hang off `onPressed` /
  `onClicked`: `plugins/bar/widgets/Workspaces.qml:68` (workspace number → `root.focusWorkspace`),
  `plugins/bar/widgets/Tray.qml:818-848` (tray icons), `plugins/bar/indicators/*.qml`
  (`onPressed: root.toggle()`), `plugins/menu/BarWidget.qml` for the Omarchy button.
- Qt turns an unaccepted `wl_touch` into a synthesized mouse press:
  `qtdeclarative` v6.11.2 `src/quick/util/qquickdeliveryagent.cpp:1791` and `:2594`. A synthesized left
  press satisfies the `MouseArea`, so `onPressed` fires. Hover is only for tooltip/reveal
  (`WidgetButton.qml:61`), not for the click.
- **Conclusion for this hop: nothing here needs changing.** If the bar still ignores taps after a
  touch device exists, the test is a tap while `WAYLAND_DEBUG=1` runs on the shell: look for
  `wl_touch.down` arriving at the layer surface's seat.

---

## The simulated-touch fallback (`touchMode = "2"`): what it costs

`SIMULATED_TOUCH = 2` → `InputStrategyInterface.SimulatedTouchInputStrategy`
(`TouchInputHandler.java:64-66`, `:377-390`). The app sends **mouse** input derived from the finger,
through the same `InputEventSender`:

- **Tap** — `GestureListener.onTap` (`TouchInputHandler.java:677-693`): checks the point is inside the
  image (`screenPointLiesOutsideImageBoundary`), moves the X cursor to it
  (`moveCursorToScreenPoint`, active for this strategy, `:561-568`), then
  `mInputStrategy.onTap(button)` → ButtonPress+Release at the cursor
  (`SimulatedTouchInputStrategy.onTap`). One finger = left, two = right, three = middle
  (`mouseButtonFromPointerCount`, `:739-750`); a double-tap is split by
  `ViewConfiguration.getDoubleTapTimeout()` (the `mLastTapTimeInMs` / `mDoubleTapSlopSquareInPx` logic in
  `InputStrategyInterface.java:73-120`).
- **Drag** — `onLongPress` (`:722-736`) → `onPressAndHold` (button down) and `mIsDragging = true`;
  every subsequent move re-anchors the cursor to the finger
  (`:656-663` — the branch deliberately *not* taken in direct-touch mode) and the release ends the
  button. Net effect in the guest: press, drag, release at the finger.
- **Two-finger gesture** — `SwipeDetector` classifies swipe vs pinch (`:633-644`); a pinch/swipe calls
  `mInputStrategy.onScroll(...)` → a mouse **wheel** event (`sendMouseWheelEvent`); a real 2-finger tap
  is a right click; a 3-finger drag is a swipe action (`onSwipe`, `:571-582`).

What switching to `2` costs: taps become real clicks and the bar would work **today with no guest
change**, but the guest loses true multi-touch (pinch inside apps becomes wheel scroll), drag/text
selection becomes the long-press simulation, and the X cursor now moves on every tap — the exact
behaviour direct-touch was adopted to avoid (AGENTS.md / `TouchInputHandler.java:656-663`).

---

## Cheapest tests, in order (for the device-side sibling)

1. `hyprctl -j devices` → empty `touch` array **confirms H1** (no touch device in Hyprland). This is
   the decisive one; the JSON key always exists (HyprCtl.cpp:833-845).
2. Hyprland's own log: `grep -i "aquamarine touch" $XDG_RUNTIME_DIR/hypr/*/hyprland*.log` — the
   `newTouch` debug line never appears (Compositor.cpp:492; needs `/etc/phoshdroid/trace` for DEBUG).
   Consistent with H1.
3. `hyprctl getoption input:touchdevice:enabled` and `ls ~/.local/state/omarchy/toggles/hypr/` — rule
   out an Omarchy-side disable (H2). Both need only what the image ships.
4. A/B for the fix decision (needs an APK rebuild, one line): change
   `app/src/main/kotlin/com/phoshdroid/app/LauncherActivity.kt:543` to `"2"` and tap the workspace
   numbers. If they switch, the entire guest side (cage → Hyprland → Qt → QML) is proven healthy and
   only the host→guest touch handoff is broken — i.e. aquamarine is the only thing left to patch.
   (Note the line is applied on **every** launch, so setting `touchMode` in Termux:X11's own
   preferences does not survive; it must be the code change.)

