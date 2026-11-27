#!/usr/bin/env python3
"""Group the rows of attrib-smaps.sh by process and class; print the class table and the
25 largest mappings per process (PSS). Usage: attrib.py <rows file> [layers.json]"""
import collections
import json
import re
import sys

ROW = re.compile(r"(\S+) (\d+) pss=(\d+) rss=(\d+) pd=(\d+) swap=(\d+) perm=(\S+) size=(\d+) (.*)")


def klass(perm, name):
    n = name.lower()
    if n.startswith("/memfd:aquamarine-shm"):
        return "memfd aquamarine-shm (frame buffers)"
    if n.startswith("/memfd:"):
        return "memfd other"
    if "ashmem" in n or n.startswith("/dev/shm") or "/shm/" in n:
        return "ashmem / shm"
    if "kgsl" in n or "dmabuf" in n or "dma_buf" in n or "dma_heap" in n or "gralloc" in n or "/dev/dri" in n:
        return "GPU (kgsl / dmabuf)"
    if re.search(r"\.(ttf|ttc|otf|woff2?|pfb)(\s|$)", n) or "/fonts/" in n:
        return "font files"
    if re.search(r"\.(qmlc|jsc|qmlcache)(\s|$)", n) or "qmlcache" in n or "qml_cache" in n:
        return "QML caches"
    if re.search(r"\.(png|jpe?g|webp|svg|gif|bmp|icc)(\s|$)", n):
        return "image files"
    if re.search(r"/lib(qt|Qt)[^/]*\.so", name) or "/qt6/" in n or "/qml/" in n:
        return "libs: Qt"
    if "mesa" in n or "dri" in n.split("/")[-1] or "libllvm" in n or "libgallium" in n or "vulkan" in n or "libegl" in n or "libgl" in n:
        return "libs: Mesa / GL / LLVM"
    if ".so" in n:
        return "libs: other"
    if name == "-" or n.startswith("[anon") or n in ("[heap]", ""):
        if "x" in perm:
            return "anon exec (JIT)"
        return "heap and anon"
    if n.startswith("[stack") or n.startswith("[vdso") or n.startswith("[vvar") or n.startswith("[vsyscall"):
        return "stack / vdso"
    return "other files"


rows = collections.defaultdict(list)
for line in open(sys.argv[1], errors="replace"):
    m = ROW.match(line.strip())
    if m:
        label, pid, pss, rss, pd, sw, perm, size, name = m.groups()
        rows[(label, int(pid))].append(dict(pss=int(pss), rss=int(rss), pd=int(pd), swap=int(sw), perm=perm,
                                            size=int(size), name=name))
for (label, pid), maps in sorted(rows.items()):
    tot = sum(r["pss"] for r in maps)
    print(f"\n### {label} pid {pid}: PSS {tot / 1024:.1f} MB, private dirty {sum(r['pd'] for r in maps) / 1024:.1f} MB, "
          f"swap {sum(r['swap'] for r in maps) / 1024:.1f} MB, {len(maps)} mappings\n")
    byc = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in maps:
        c = byc[klass(r["perm"], r["name"])]
        c[0] += r["pss"]; c[1] += r["rss"]; c[2] += r["pd"]; c[3] += r["swap"]; c[4] += 1
    print("| class | PSS MB | RSS MB | private dirty MB | swap MB | mappings |")
    print("|---|---|---|---|---|---|")
    for k, v in sorted(byc.items(), key=lambda kv: -kv[1][0]):
        print(f"| {k} | {v[0] / 1024:.1f} | {v[1] / 1024:.1f} | {v[2] / 1024:.1f} | {v[3] / 1024:.1f} | {v[4]} |")
    print("\n| # | PSS MB | RSS MB | size MB | perm | class | mapping |")
    print("|---|---|---|---|---|---|---|")
    for i, r in enumerate(sorted(maps, key=lambda r: -r["pss"])[:25], 1):
        nm = r["name"]
        nm = nm.replace("/data/data/com.phoshdroid.app/files/usr/var/lib/proot-distro/installed-rootfs/omarchy", "<guest>")
        print(f"| {i} | {r['pss'] / 1024:.1f} | {r['rss'] / 1024:.1f} | {r['size'] / 1024:.1f} | {r['perm']} | "
              f"{klass(r['perm'], r['name'])} | {nm[:90]} |")
if len(sys.argv) > 2:
    try:
        lay = json.load(open(sys.argv[2]))
        print("\n### layer surfaces (hc.sh j/layers)\n")
        print("| monitor | level | namespace | x,y | w x h | MB at 4 B/px |")
        print("|---|---|---|---|---|---|")
        for mon, levels in lay.items():
            for lvl, items in levels.items():
                for it in items:
                    print(f"| {mon} | {lvl} | {it.get('namespace')} | {it.get('x')},{it.get('y')} | {it.get('w')} x {it.get('h')} | "
                          f"{it.get('w', 0) * it.get('h', 0) * 4 / 1048576:.1f} |")
    except Exception as e:  # layers are optional context
        print("layers: could not parse", e)
