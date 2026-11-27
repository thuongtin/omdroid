# R12: Brave launches in the session

Measured and fixed on the tablet, 2026-11-27.

## The symptom

Launching Brave from its own entry in the session failed: no window, and the next launch showed
"Brave Browser quit unexpectedly".

## The cause, measured

A bare `brave` aborts before it draws anything:

```
FATAL:sandbox/linux/suid/client/setuid_sandbox_host.cc:172] The SUID sandbox helper binary was
found, but is not configured correctly. Rather than run without sandboxing I'm aborting now.
You need to make sure that /opt/brave-bin/chrome-sandbox is owned by root and has mode 4755.
```

`chrome-sandbox` needs to be root-owned with mode 4755, which nothing inside proot can be. Every
launch therefore died at start-up, and Chromium's crash reporter carried the evidence into the
next window. The image's own Chromium is not exposed to this because Omarchy's launcher already
starts it with the sandbox off in its proot branch (`omarchy-launch-browser`:
`exec chromium --no-sandbox --disable-dev-shm-usage --password-store=basic ...`).

## The fix

`complete/bin/brave`, a launcher that execs `/usr/bin/brave` with the same three flags, linked into
`/usr/local/bin` by the complete hook. `/usr/local/bin` comes before `/usr/bin` in the session
PATH, so a desktop entry's `Exec=brave %U`, the Omarchy menu and a plain `brave` in a terminal all
get them.

```
brave --no-sandbox --disable-dev-shm-usage --password-store=basic "$@"
```

Switch: `OMDROID_COMPLETE_BROWSER=0` keeps the image's launcher (`OMDROID_COMPLETE=0` turns it off
with the rest of the hook).

## Measured on the tablet

| step | result |
| --- | --- |
| bare `brave`, before | aborts with the sandbox FATAL, no window; 0 or dying processes |
| bare `brave`, after the link | a full Brave window (tab strip, address bar, new-tab page), 10 processes alive at 45 s |
| `command -v brave` after the hook | `/usr/local/bin/brave` |
| which display it uses | Wayland on the session's own socket (`wayland-1`, Hyprland); the `drmGetDevices2` and dbus errors in its log are benign here |

The "quit unexpectedly" dialog that still appears is Brave's own record of the earlier crashed
launches; "Don't ask again" clears it.

## Host gate

`docs/omarchy/tools/complete-hook-test.sh` covers the link: it is present with the switch on and
gone with the switch off.

## Not verified

- Chromium through the same launcher path was not re-tested; it was already working.
- A cold start carrying this fix: no APK with it has been built yet, so the link in the running
  session came from the hook being run by hand.
