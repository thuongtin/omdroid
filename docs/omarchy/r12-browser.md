# R12: Chromium-family browsers launch in the session

Measured and fixed on the tablet, 2026-11-27. The trigger was Brave, but the cause is
the whole Chromium family, so the fix covers the family.

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

Chromium's setuid sandbox wants a helper owned by root with mode 4755, and its zygote wants user
namespaces. Neither exists inside proot. The image's two helpers each fail the check for a
different reason:

| helper | mode | owner | why it fails |
| --- | --- | --- | --- |
| `/opt/brave-bin/chrome-sandbox` | `-rwsr-xr-x` | `omarchy` | the setuid bit is there, but the owner is the session user, never root |
| `/usr/lib/chromium/chrome-sandbox` | `-rwx------` | `omarchy` | no setuid bit at all |

So this is not a Brave defect: any Chromium-family binary started bare in this session dies the
same way. Chromium appears to work only because Omarchy's launcher hard-codes the flags in its
proot branch:

```
omarchy-launch-browser:  exec chromium --no-sandbox --disable-dev-shm-usage --password-store=basic ...
```

That is a per-app fix of the same shape, for one app.

## The fix, one launcher for the family

`complete/bin/chromium-proot` takes the name it was called by, so one file serves every member:

```
name=${0##*/}
exec "/usr/bin/$name" --no-sandbox --disable-dev-shm-usage --password-store=basic "$@"
```

The complete hook links it into `/usr/local/bin` for each name the image actually has (`brave`,
`chromium`, `google-chrome-stable`, `microsoft-edge-stable`, `vivaldi-stable`, `opera` are tried;
only present ones are linked). `/usr/local/bin` comes before `/usr/bin` in the session PATH, so a
desktop entry's `Exec=brave %U`, the Omarchy menu, `omarchy-launch-browser` and a plain `brave` in
a terminal all get the flags. Adding a browser to the image needs no code change.

Switch: `OMDROID_COMPLETE_BROWSER=0` keeps the image launchers (`OMDROID_COMPLETE=0` turns it off
with the rest of the hook).

## What stays per-app, and what cannot be fixed

- **Electron apps** do not read a wrapper: they honour `ELECTRON_DISABLE_SANDBOX=1` from the
  environment. The image has none installed; if one is added, that variable belongs in the session
  environment rather than in this launcher.
- **The sandbox itself cannot be made to work here.** It needs a root-owned 4755 helper and
  unprivileged user namespaces; proot fakes uid 0 for the process, not for file ownership or
  namespace creation. Running with the sandbox off is the correct trade inside this session, and it
  is what Omarchy itself does under proot.

## Measured on the tablet

| step | result |
| --- | --- |
| bare `brave`, before | aborts with the sandbox FATAL, no window; processes die |
| bare `brave`, after | a full Brave window (tab strip, address bar, new-tab page), 8-10 processes alive at 45 s |
| both family members linked | `/usr/local/bin/brave` and `/usr/local/bin/chromium` point at `complete/bin/chromium-proot` |
| which display it uses | Wayland on the session's own socket (`wayland-1`, Hyprland); the `drmGetDevices2`, udev and dbus errors in its log are benign here |

The "quit unexpectedly" dialog that still appears is Brave's own record of the earlier crashed
launches; "Don't ask again" clears it.

## Host gate

`docs/omarchy/tools/complete-hook-test.sh` covers the links against a fake `/usr/bin`: an installed
browser is linked to the launcher, a second family member shares it, a name the image lacks is not
linked, and the switch off removes them.

## Not verified

- `chromium` launched through the link was not opened to a page; only its `--version` was checked.
  It already worked via Omarchy's own flags, which the launcher duplicates.
- A cold start carrying this fix: no APK with it has been built yet, so the links in the running
  session came from running the hook by hand.
