#!/usr/bin/env python3
"""Host test (R11 S4): the Omdroid block in the Omarchy menu extension does what it says.

It runs the REAL `MenuModel.js` of the image (through node) over the image's own default
menu plus the extension file this tool produces, with the proot conditions: `when:` guards
are never evaluated (Menu.qml skips them under OMARCHY_PROOT=1), so `whenResults` is empty.

Checks
  (i)   control: without the block, the System menu lists all seven rows, Hibernate and
        Screensaver included (that is the gap)
  (ii)  with the block: Screensaver, Lock and Hibernate are gone; Suspend is "Back to Android"
        running `omdroid-session home`; Logout, Restart and Shutdown keep their scripts and icons
  (iii) the block is idempotent, `remove` restores the original file byte for byte, and text the
        user wrote around it is left alone, including an entry of their own after the block

usage: complete-menu-test.py --omarchy <extracted usr/share/omarchy> [-v]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
EXT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "rootfs", "overlay", "etc", "phoshdroid",
                                    "complete", "omdroid-menu-ext.py"))

NODE = r"""
const fs = require('fs');
const M = require(process.argv[2]);
const dflt = M.parseMenuJsonc(fs.readFileSync(process.argv[3], 'utf8'));
const user = M.parseMenuJsonc(fs.readFileSync(process.argv[4], 'utf8'));
const merged = M.mergeMenuSources(dflt, user);
const rows = [];
for (const id of merged.itemOrder) {
  const e = merged.items[id];
  if (e.parent !== 'system') continue;
  // proot: whenResults is {} (guards are not evaluated), exactly as Menu.qml leaves it
  if (!M.isVisible(merged.items, merged.itemOrder, {}, e)) continue;
  rows.push({id, label: e.label, action: e.action, icon: e.icon, description: e.description});
}
console.log(JSON.stringify(rows));
"""


def visible_rows(omarchy, ext_file, tmp):
    js = os.path.join(tmp, "probe.js")
    with open(js, "w") as fh:
        fh.write(NODE)
    out = subprocess.run(
        ["node", js, os.path.join(omarchy, "shell/plugins/menu/MenuModel.js"),
         os.path.join(omarchy, "default/omarchy/omarchy-menu.jsonc"), ext_file],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("node failed: " + out.stderr)
    return json.loads(out.stdout)


def ext(verb, path):
    r = subprocess.run([sys.executable, "-B", EXT, verb, "--file", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ext failed: " + r.stderr)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--omarchy", required=True)
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="menu-test-")
    template = os.path.join(a.omarchy, "config/omarchy/extensions/omarchy-menu.jsonc")
    ok_all = True

    def check(name, ok, detail=""):
        nonlocal ok_all
        ok_all &= bool(ok)
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  -- " + detail) if (a.v or not ok) else ""))

    user = os.path.join(tmp, "omarchy-menu.jsonc")
    shutil.copy(template, user)
    before = open(user).read()

    base_rows = visible_rows(a.omarchy, user, tmp)
    base_labels = [r["label"] for r in base_rows]
    check("control: the stock System menu shows all seven rows under proot",
          base_labels == ["Screensaver", "Lock", "Suspend", "Hibernate", "Logout", "Reboot", "Shutdown"],
          str(base_labels))

    print(ext("apply", user))
    rows = visible_rows(a.omarchy, user, tmp)
    labels = [r["label"] for r in rows]
    check("block: Screensaver, Lock and Hibernate are hidden", labels == ["Back to Android", "Logout", "Restart", "Shutdown"], str(labels))
    by = {r["id"]: r for r in rows}
    check("block: Suspend runs omdroid-session home", by["system.suspend"]["action"] == "omdroid-session home",
          str(by.get("system.suspend")))
    stock = {r["id"]: r for r in base_rows}
    check("block: Logout, Restart and Shutdown keep their scripts and icons",
          all(by[i]["action"] == stock[i]["action"] and by[i]["icon"] == stock[i]["icon"] and by[i]["icon"]
              for i in ("system.logout", "system.reboot", "system.shutdown")),
          str({i: (by[i]["action"], by[i]["icon"]) for i in by}))
    check("block: Suspend keeps a Nerd Font icon", bool(by["system.suspend"]["icon"]))

    once = open(user).read()
    ext("apply", user)
    check("apply twice changes nothing", open(user).read() == once)

    ext("remove", user)
    check("remove restores the file byte for byte", open(user).read() == before)

    # a user's own content: an entry before and one after the block, with comments
    custom = '{\n  // mine\n  "personal.notes": {"label":"Notes","action":"true"},\n}\n'
    with open(user, "w") as fh:
        fh.write(custom)
    ext("apply", user)
    after = visible_rows(a.omarchy, user, tmp)
    check("a user file with its own entries still parses and keeps them",
          "personal.notes" in open(user).read() and [r["label"] for r in after] == labels, str([r["label"] for r in after]))
    ext("remove", user)
    check("remove leaves the user's own text untouched", open(user).read() == custom)

    # the user overrides one of our rows AFTER the block: the user wins (last key wins)
    with open(user, "w") as fh:
        fh.write('{\n}\n')
    ext("apply", user)
    text = open(user).read().replace("\n}\n", '\n  "system.lock": {"icon":"x","label":"Lock","action":"mine"}\n}\n')
    with open(user, "w") as fh:
        fh.write(text)
    mine = {r["id"]: r for r in visible_rows(a.omarchy, user, tmp)}
    check("an entry the user writes after the block wins", mine.get("system.lock", {}).get("action") == "mine",
          str(mine.get("system.lock")))

    print("\nall passed" if ok_all else "\nFAILED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
