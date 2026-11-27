# r12: the extra-key bar is summoned, not restored

Termux:X11's extra-key bar (the "X11 footer") now starts hidden in every session and is summoned by
a small floating keyboard button in the bottom-left corner of the X view; tapping the same button
hides it again. The bar is an overlay: with Termux:X11's `adjustHeightForEK` preference off (the
default, and the only value this app writes), showing it draws the keys over the bottom of the
desktop instead of shrinking it. The X root is the full window on every display and the host
reserves no bottom gap.

## What changed

**termux-x11** (`feat/extra-keys-pill`):

- `MainActivity` keeps the bar's state in a session field, `extraKeysVisible`, that starts `false`.
  `setTerminalToolbarView()` no longer restores the saved `additionalKbdVisible` preference. The
  preference is still written when the user toggles the bar (the settings screen's hidden switch
  keeps its meaning), but nothing reads it to decide visibility at launch or resume. Every path
  that could previously show the bar from the stored preference — `onCreate`'s
  `toggleExtraKeys(false, false)`, `onResume`, `onConfigurationChanged`,
  `onPreferencesChangedCallback` (the preference listener) and `clientConnectedStateChanged` — now
  goes through that field.
- New `@+id/extra_keys_button`: a 36 dp `ImageButton` in the root `FrameLayout`, bottom-left
  (`layout_gravity="bottom|start"`, 4 dp margins), a translucent dark circle
  (`drawable/extra_keys_button_bg.xml`) with a keyboard glyph drawn as a vector
  (`drawable/ic_extra_keys.xml`, no binary asset), content description `Show or hide the key bar`.
  It calls `toggleExtraKeys()`, so the same button shows and hides the bar. Its visibility follows
  the surface (`LorieView.connected()`), it is hidden in picture-in-picture, and while the bar is
  shown it is lifted above it so the keys never cover it.

**app**:

- `DockMonitor` no longer writes `showAdditionalKbd` / `additionalKbdVisible`: the bar is not a
  dock-driven affordance any more. Everything else about docking (UI mode file, UI scale, moving the
  session onto the monitor) is unchanged.
- `DisplayGeometry` no longer reserves the bar's height. `extraKeysShown`, `extraKeyRows` and the
  density input were dead once the bar stopped taking space and were removed;
  `XGeometry.bottomGap` is always 0 and the launcher passes 0 padding to the X activity on both
  displays.
- `docs/omarchy/launch-contract.md` sections 1, 3, 5 and the dock section follow the change.
