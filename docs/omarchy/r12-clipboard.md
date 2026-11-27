# R12: the clipboard bridge

Built and measured on the tablet, 2026-11-27. Text only, 1 MiB cap.

## The gap this closes

R11 measured it (section 5 of `r11-completeness.md`): under cage nothing turns a Wayland data
offer into an X selection, so the two clipboards were separate worlds. `printf x | wl-copy` then
`wl-paste` worked inside Hyprland, while an X client on `:0` read `CLIPBOARD owner=0x0` before and
after. Android only ever talks to the X side, so nothing crossed in either direction.

Xlorie is the half that talks to Android: when an X client takes CLIPBOARD it asks that client for
TARGETS and the text and forwards both to Android, and when Android copies it takes the selection
itself and answers conversions (`termux-x11/app/src/main/cpp/lorie/clipboard.c`,
`lorieSelectionCallback`, `lorieProcConvertSelection`). There was simply no X client on the guest
side of that conversation.

## What was built

`rootfs/overlay/etc/phoshdroid/complete/omdroid-clipboard.py`, one process, `libX11` and
`libXfixes` through `ctypes` (the same approach as `fit-x11.py`), started by
`complete/session-start.sh`:

| direction | how |
| --- | --- |
| guest to Android | `wl-paste --watch` runs a command per change, which drops the text into `/tmp/omdroid-clipboard.dat` with an atomic rename; the bridge takes CLIPBOARD on `:0` with its own window and answers `TARGETS`, `UTF8_STRING`, `STRING`, `TEXT` and `text/plain;charset=utf-8`. Xlorie then forwards it to Android. |
| Android to guest | XFixes reports each CLIPBOARD owner change; an owner that is not the bridge means someone else (Xlorie, after an Android copy) holds text. The bridge converts it, reads the property and runs `wl-copy`. |

Details that cost a round each and are worth keeping:

- **`wl-paste --watch` takes a command, not a stream.** `wl-paste --watch` with no argument exits
  (option requires an argument), and the offered type here is plain `STRING`, not
  `text/plain;charset=utf-8`. The file-and-rename sink above sidesteps both: no framing problem for
  multi-line text and no half-written read.
- **Hyprland's socket is not the one `start.sh` exports.** `start.sh` sets
  `WAYLAND_DISPLAY=wayland-omarchy` for cage, but the session's clipboard lives on Hyprland's own
  socket, `wayland-1` (quickshell's environment shows it). The bridge therefore tries
  `$WAYLAND_DISPLAY` and then every `wayland-*` socket in `XDG_RUNTIME_DIR`, newest number first,
  and keeps the first one where `wl-paste` stays alive.
- **The loop guard needs both sides of the memory.** Pushing an X copy into Wayland makes
  `wl-paste --watch` fire with that same text; the bridge records it as also-set-on-X, so it does
  not take the X selection back and hand Xlorie the same clipboard again. Before that, a log showed
  `x -> wayland` immediately followed by `wayland -> x`.
- **Start order.** The hook runs before cage starts, so the bridge waits for `:0` (60 s) and for a
  Wayland socket that accepts `wl-paste` (60 s), and re-starts the watch if Hyprland restarts under
  it.
- **Both halves must use the same compositor.** `wl-copy` inherited the hook's
  `WAYLAND_DISPLAY=wayland-omarchy` (cage) and wrote the text into cage's clipboard, so Hyprland's
  stayed empty while the log said the copy had succeeded and `wl-paste` answered "Nothing is
  copied". `wl-copy` now gets the display the watch found.
- **`wl-copy` must not be waited on.** It can serve the selection in the foreground, and a blocking
  wait stalled the loop that notices the next Android copy: measured as a 4 s delay between the
  ownership change and the conversion. It is started, handed the text and left running now, with
  the handles kept so it cannot become a zombie.

Switch: `OMDROID_COMPLETE_CLIPBOARD=0` in `~/.config/omdroid/session.env` (or
`OMDROID_COMPLETE=0` for the whole hook). Pid in `~/.local/state/omdroid/complete/clipboard.pid`,
log in `/tmp/omdroid-clipboard.log` (verbose with `OMDROID_CLIPBOARD_DEBUG=1`).

## Measured on the tablet

Session on the tablet, build with the files pushed in (13:49-13:50), bridge started by the hook
itself (`complete: clipboard: bridge started (pid 26893)`):

| check | command | result |
| --- | --- | --- |
| guest to X | `printf guest-text-A \| wl-copy`, then `clipboard-x.py read` | `owner=0x800001`, `text='guest-text-A'` (the owner was `0x0` before this work) |
| Xlorie collects it | bridge log | `x: answered TARGETS for 0x511`, `x: answered 12 chars for 0x511` — 0x511 is Xlorie's window, so the Android half fired unasked |
| X to guest | `clipboard-x.py write android-text-B 8` (stands in for Xlorie), then `wl-paste --no-newline` | `android-text-B`; log shows `x: CLIPBOARD owner=0xa00001`, `x -> wayland: 14 chars` |
| no echo | same run | `x -> wayland: 19 chars` with no following `wayland -> x` |
| cold start | final build of this branch (1,124,829,394 B, `sha256 6c0f06f7...`), installed 14:04:09, then one force-stop and start | the hook started the bridge by itself: `complete: clipboard: bridge started (pid 3503)`; the log shows `wayland: watching wayland-1` with no `WAYLAND_DISPLAY` in the environment; guest to X gave `owner=0x600001 text='cold3-A'` and X to guest gave `wl-paste: cold3-B`, both logged inside the same session |
| speed | probe takes CLIPBOARD, `wl-paste` polled every 0.5 s | conversion inside the first poll: `x -> wayland: 8 chars` logged within 0.5 s of the ownership change |

`clipboard-x.py` is the probe in `docs/omarchy/tools/`: `read` prints the owner and the text,
`write TEXT [SEC]` takes CLIPBOARD with that text and answers conversions for SEC seconds, which is
exactly what Xlorie does for an Android copy.

## Host gate

`docs/omarchy/tools/complete-hook-test.sh`: 41 checks, all pass, four of them new — the switch on
starts the bridge, the process is alive, the switch off stops it, and the process is gone.

## Not verified

- **A human copy on Android.** The direction was proven by driving the X side the way Xlorie does,
  and Xlorie collected the guest-to-Android text on its own, but no finger has selected text in an
  Android app and pasted it in the guest yet.
- **Images and rich content.** Text only; anything that needs INCR transfer is capped at 1 MiB.
- **PRIMARY selection.** Only CLIPBOARD is bridged, which is what Android and `wl-copy` use.

## Files

- `rootfs/overlay/etc/phoshdroid/complete/omdroid-clipboard.py` — the bridge.
- `rootfs/overlay/etc/phoshdroid/complete/session-start.sh` — the new part and its switch.
- `docs/omarchy/tools/clipboard-x.py` — the X-side probe used above.
- `docs/omarchy/tools/complete-hook-test.sh` — four checks for the start/stop switch.
