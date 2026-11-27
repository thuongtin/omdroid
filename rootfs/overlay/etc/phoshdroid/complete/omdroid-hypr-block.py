#!/usr/bin/env python3
"""Manage the Omdroid block in the user's Hyprland looknfeel.lua (R11 S4).

    omdroid-hypr-block.py apply|remove [--file PATH]

Hyprland shows two start-up warning banners on every start: "hyprland-guiutils is missing"
and "launched without start-hyprland". Both have an option in the shipped binary
(misc:disable_hyprland_guiutils_check, misc:disable_watchdog_warning); the guest has neither
the package nor start-hyprland (proot has no systemd, the session script execs Hyprland
itself), so the warnings say nothing the owner can act on. The block sets the two options.

Same rules as the mobile-UI block next to it: one marked block appended to the user's file,
never a rewrite of their lines, removed whole by `remove`, idempotent. A missing file is left
missing (Hyprland then keeps its defaults and shows the banners).
"""
import argparse
import os
import sys

BEGIN = "-- >>> omdroid complete >>>"
END = "-- <<< omdroid complete <<<"
BODY = [
    "-- Hyprland start-up warnings that cannot be acted on under proot (hyprland-guiutils is not",
    "-- in the guest, and the session script starts Hyprland itself). Written by",
    "-- /etc/phoshdroid/complete/session-start.sh; OMDROID_COMPLETE_BANNERS=0 removes it.",
    "hl.config({ misc = { disable_hyprland_guiutils_check = true, disable_watchdog_warning = true } })",
]


def strip(lines):
    out, skip = [], False
    for line in lines:
        if line == BEGIN:
            skip = True
            continue
        if line == END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("verb", choices=["apply", "remove"])
    ap.add_argument("--file", default=os.path.join(os.environ.get("HOME", "/home/omarchy"), ".config/hypr/looknfeel.lua"))
    a = ap.parse_args()
    try:
        with open(a.file, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        print("complete: banners: no %s, nothing to do" % a.file)
        return 0
    lines = text.split("\n")
    had_nl = lines and lines[-1] == ""
    if had_nl:
        lines = lines[:-1]
    kept = strip(lines)
    new = kept + [BEGIN] + BODY + [END] if a.verb == "apply" else kept
    out = "\n".join(new) + ("\n" if had_nl or a.verb == "apply" else "")
    if out == text:
        print("complete: banners: block already %s" % ("current" if a.verb == "apply" else "absent"))
        return 0
    tmp = a.file + ".omdroid.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(out)
    os.replace(tmp, a.file)
    print("complete: banners: block %s" % ("written" if a.verb == "apply" else "removed"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
