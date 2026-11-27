#!/usr/bin/env bash
# verify-common.sh -- helpers shared by the R11 S5 verification phases. Source it from a phase
# script after exporting TABLET_SERIAL, R11 (the round's scratch dir, holding device/phase-lib.sh),
# PHASE_OUT (this phase's output dir) and TOOLS (docs/omarchy/tools of the worktree):
#
#   export TABLET_SERIAL=<adb serial> R11=<round scratch> PHASE_OUT=<dir> TOOLS=<worktree>/docs/omarchy/tools
#   flock -w 10800 "$R11/tablet.lock" bash <phase.sh> > <log> 2>&1; echo "ALLDONE $(date -u +%T)" >> <log>
#
# It pulls in the round's phase library (owner state saved and put back on any exit, R10 build
# reinstalled and cold-started at the end) and adds what the verification phases share.
: "${R11:?}" "${TABLET_SERIAL:?}" "${PHASE_OUT:?}" "${TOOLS:?}"
VTOOLS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$R11/device/phase-lib.sh"
mkdir -p "$PHASE_OUT/crops" "$OMARCHY_SHOTS"

installed_sha() { adb_ shell "sha256sum \$(pm path $PKG | sed 's/package://' | tr -d '\r')" 2>/dev/null | cut -c1-64; }
ensure_r10() { # the build under test: $VERIFY_APK when set (another stream's APK), else the R10 integration build
    local apk=${VERIFY_APK:-$R10_APK} want s
    want=$(sha256sum "$apk" | cut -c1-64)
    s=$(installed_sha)
    if [ "$s" != "$want" ]; then
        phase_log "installed sha ${s:0:12} is not the wanted build ${want:0:12}; installing $(basename "$apk")"
        timeout 400 "$TOOLS/install.sh" "$apk" 2>&1 | grep -E 'INSTALL|sha256' | tail -2
        s=$(installed_sha)
    fi
    phase_log "build under test: APK sha256 $s $([ "$s" = "$R10_SHA" ] && echo '= R10 integration build (f2584e7)' || echo "= $(basename "$apk")") $([ "$s" = "$want" ] || echo 'MISMATCH: the wanted build did not install')"
}
app_pid() { adb_ shell pidof $PKG | tr -d '\r'; }
hypr_pid() { adb_ shell pidof Hyprland | tr -d '\r'; }
top_activity() { adb_ shell dumpsys activity activities 2> /dev/null | grep -m1 topResumedActivity | sed -E 's/.* u0 ([^ ]+) .*/\1/' | tr -d '\r'; }
hcq() { "$TOOLS/hc.sh" "$@" 2> /dev/null; }
probe_q() { "$TOOLS/probe.sh" -q 2>&1 | tail -1; }
clients_line() {
    hcq j/clients | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("[")
try: c=json.loads(t[i:]) if i>=0 else []
except ValueError: c=[]
print("clients=%d %s" % (len(c), [x.get("class") for x in c]))'
}
devices_line() {
    hcq j/devices | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("{")
try: d=json.loads(t[i:])
except ValueError: print("devices: unparsable"); sys.exit(0)
print("devices: mice=%s keyboards=%s touch=%s" % ([m.get("name") for m in d.get("mice",[])], [k.get("name") for k in d.get("keyboards",[])], [t.get("name") for t in d.get("touch",[])]))'
}
monitor_line() {
    hcq j/monitors | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("[")
try: m=json.loads(t[i:])
except ValueError: print("monitors: unparsable"); sys.exit(0)
print("monitors: " + "; ".join("%s %dx%d@%.2f scale=%s" % (x["name"], x["width"], x["height"], x["refreshRate"], x["scale"]) for x in m))'
}
# the process-level proof of what a session really runs (env switches and the aquamarine library)
arm_check() { # $1 label
    local p f; p=$(hypr_pid); f=$(mktemp)
    phase_log "arm $1: Hyprland pid ${p:-none}"
    [ -n "$p" ] || { rm -f "$f"; return 1; }
    cat > "$f" << EOF
tr '\0' '\n' < /proc/$p/environ | grep -E '^(AQ_TRACE|AQ_WAYLAND_FULL_DAMAGE|HYPRLAND_TRACE|AQ_WAYLAND_REFRESH_MHZ|MALLOC_ARENA_MAX|OMDROID_GPU)='
grep -a libaquamarine /proc/$p/maps | head -1
EOF
    runas "$f" | sed 's/^/    /'
    rm -f "$f"
}
android_shot() { # $1 name: a raw Android screenshot (any activity on top), size printed
    adb_ exec-out screencap -p > "$OMARCHY_SHOTS/$1.png" 2> /dev/null
    phase_log "android shot $1: $(file -b "$OMARCHY_SHOTS/$1.png" | cut -c1-60) top=$(top_activity)"
}
ui_dump() { # $1 name: what the foreground Android screen says, one node per line
    adb_ shell uiautomator dump /data/local/tmp/verify-ui.xml > /dev/null 2>&1
    adb_ shell cat /data/local/tmp/verify-ui.xml > "$PHASE_OUT/ui-$1.xml" 2> /dev/null
    python3 "$TOOLS/uitap.py" --all < "$PHASE_OUT/ui-$1.xml" 2> /dev/null | cut -c1-200
}
ui_tap() { # $1 regex: tap the first Android node whose text matches; prints what it tapped
    local xy; xy=$(python3 "$TOOLS/uitap.py" "$1" < "$PHASE_OUT/ui-$2.xml" 2> /dev/null)
    if [ -n "$xy" ]; then phase_log "tap '$1' at $xy"; adb_ shell input tap $xy; else phase_log "no node matches '$1'"; return 1; fi
}
gpush_to() { "$TOOLS/gpush.sh" "$1" "$2" > /dev/null 2>&1; }
# NOT A VALID REPAINT CHECK (kept for the record, used by phase 2 only): the `debug.vfr = false` re-assert changes
# nothing when vfr is already false, so Hyprland damages nothing and the two shots are both after-event frames
# (S1 measured 0 damaged commits of 233 and 256). Use verify-p9-repaint2.sh, which proves its forcing step first.
repaint_diff() { # $1 name
    sleep 3; "$TOOLS/shot.sh" "$1-before" > /dev/null 2>&1
    hcq '/eval hl.config({ debug = { vfr = false } })' > /dev/null
    sleep 3; "$TOOLS/shot.sh" "$1-after" > /dev/null 2>&1
    local r; r=$(python3 "$VTOOLS/verify-scrdiff.py" "$OMARCHY_SHOTS/$1-before.png" "$OMARCHY_SHOTS/$1-after.png" --crop "$PHASE_OUT/crops/$1.png")
    echo "$1: $r"
    printf '%s\t%s\n' "$1" "$(echo "$r" | head -1)" >> "$PHASE_OUT/diffs.tsv"
}
wait_for_log() { # $1 regex, $2 max seconds: wait until logcat holds the line
    local i
    for i in $(seq 1 "$2"); do
        adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -aqE "$1" && return 0
        sleep 1
    done
    return 1
}
main_state() { # $1 label: the app's main thread and thread-state census, read from /proc (no screen, no stream)
    local pid f; pid=$(app_pid)
    [ -n "$pid" ] || { phase_log "$1: no app process"; return; }
    f=$(mktemp)
    printf '%s\n' "pid=$pid" \
        'echo "main thread: state=$(cut -d" " -f3 /proc/$pid/task/$pid/stat) wchan=$(cat /proc/$pid/task/$pid/wchan)"' \
        'for t in /proc/$pid/task/*; do echo "$(cut -d" " -f2,3 $t/stat) wchan=$(cat $t/wchan)"; done | sort | uniq -c | sort -rn | head -8' > "$f"
    phase_log "$1: app pid $pid"
    runas "$f" 2>&1 | sed 's/^/    /'
    rm -f "$f"
}
anr_events() { # $1 label: did the system raise an ANR for the app since the last `logcat -b events -c`
    phase_log "$1: am_anr events: [$(timeout 20 adb -s "$TABLET_SERIAL" logcat -b events -d 2> /dev/null | grep -a 'am_anr' | grep -a "$PKG" | tail -2 | cut -c1-170 | tr '\n' '|')]"
}
