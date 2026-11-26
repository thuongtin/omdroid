#!/bin/bash
# omdroid-repair-links.sh: restore hard-link members of the guest image that an
# older extractor dropped. Guests extracted before 0.0.14 lack all 1832 of them
# (the extractor could not hard-link inside app data and silently skipped them),
# /usr/bin/ld and gawk among them, so gcc fails with cannot find ld and makepkg
# builds break. hardlinks.txt lists "member<TAB>target" from the image; each
# missing member is copied from its target (about 11 MB in total). A marker
# keyed on the list checksum skips the scan on every later start.
# Comments in this file avoid apostrophes on purpose (same rule as start.sh).
set -u
LIST=/etc/phoshdroid/hardlinks.txt
[ -r "$LIST" ] || exit 0
STATE=${HOME:-/home/omarchy}/.local/state/omdroid
sum=$(cksum < "$LIST" | cut -d" " -f1)
MARK=$STATE/links-$sum
[ -e "$MARK" ] && exit 0
mkdir -p "$STATE"
fixed=0
failed=0
present=0
while IFS=$'\t' read -r member target; do
    [ -n "$member" ] && [ -n "$target" ] || continue
    if [ -e "/$member" ] || [ -L "/$member" ]; then
        present=$((present + 1))
        continue
    fi
    if [ -f "/$target" ] && mkdir -p "$(dirname "/$member")" && cp -p "/$target" "/$member" 2>/dev/null; then
        fixed=$((fixed + 1))
    else
        failed=$((failed + 1))
        echo "omdroid-repair-links: could not restore /$member from /$target"
    fi
done < "$LIST"
echo "omdroid-repair-links: restored $fixed, already present $present, failed $failed"
if [ "$failed" = 0 ]; then
    : > "$MARK"
fi
exit 0
