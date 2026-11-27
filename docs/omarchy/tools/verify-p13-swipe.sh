#!/usr/bin/env bash
# verify-p13-swipe.sh -- R11 S5 phase 13 (run under the tablet lock; see verify-common.sh): the closing gesture experiment.
#   Phase 8 swiped at an EMPTY desktop (foot was opened and then the arm focused workspace 2, leaving foot elsewhere), so its
#   "nothing moves" reading could not be trusted. This phase asserts the arrangement before every swipe and aborts loudly
#   if it is wrong:
#     - a foot client exists whose workspace.id equals the active workspace id (hyprctl j/clients, j/activeworkspace);
#     - the focused window is foot (hyprctl j/activewindow class);
#     - the frame taken just before the swipe differs from a clean-desktop frame by more than 100,000 px (the window is
#       really on the screen).
#   Arms, one session: control (nothing bound), 2 fingers, 4 fingers, then 2 fingers with gestures:workspace_swipe_touch
#   set true at runtime (read back with getoption, restored afterwards, original value logged). Each swipe records ws
#   before/after, the active workspace id, the monitor and a frame. If nothing moves in any arm, that is the result.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
T_START=$(date +%s); DEADLINE=$((T_START + 780))
: > "$PHASE_OUT/swipes.tsv"
trap 'owner_restore' EXIT
trap 'exit 130' INT TERM
MT=/data/local/tmp/verify-mt.json
shot() { "$TOOLS/shot.sh" "$1" > /dev/null 2>&1; }
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache

ws_id() { hcq j/activeworkspace | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("{")
try: w=json.loads(t[i:]); print(w.get("id","?"))
except ValueError: print("?")' 2>/dev/null; }
ws_state() { echo "ws=$(ws_id) $(monitor_line | sed 's/monitors: //') top=$(top_activity | sed 's#com.phoshdroid.app/##; s#com.miui.home/.launcher.Launcher#ANDROID-HOME#')"; }
foot_info() { # "ws=<id> activeclass=<class>" from j/clients + j/activewindow
    local c a
    c=$(hcq j/clients | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("[")
try: cl=json.loads(t[i:])
except ValueError: print("unparsable"); raise SystemExit
f=[x for x in cl if x.get("class")=="foot"]
print("ws=%s monitor=%s at=%s size=%s" % (f[0]["workspace"]["id"], f[0].get("monitor"), f[0].get("at"), f[0].get("size")) if f else "ws=NONE")' 2>/dev/null)
    a=$(hcq j/activewindow | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("{")
try: w=json.loads(t[i:]); print(w.get("class","NONE"))
except ValueError: print("NONE")' 2>/dev/null)
    echo "$c activeclass=$a"
}
flag_of() { hcq 'getoption gestures:workspace_swipe_touch' | grep -aoE 'int: [0-9]+|bool: (true|false)|custom type|no such option' | head -1; }
flag_set() { # $1 value: set the option and read it back; returns 0 when the read-back matches
    hcq "setoption gestures:workspace_swipe_touch $1" > /dev/null 2>&1
    [ "$(flag_of)" = "$2" ] && return 0
    hcq "keyword gestures:workspace_swipe_touch $1" > /dev/null 2>&1
    [ "$(flag_of)" = "$2" ] && return 0
    return 1
}
frame_diff_px() { # $1 and $2 shot names: changed pixels, from the diff's own numbers
    python3 "$VTOOLS/verify-scrdiff.py" "$OMARCHY_SHOTS/$1.png" "$OMARCHY_SHOTS/$2.png" 2>/dev/null | head -1 | sed -n 's/.*changed=\([0-9]*\).*/\1/p'
}
assert_arrangement() { # $1 arm: foot on the visible workspace, focused, and on the frame; aborts the phase loudly when not
    local arm=$1 info fws aws px i
    for i in $(seq 1 15); do
        info=$(foot_info); fws=$(echo "$info" | sed -n 's/.*ws=\([0-9]*\).*/\1/p'); aws=$(ws_id)
        case "$info" in *"ws=NONE"*) sleep 1 ;; *) [ "$fws" = "$aws" ] && [ -n "$fws" ] && break ;; esac
        sleep 1
    done
    if [ -z "${fws:-}" ] || [ "$fws" != "$aws" ]; then
        phase_log "ARM ABORT ($arm): foot is not on the visible workspace: $info, active ws=$aws"
        phase_log "ARM ABORT ($arm): no swipe taken in this arm"
        exit 3
    fi
    case "$info" in *"activeclass=foot"*) ;; *)
        phase_log "ARM ABORT ($arm): foot is on ws $aws but is not the focused window: $info"
        phase_log "ARM ABORT ($arm): no swipe taken in this arm"
        exit 3 ;;
    esac
    shot "$arm-pre"
    px=$(frame_diff_px "$arm-pre" clean)
    phase_log "$arm arrangement: $info, active ws=$aws; the window occupies $px px of the frame versus the clean desktop"
    if [ "${px:-0}" -lt 100000 ]; then
        phase_log "ARM ABORT ($arm): the frame before the swipe does not show the window ($px px differ from the clean frame)"
        phase_log "ARM ABORT ($arm): no swipe taken in this arm"
        exit 3
    fi
}
swipe() { # $1 name, then verify-mkuinput.py move arguments
    local name=$1 before; shift
    python3 "$VTOOLS/verify-mkuinput.py" "$PHASE_OUT/$name.json" --steps 30 move "$@" | tail -1
    adb_ push "$PHASE_OUT/$name.json" $MT > /dev/null 2>&1
    before=$(ws_state)
    adb_ shell uinput $MT > /dev/null 2>&1
    sleep 2
    printf '%s\t%s\t%s\n' "$name" "$before" "$(ws_state)" >> "$PHASE_OUT/swipes.tsv"
    phase_log "$name: before [$before] after [$(ws_state)]"
    shot "$name-after"
}
arm_swipes() { # $1 tag
    local x1=1000 x2=1300 x3=1600 x4=1900
    if [ "${2:-2}" = 4 ]; then
        swipe "$1-right" $x1 1000 $((x1 + 800)) 1000 $x2 1000 $((x2 + 800)) 1000 $x3 1000 $((x3 + 800)) 1000 $x4 1000 $((x4 + 800)) 1000
        swipe "$1-left" $((x1 + 800)) 1000 $x1 1000 $((x2 + 800)) 1000 $x2 1000 $((x3 + 800)) 1000 $x3 1000 $((x4 + 800)) 1000 $x4 1000
    else
        swipe "$1-right" $x1 1000 $((x1 + 800)) 1000 $x2 1000 $((x2 + 800)) 1000
        swipe "$1-left" $((x1 + 800)) 1000 $x1 1000 $((x2 + 800)) 1000 $x2 1000
    fi
}

