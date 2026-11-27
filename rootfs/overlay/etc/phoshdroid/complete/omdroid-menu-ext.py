#!/usr/bin/env python3
"""Manage the Omdroid block in the Omarchy menu extension (R11 S4).

    omdroid-menu-ext.py apply|remove [--file PATH]

Omarchy reads ~/.config/omarchy/extensions/omarchy-menu.jsonc on top of its default menu:
an entry that reuses an id overrides the fields it names. Under proot the menu does NOT
evaluate `when:` guards (Menu.qml evaluateGuards skips them when OMARCHY_PROOT=1), so every
row is shown, including the ones that mean nothing on a tablet. A row with no `action`,
`target` or `provider` and no children is a menu without content, and the menu hides it:
that is how a row is removed here.

The block is marked, key-level and reversible. Everything outside the markers is the
user's and is never touched; entries the user writes AFTER the block win (JSON keeps the
last duplicate key). `apply` replaces an older block with the current one, `remove` deletes
the block and nothing else. Both are idempotent.
"""
import argparse
import os
import sys

BEGIN = "  // omdroid:begin managed by /etc/phoshdroid/complete (OMDROID_COMPLETE_MENU=0 removes it)"
END = "  // omdroid:end"

# One entry per line. A reused id resets every field the entry does not name (normalizeItem
# fills the rest with empty strings), so a visible row repeats its icon and action; a hidden
# row carries a label only (no action: Menu hides an empty menu).
ENTRIES = [
    ('system.screensaver', '{"label":"Screensaver"}'),
    ('system.lock', '{"label":"Lock"}'),
    ('system.suspend', '{"icon":"\U000f04b2","label":"Back to Android","action":"omdroid-session home","description":"Hands the screen back to Android; the desktop keeps running"}'),
    ('system.hibernate', '{"label":"Hibernate"}'),
    ('system.logout', '{"icon":"\U000f0343","label":"Logout","action":"omarchy-system-logout","description":"Ends the desktop session"}'),
    ('system.reboot', '{"icon":"\U000f0709","label":"Restart","action":"omarchy-system-reboot","description":"Restarts the desktop session, not the tablet"}'),
    ('system.shutdown', '{"icon":"\U000f0425","label":"Shutdown","action":"omarchy-system-shutdown","description":"Ends the session and closes Omdroid, not the tablet"}'),
]


def block_lines():
    out = [BEGIN]
    for key, value in ENTRIES:
        out.append('  "%s": %s,' % (key, value))
    out.append(END)
    return out


def split_block(lines):
    """(before, after) around an existing block, or None when there is none."""
    start = end = None
    for i, line in enumerate(lines):
        if line.strip().startswith("// omdroid:begin"):
            start = i
        elif line.strip().startswith("// omdroid:end") and start is not None:
            end = i
            break
    if start is None or end is None:
        return None
    return lines[:start], lines[end + 1:]


def apply(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, "\n".join(["{"] + block_lines() + ["}"]) + "\n")
        return "created %s with the Omdroid block" % path
    lines = text.split("\n")
    found = split_block(lines)
    if found:
        before, after = found
        new = before + block_lines() + after
    else:
        # Insert right after the first line that opens the object.
        for i, line in enumerate(lines):
            if line.strip() == "{" or line.rstrip().endswith("{") and not line.strip().startswith("//"):
                new = lines[: i + 1] + block_lines() + lines[i + 1:]
                break
        else:
            return "left %s alone: no opening brace found" % path
    if new == lines:
        return "menu block already current"
    write(path, "\n".join(new))
    return "menu block written"


def remove(path):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
    except FileNotFoundError:
        return "no menu extension file"
    found = split_block(lines)
    if not found:
        return "no Omdroid menu block to remove"
    before, after = found
    write(path, "\n".join(before + after))
    return "menu block removed"


def write(path, text):
    tmp = path + ".omdroid.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("verb", choices=["apply", "remove"])
    ap.add_argument("--file", default=os.path.join(os.environ.get("HOME", "/home/omarchy"),
                                                    ".config/omarchy/extensions/omarchy-menu.jsonc"))
    args = ap.parse_args()
    print("complete: menu: " + (apply(args.file) if args.verb == "apply" else remove(args.file)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
