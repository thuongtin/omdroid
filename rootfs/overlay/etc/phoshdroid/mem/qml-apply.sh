#!/bin/bash
# R11 mem: put patched Quickshell files over the image copies, keeping the originals.
# Idempotent. Files live in mem/qml/<path under the shell dir>, each with a sibling
# <file>.base-sha256 holding the sha256 of the image original it was derived from: a
# patch is applied only to exactly that original, so an image whose file moved on is
# left alone (and logged). The original is kept as <file>.omdroid-orig, which Quickshell
# never loads (it is not a .qml name). OMDROID_MEM=0 or OMDROID_MEM_QML=0 restores them.
# OMDROID_QML_ROOT overrides the shell dir (host dry runs).
src=/etc/phoshdroid/mem/qml
dst=${OMDROID_QML_ROOT:-/usr/share/omarchy/shell}
[ -d "$src" ] || exit 0

off=0
[ "${OMDROID_MEM:-1}" = 0 ] && off=1
[ "${OMDROID_MEM_QML:-1}" = 0 ] && off=1

sha() { sha256sum < "$1" | cut -c1-64; }

find "$src" -name '*.qml' -type f | sort | while read -r patched; do
    rel=${patched#"$src"/}
    target=$dst/$rel
    orig=$target.omdroid-orig
    base_file=$patched.base-sha256
    if [ "$off" = 1 ]; then
        if [ -f "$orig" ]; then
            mv -f "$orig" "$target" && echo "mem: qml restored $rel"
        fi
        continue
    fi
    if [ ! -f "$target" ]; then
        echo "mem: qml skip $rel (not in the image)"
        continue
    fi
    if [ "$(sha "$target")" = "$(sha "$patched")" ]; then
        echo "mem: qml in place $rel"
        continue
    fi
    base=$(cut -c1-64 "$base_file" 2>/dev/null)
    if [ -f "$orig" ]; then
        have=$(sha "$orig")
    else
        have=$(sha "$target")
    fi
    if [ -z "$base" ] || [ "$have" != "$base" ]; then
        echo "mem: qml skip $rel (image file is $have, patch is for ${base:-unknown})"
        continue
    fi
    [ -f "$orig" ] || cp -p "$target" "$orig" || { echo "mem: qml cannot back up $rel"; continue; }
    if cp "$patched" "$target.new" && mv -f "$target.new" "$target"; then
        echo "mem: qml patched $rel"
    else
        rm -f "$target.new"
        echo "mem: qml patch failed $rel"
    fi
done
exit 0
