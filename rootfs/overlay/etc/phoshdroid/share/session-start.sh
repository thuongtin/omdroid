#!/bin/bash
# R11 share: the phone's storage where a file manager looks for it.
#
# start.sh runs this after session.env, so OMARCHY_SHARE is the host's decision
# (contract section 10): `storage` means the session mounts /sdcard at
# /home/omarchy/Phone, anything else means sharing is off.
#
# What it does: one Nautilus bookmark for ~/Phone, so the file manager's sidebar
# names the phone's storage instead of hiding it three directories down. Nautilus
# (and GTK's places sidebar in general) reads bookmarks from
# ~/.config/gtk-3.0/bookmarks, one `<uri> <label>` line each - the same path in
# GTK3 and GTK4.
#
# No-clobber rule, the same one omdroid-ui.sh follows: the line is only appended
# when our URI is absent, the line we added is recorded in
# ~/.local/state/omdroid/share/bookmark.line, and removal takes a line back only
# while it still equals the recorded text. A line the user edited keeps the
# user's label; the script logs the skip and leaves it.
#
# Dry run: OMDROID_ROOT points the script at a scratch guest tree
# (root/home/omarchy, root/etc/phoshdroid) instead of /.

set -u

root="${OMDROID_ROOT:-}"
if [ -n "$root" ]; then
    home="$root/home/omarchy"
else
    home="${HOME:-/home/omarchy}"
fi

state="$home/.local/state/omdroid/share"
bookmarks="$home/.config/gtk-3.0/bookmarks"
uri="file:///home/omarchy/Phone"
line="$uri Omdroid Phone"
owned="$state/bookmark.line"

log() {
    printf 'omdroid-share: %s\n' "$*"
}

mkdir -p "$state" || exit 0

add_bookmark() {
    if [ -f "$bookmarks" ] && grep -Fxq "$line" "$bookmarks"; then
        log "bookmark already present"
        printf '%s\n' "$line" > "$owned"
        return 0
    fi
    mkdir -p "$(dirname "$bookmarks")" || return 1
    [ -f "$bookmarks" ] || : > "$bookmarks"
    local tmp
    tmp=$(mktemp "$state/bookmarks.XXXXXX") || return 1
    # Move our URI to the end instead of adding a second line for it.
    awk -v uri="$uri" 'index($0, uri) != 1 { print }' "$bookmarks" > "$tmp"
    printf '%s\n' "$line" >> "$tmp"
    cat "$tmp" > "$bookmarks"
    rm -f "$tmp"
    printf '%s\n' "$line" > "$owned"
    log "bookmark added: $line"
}

remove_bookmark() {
    [ -f "$bookmarks" ] || return 0
    if [ ! -f "$owned" ]; then
        log "no bookmark recorded; nothing to remove"
        return 0
    fi
    local our tmp
    our=$(cat "$owned")
    tmp=$(mktemp "$state/bookmarks.XXXXXX") || return 1
    awk -v our="$our" '$0 != our { print }' "$bookmarks" > "$tmp"
    if cmp -s "$tmp" "$bookmarks"; then
        log "bookmark no longer ours (edited or gone); leaving it"
    else
        cat "$tmp" > "$bookmarks"
        log "bookmark removed"
    fi
    rm -f "$tmp" "$owned"
}

case "${OMARCHY_SHARE:-}" in
    storage) add_bookmark ;;
    *) remove_bookmark ;;
esac

exit 0
