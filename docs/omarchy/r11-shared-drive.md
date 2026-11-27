# R11 S3: a shared drive between Android and Omarchy

Branch `r11/shared-drive`, worktree `proot-post-r11-share`, base `90d7494`.
Brief: the round-11 share stream brief (kept with the round's scratch notes, not in the repo).

Evidence labels: **measured** (command given), **read** (file:line or URL), **estimated**.

## Status

| Step | State | Proof |
| --- | --- | --- |
| 1. Today's path on the device (`bind_sdcard`, `~/Phone`, both directions, time, media store) | PASS | Phase 1, both arms in the same minute. Bind off: `/home/omarchy/Phone` does **not exist** (the brief said "empty directory" - it is absent). Bind on: 35 top-level entries, guest writes land as uid 10298/group 1023 mode 0660 (dirs 2770), both directions work, cold start 10.3 s off vs 10.6-11.2 s on, a guest-written picture is **not** in the media store until `MEDIA_SCANNER_SCAN_FILE`. `<scratch>/share/phase1/step1.txt` |
| 2. The default rule as a pure function + unit tests | PASS | `storage/ShareRule.kt` + `ShareRuleTest` (5 tests, green in `:app:testDebugUnitTest`). Device, three arms on the new build: `mode=auto all-files=true -> bind=true`; `mode=on all-files=false -> bind=true` and the guest then sees only **10** of the 35 top-level entries (the media dirs; the app's own files are missing); `mode=auto all-files=false -> bind=false`. The deny needs `appops set --uid` - the package mode alone does not change `Environment.isExternalStorageManager()` |
| 3. Guest side: file-manager bookmark in `share/session-start.sh` | PASS | `rootfs/overlay/etc/phoshdroid/share/session-start.sh`; host dry run (add, idempotent, user line kept, user-edited label left alone, off removes only ours); device: `file:///home/omarchy/Phone Omdroid Phone` added beside the owner's four bookmarks, and `omdroid-share: bookmark removed` with sharing off, the owner's lines untouched |
| 4. DocumentsProvider in `storage/` + path rules + tests + manifest | PASS | `storage/GuestTree.kt`, `storage/OmdroidDocumentsProvider.kt`, `GuestTreeTest` (9 tests green), manifest `<provider>` per the platform page; device: registered and queried by DocumentsUI |
| 5. Device proof of the provider (read, write, Files app) | PASS | root listed in the picker (parent-viewed), the guest home listed with 11 children and their real sizes/dates, a subdirectory opened, `createDocument` created a real file in the guest home (host-side `run-as` read back), and `openDocument … mode=r` served a guest file to the system's document viewer (provider log, phase 9); the viewer's screen, viewed by the parent, shows the file's own text `hello from the guest side`, named `omdroid-read-test`, at 100.0 % |
| 6. `launch-contract.md` storage section | PASS | `docs/omarchy/launch-contract.md` section 10 |

## What changed

**Step 2 - the default (host).**
- `app/src/main/kotlin/com/phoshdroid/app/storage/ShareRule.kt:23` - the tri-state (`auto`/`on`/`off`),
  `resolve(mode, allFilesGranted)` at `:37`, the legacy boolean fold at `:49`.
- `settings/PhoshdroidPreferences.kt:63` - `bindSdcardMode` reads `bind_sdcard_mode`, folds a stored
  `bind_sdcard` in once, and removes the old key on the next write.
- `proot/ProotService.kt:110` - the session start resolves the rule with
  `Environment.isExternalStorageManager()` and logs one line (`share: mode=.. all-files=.. -> bind=..`).
- `SettingsFragment.kt:31` - a `ListPreference` with a live summary (`storageSummary`, `:42`) and the
  all-files request kept on this screen only, never on the launch path (R2 rule).
- `res/xml/preferences.xml:31`, `res/values/strings.xml:56` (`<!-- r11 share -->` block).

**Step 3 - the guest side.**
- `rootfs/overlay/etc/phoshdroid/share/session-start.sh` - one Nautilus bookmark for `~/Phone`
  (`~/.config/gtk-3.0/bookmarks`, the file GTK3 and GTK4 both read), keyed on `OMARCHY_SHARE`;
  idempotent, records what it added in `~/.local/state/omdroid/share/bookmark.line`, and removes the
  line only while it still equals the recorded text. Supports `OMDROID_ROOT` for a host dry run.
  `share/**` is already in `syncGuestOverlay` (`app/build.gradle.kts:87`) and in the packager, so no
  list edit.

**Step 4 - the provider.**
- `storage/GuestTree.kt` - document id to host file, resolving symlinks in GUEST space (absolute target
  rebased on the guest rootfs, relative on the link's directory, 16 hops), `..` refused, containment
  in `/home/omarchy`, nothing before `.extraction_complete`.
- `storage/OmdroidDocumentsProvider.kt` - authority `com.phoshdroid.app.documents`, one root
  "Omdroid", ids `root` / `doc:<path>`; read, write, create, delete (no symlink following),
  rename, MIME from the extension, one `documents:` log line per call.
- `AndroidManifest.xml:57` - the `<provider>` exactly as the platform documents it for a custom
  provider: `exported="true"`, `grantUriPermissions="true"`,
  `android:permission="android.permission.MANAGE_DOCUMENTS"`, intent filter
  `android.content.action.DOCUMENTS_PROVIDER`
  (read: developer.android.com/guide/topics/providers/create-document-provider).

**Step 6.** `docs/omarchy/launch-contract.md` section 10: the binds, `OMARCHY_SHARE`, the default
rule, the measured numbers, the provider's authority and every path rule.

## Host proof

- `:app:testDebugUnitTest --tests 'com.phoshdroid.app.storage.*'` - BUILD SUCCESSFUL (14 tests:
  `ShareRuleTest` 5, `GuestTreeTest` 9). `GuestTreeTest` covers: plain path, root, `..` and absolute
  ids, a guest absolute symlink, a relative symlink, links that leave the home (`/etc/passwd`,
  `../../etc/passwd`), a symlink loop (hop cap), the un-extracted guest, and listing order.
- `bash -n` on `share/session-start.sh` and `phase1.sh`/`phase2.sh`.
- The bookmark hook's dry run (`OMDROID_ROOT=<scratch tree>`): add -> one line; second run ->
  "already present", still one line; a user line survives a removal; a user-edited label is logged
  and left; `off` with no bookmarks file exits 0.
- Build: `docs/omarchy/tools/build-chain.sh --no-repack` (assemble + `:app:test`) under the gradle
  lock; the APK was copied out of `app/build/` at once. The chain prints
  `IMAGE!=REPO start.sh` - expected with `--no-repack`: the reflinked image predates the base
  commit's `start.sh`, and `GuestOverlay` re-syncs `etc/phoshdroid/**` from the APK on every cold
  start, so the guest runs the repo copy.

## Device proof

**Step 1** (R10 integration APK, `<scratch>/share/phase1/step1.txt`, same minute, arms alternating):

| Fact | Off | On |
| --- | --- | --- |
| `/home/omarchy/Phone` | absent (`ls` answers "No such file or directory") | the phone's storage, 35 top-level entries, `/sdcard` the same tree |
| guest -> Android | n/a | `~/Phone/omdroid-guest-write.txt` created, `adb shell cat /sdcard/...` reads it back |
| Android -> guest | n/a | a file created on `/sdcard/Download` appears in the guest listing at `~/Phone/Download` (mode 0660); that arm wrote 0 bytes (the `run-as` + `sh -c` quoting broke `printf`), so the content proof for this direction is the guest->Android row and step 5 |
| ownership | n/a | guest-created files: uid 10298 (the app's uid), gid 1023 `media_rw`, mode 0660; dirs 2770; guest umask 0077 |
| cold start to desktop | 10.3 s | 10.6 s and 11.2 s |
| media store | n/a | a PNG written from the guest is absent from `content://media/external/images/media` until `MEDIA_SCANNER_SCAN_FILE` (then `Row: 13446 omdroid-media-test.png`) |

Two things the round found that the brief did not know:
- **`~/Phone` is absent when sharing is off, not empty.** A guest script cannot use "the directory
  exists" as the signal; `OMARCHY_SHARE` is the only signal, which is what the hook reads.
- **`run-as <pkg> cat /sdcard/Download/<file written by the guest>` answers `Permission denied`**
  while `adb shell cat` on the same path reads it. The app's own uid created the file through the
  proot bind, so this is the FUSE/MediaStore permission model, not file modes. It is a second reason
  the provider serves the app-private guest home instead of `/sdcard`.

**Steps 2-5:** see the phase 2 and phase 3 sections below.

**Phase 2** (my APK, sha256 `398d47bfb53c6217…`, commit `a602e12`;
`<scratch>/share/phase2/step5.txt`):

- Install PASS: the installed `base.apk` sha256 equals the local APK's.
- Default arm: cold start 11.2 s handover / 10.7 s to desktop, `probe.sh` PASS, logcat
  `share: mode=auto all-files=true -> bind=true`, `~/Phone` present with 35 entries, and the guest
  bookmark is there: `file:///home/omarchy/Phone Omdroid Phone` in `~/.config/gtk-3.0/bookmarks`
  (the owner's four existing bookmarks untouched), with `omdroid-share: bookmark added` in the
  session log. **Step 3 proven on the device.**
- Provider: registered (`dumpsys activity providers`:
  `com.phoshdroid.app.documents: …/com.phoshdroid.app/.storage.OmdroidDocumentsProvider`, uid 10323)
  and DocumentsUI queried it (`documents: queryRoots: root=…/installed-rootfs/omarchy/home/omarchy`).
- The brief's CLI route answers exactly as the platform intends:
  `Permission Denial: opening provider … from (null) (uid=2000) requires that you obtain access
  using ACTION_OPEN_DOCUMENT or related APIs`.
- **Two instrument failures that phase 3 corrects:**
  - `appops set <pkg> MANAGE_EXTERNAL_STORAGE ignore` sets the *package* mode only; the *uid* mode
    stays `allow`, so `Environment.isExternalStorageManager()` still answered `true` and both
    no-grant arms measured the grant-on path (`mode=on all-files=true`, `mode=auto all-files=true`).
    The deny needs `appops set --uid`.
  - This ROM has no activity for `android.provider.action.BROWSE` (`unable to resolve Intent`) and
    its picker ignores `EXTRA_INITIAL_URI`, so the two provider screenshots from phase 2 show the
    wrong screen and are not cited. The provider is instead driven by tapping the "Omdroid" root in
    the picker's drawer (phase 3).

**Phase 3** (same APK; `<scratch>/share/phase3/step5b.txt`): the no-grant arms, done properly with
`appops set --uid`.

| Arm | Log line | Guest side |
| --- | --- | --- |
| all-files denied, mode `on` (forced) | `share: mode=on all-files=false -> bind=true` | `~/Phone` present but only **10** top-level entries - Android, Audiobooks, DCIM, Documents, Download, Movies, Music, Pictures, Podcasts, plus one ROM-owned directory - where the grant gives 35; the app's own files are missing |
| all-files denied, mode `auto` (the default) | `share: mode=auto all-files=false -> bind=false` | `~/Phone` is the leftover empty dir (`d--------- 2 omarchy omarchy`), and the hook logged `omdroid-share: bookmark removed`, leaving the owner's four bookmarks |
| grant restored, mode `auto` | `share: mode=auto all-files=true -> bind=true` | `~/Phone` mounted again; desktop ready in 6.6 s |

That is the evidence behind the default: without the grant a bind shows a partial tree whose extra
directories are the media collections, which reads as "the phone's storage, minus the user's own
files" - worse than no bind at all. Cold starts across all arms: 6.6-11.3 s to desktop, no arm stood
out.

**Phase 4** (same APK; `<scratch>/share/phase4/step5c.txt`): the provider driven through the ROM's
picker by name, not by `content`.

- The picker's roots drawer lists it: **"Omdroid" / "The Omarchy home inside Omdroid"** (our root's
  title and summary), beside the device's own storage, the Drive accounts and "Termux".
- Tapping it lists the guest home with names, sizes and dates:
  `.cache .config .local Downloads Phone Pictures Projects Videos .bash_logout 21 B .bash_profile
  57 B .bashrc 592 B`, and the provider logged
  `children of 'root' (omarchy): 11 [.cache, .config, .local, Downloads, Phone]`.
- Into a subdirectory: `children of 'doc:Downloads' (Downloads): 0 []` - correct, the owner's guest
  `~/Downloads` is empty.
- **Create, end to end**: after the picker's SAVE,
  `createDocument in 'doc:Downloads' name=omdroid-provider-create.txt -> Downloads/omdroid-provider-create.txt`
  and, read back from the host over `run-as`,
  `-rw------- 1 u0_a323 u0_a323 0 2026-11-27 01:31 …/home/omarchy/Downloads/omdroid-provider-create.txt`
  - a real file, owned by the app, in the guest home.
- Two of this phase's own instrument bugs, both fixed here: the device shell glob-expanded
  `-t */*` into `bin/abb` (the MIME type must be quoted for the *device* shell), and the tap matcher
  matched `omdroid-provider-create.txt` when told to tap "Omdroid" (exact-text matching now). The
  `OPEN_DOCUMENT` arm's drawer tap did not open the drawer in this run; `CREATE_DOCUMENT`'s did.
- **Screenshot caveat (parent-viewed):** this phase's four picker shots
  (`p4-picker-1`, `-downloads`, `-omdroid`, `-read`) are byte-identical - the screen did not change
  between them - so they prove nothing about navigation. The listing claims here rest on the
  provider's own log lines, not on the images.

**Phase 5** (same APK; `<scratch>/share/phase5/step5d.txt`): the picker remembered the provider's
folder from phase 4 and opened **inside** it:

- `Files from Omdroid/The Omarchy home inside Omdroid` with both files and their real sizes and
  times - `omdroid-provider-create.txt 0 B 01:31` and `omdroid-read-test.txt 26 B 02:14` (the 26 B
  file was written from the host over `run-as` a second before). That is `queryChildDocuments` +
  `COLUMN_SIZE` + `COLUMN_LAST_MODIFIED` on the device.
- Provider log: `queryDocument root`, `queryDocument doc:Downloads`,
  `children of 'doc:Downloads' (Downloads): 2 [omdroid-provider-create.txt, omdroid-read-test.txt]`.
- The read tap itself missed: opening the roots drawer moved the picker to "Recent", so the file row
  was gone by the time the tap landed. Phase 6 taps the row before touching the drawer.

**Phase 6** (same APK; `<scratch>/share/phase6/step5e.txt`): another attempt at the read tap, and it
failed for a UI reason, not a provider one: the picker reopened on "Recent" (the previous phase left
it there), the drawer toggle tap at the hamburger did not open the drawer in this run, and the
provider log stayed **empty** - nothing asked it for anything. `openDocument` is still the one
provider method not observed on the device. Phase 7 is the last attempt: it seeds the picker with our
document URI as the intent's data, and falls back to a swipe-opened drawer.

**Phase 7, re-queued and run at 08:06** (`<scratch>/share/phase7/step5f.txt`): seeding the picker with
our document URI as the intent **data** works where `EXTRA_INITIAL_URI` did not - the picker opens
straight into `Files from Omdroid/The Omarchy home inside Omdroid` and lists
`omdroid-read-test.txt 26 B 08:07`. Tapping the row's own preview action
(`Preview the file omdroid-read-test.txt`) raised the system's "Open with …" resolver listing a
document reader, which answers the question the other way round: DocumentsUI holds the URI and hands it
to a viewer, so `openDocument` is called by the **viewer**, not by the picker - the provider log for the
whole phase holds only `queryDocument root`, `queryDocument doc:Downloads` and
`children of 'doc:Downloads' … 1 [omdroid-read-test.txt]`. Phase 8 therefore answers the resolver with
"Once" (never "Always": that would set a default app on the owner's device) and reads the log again.
**Parent-viewed:** `p7-after-tap.png` shows precisely this - the picker inside Omdroid > Downloads with
the file row and the system chooser on top.

**Phase 8** (same APK; `<scratch>/share/phase8/step5g.txt`) failed for a plain reason: `am start`
answered *"Activity not started, intent has been delivered to currently running top-most instance"* -
the picker instance phase 7 left open on the resolver screen stayed alive, so the seeded intent went to
*it* and the screen stayed on the device's own Downloads (`Files in downloads`, the owner's files). No
provider call at all. Phase 9 force-stops `com.google.android.documentsui` and
`com.android.intentresolver` before the seeded intent, then taps the row's preview and answers the
chooser with "Once" (never "Always").

**Phase 9** (same APK; `<scratch>/share/phase9/step5h.txt`): the read path, proven. With the picker and
the resolver force-stopped first, the seeded intent landed inside `Omdroid > Downloads`
(`omdroid-read-test.txt 26 B 09:08`), the row's preview raised the chooser, and answering **Once**
produced this in the provider's log:

```
documents: queryDocument doc:Downloads/omdroid-read-test.txt
documents: openDocument doc:Downloads/omdroid-read-test.txt mode=r ->
  …/installed-rootfs/omarchy/home/omarchy/Downloads/omdroid-read-test.txt
```

and the viewer that took the file became the top activity (`topResumedActivity=<the device's bundled
document viewer, PdfActivity>`). So `openDocument` was called by the viewer, not by the picker - exactly
the split phase 7 exposed. The viewer's screen is `phase9/shots/p9-viewer.png`, **viewed by the
parent**: a text viewer showing the file's content `hello from the guest side`, named
`omdroid-read-test`, at 100.0 % - so the read renders the guest's bytes, not just an empty frame.

## Screenshots (viewed by the parent; this stream cannot see images)

All under `<scratch>/share/<phase>/shots/`. They show the owner's account names and recent files, so
they stay in scratch and are never committed (nothing image-shaped is in any commit on this branch).

| File | Parent's verdict |
| --- | --- |
| `phase6/shots/p6-picker-list.png` | Android's file picker on "Recent"; its "Browse files in other apps" row lists **Omdroid** beside Termux and the Drive accounts - the root is registered and visible. It does not show the guest home's contents. |
| `phase7/shots/p7-after-tap.png` | Inside **Omdroid > Downloads** ("Files from Omdroid/The Omarchy home inside Omdroid"), one file `omdroid-read-t…`, with the system "Open with" chooser on top. Browsing a guest folder from Android works and tapping a guest file reaches the app chooser; the file's contents are not shown yet - that is phase 8's job. |
| `p4-picker-1`, `p4-picker-downloads`, `p4-picker-omdroid`, `p4-picker-read` | Byte-identical: the screen did not change between those steps, so they prove no navigation. |
| `p5-picker-downloads` = `p5-picker-read`; `p6-picker-after-tap` = `p6-picker-preview` | Same, per phase. |
| `phase9/shots/p9-viewer.png` | **Viewed by the parent:** a text viewer showing the guest file's content `hello from the guest side`, named `omdroid-read-test`, at 100.0 % - the read path renders, not just opens. |

So every listing, create and read claim in this report rests on the provider's own `documents:` logcat
lines and on host-side `run-as` reads; a screenshot is corroboration only, and these particular ones
corroborate just the two rows above.

## Switches

- `bind_sdcard_mode` = `auto` | `on` | `off` (Settings -> Storage -> Share Android storage). `auto`
  (the default) is on exactly while the app holds all-files access. No rebuild needed to flip it.
- `OMARCHY_SHARE=storage` in the guest env is the guest-side signal; unset it (or set the mode to
  `off`) and the bookmark hook removes its line. `~/.config/omdroid/session.env` can override it for
  a manual session.
- The provider is always registered; it serves nothing before the guest is extracted.

## Risks

- The provider is reachable only through the system picker (`MANAGE_DOCUMENTS`), which is the
  documented model, but it also means `adb shell content query` cannot read it (the platform answers
  `requires that you obtain access using ACTION_OPEN_DOCUMENT`). Device proof therefore goes through
  DocumentsUI and the provider's own log lines, not through `content`.
- `deleteDocument` deletes a directory tree recursively, never following a symlink. A mis-tap in the
  Files app on a big folder is a real delete; there is no trash.
- Guest writes are not media-scanned, so a picture saved from Omarchy is invisible to Android's
  gallery until something scans it (step 1, measured).
- The provider is independent of the share mode: turning storage sharing off does not hide the guest
  home from the picker.
- No thumbnails (`FLAG_SUPPORTS_THUMBNAIL` is not set) and no search provider.

## Not done

- Reading and writing a document through `adb shell content` (blocked by the platform permission
  model, not by this code); the device proof went through the system picker, which holds that
  permission, plus the provider's own log lines.
- A thumbnail/`queryRecentDocuments`/`querySearchDocuments` surface.
- The guest-side file manager is Nautilus 50.3 + gvfs (read: image member list); if a future image
  ships a different file manager, the bookmark path is the thing to re-check.
- Listing edge: a child that resolves outside the home (a symlink to `/etc`) is still
  listed by `queryChildDocuments` (it is shown with its metadata) and refused on open; only the
  request paths are refused at resolution. Not exercised on the device - the owner's guest has no
  such link.