"$TOOLS/coldstart.sh" 1 --tag v13 2>&1 | grep -E '^(RUN|SUMMARY)'
sleep 25
phase_log "session: $(probe_q); $(devices_line); $(ws_state)"
FLAG0=$(flag_of)
phase_log "gestures:workspace_swipe_touch at the start: '$FLAG0' (read, will be put back)"
shot clean
phase_log "clean frame taken on an empty desktop: $(ws_state)"

phase_log "=== arm ctl: nothing bound"
hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
assert_arrangement ctl
arm_swipes ctl 2

phase_log "=== arm g2: hl.gesture two fingers horizontal workspace"
phase_log "bind: $(hcq '/eval hl.gesture({ fingers = 2, direction = "horizontal", action = "workspace" })' | tail -1)"
assert_arrangement g2
arm_swipes g2 2

phase_log "=== arm g4: hl.gesture four fingers horizontal workspace"
phase_log "bind: $(hcq '/eval hl.gesture({ fingers = 4, direction = "horizontal", action = "workspace" })' | tail -1)"
assert_arrangement g4
arm_swipes g4 4

if [ "$(date +%s)" -gt "$DEADLINE" ]; then
    phase_log "deadline reached before the flag arm; arms done so far are in swipes.tsv"
    awk -F'\t' '{ printf "  %-10s %s\n    -> %s\n", $1, $2, $3 }' "$PHASE_OUT/swipes.tsv"
    exit 0
fi
phase_log "=== arm g2t: two fingers bound, gestures:workspace_swipe_touch true at runtime"
if flag_set 1 "int: 1"; then phase_log "flag set: '$(flag_of)'"
elif flag_set true "bool: true"; then phase_log "flag set: '$(flag_of)'"
else phase_log "flag COULD NOT be set at runtime; read-back is '$(flag_of)' - this arm is void"; fi
assert_arrangement g2t
arm_swipes g2t 2
if flag_set "$(echo "$FLAG0" | grep -aoE '[0-9]+|true|false' | head -1)" "$FLAG0"; then
    phase_log "flag restored: '$(flag_of)'"
else
    phase_log "flag RESTORE failed; it now reads '$(flag_of)', it was '$FLAG0'"
fi

gx 'pkill -x foot; echo foot closed' > /dev/null
phase_log "--- every swipe, before -> after"
awk -F'\t' '{ printf "  %-10s %s\n    -> %s\n", $1, $2, $3 }' "$PHASE_OUT/swipes.tsv"
phase_log "phase 13 done after $(( $(date +%s) - T_START )) s"
