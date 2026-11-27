#!/usr/bin/env bash
# verify-p8-gesture.sh -- R11 S5 phase 8 (run under the tablet lock; see verify-common.sh):
#   V7 follow-up. Phase 5 showed that a synthetic three-finger swipe is taken by HyperOS before
#   Hyprland can use it (`enable_three_gesture=1`, `three_gesture_horizontal_ltr=split_ltr`: the
#   first swipe put Omdroid into split screen, the second went to the Android home screen), so
#   "does a Hyprland touch workspace swipe work" was not answered. This phase binds a workspace
#   gesture at runtime (hl.gesture) with a finger count the system does not use and swipes with
#   that many fingers: two, then four, each way, each from a cold start. The control is the same
#   two-finger swipe with nothing bound. Per swipe: workspace id, monitor size (a split screen
#   shows as a narrower monitor), top activity and a screenshot.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
trap 'owner_restore' EXIT
trap 'exit 130' INT TERM
MT=/data/local/tmp/verify-mt.json

ws_line() {
    hcq j/activeworkspace | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("{")
try: w=json.loads(t[i:]); print("ws=%s" % w.get("id"))
except ValueError: print("ws=?")'
}
state() { echo "$(ws_line) $(monitor_line | sed 's/monitors: //') top=$(top_activity | sed 's#com.phoshdroid.app/##; s#com.miui.home/.launcher.Launcher#ANDROID-HOME#')"; }
swipe() { # $1 name, then verify-mkuinput.py move arguments
    local name=$1; shift
    python3 "$VTOOLS/verify-mkuinput.py" "$PHASE_OUT/$name.json" --steps 30 move "$@" | tail -1
    adb_ push "$PHASE_OUT/$name.json" $MT > /dev/null 2>&1
    local before; before=$(state)
    adb_ shell uinput $MT > /dev/null 2>&1
    sleep 2
    phase_log "$name: before [$before] after [$(state)]"
    "$TOOLS/shot.sh" "$name-after" > /dev/null 2>&1
}
arm() { # $1 tag, $2 fingers (0 = nothing bound)
    local tag=$1 f=$2
    "$TOOLS/coldstart.sh" 1 --tag "v8-$tag" 2>&1 | grep -E '^(RUN|SUMMARY)'
    sleep 25
    phase_log "arm $tag: $(probe_q); $(devices_line)"
    hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
    hcq '/dispatch hl.dsp.focus({ workspace = "2" })' > /dev/null; sleep 1
    if [ "$f" != 0 ]; then
        phase_log "bind: $(hcq "/eval hl.gesture({ fingers = $f, direction = \"horizontal\", action = \"workspace\" })" | tail -2 | tr '\n' ' ')"
    else
        phase_log "nothing bound (control)"
    fi
    local x1=1000 x2=1300 x3=1600 x4=1900 a b
    if [ "$f" = 4 ]; then
        swipe "$tag-right" $x1 1000 $((x1 + 800)) 1000 $x2 1000 $((x2 + 800)) 1000 $x3 1000 $((x3 + 800)) 1000 $x4 1000 $((x4 + 800)) 1000
        swipe "$tag-left" $((x1 + 800)) 1000 $x1 1000 $((x2 + 800)) 1000 $x2 1000 $((x3 + 800)) 1000 $x3 1000 $((x4 + 800)) 1000 $x4 1000
    else
        swipe "$tag-right" $x1 1000 $((x1 + 800)) 1000 $x2 1000 $((x2 + 800)) 1000
        swipe "$tag-left" $((x1 + 800)) 1000 $x1 1000 $((x2 + 800)) 1000 $x2 1000
    fi
    gx 'pkill -x foot; echo foot closed'
}

phase_log "screen: $("$TOOLS/screen.sh" show 2>&1 | tr '\n' ' ' | cut -c1-200)"
phase_log "HyperOS three-finger settings (read, not changed): $(adb_ shell 'settings get system enable_three_gesture; settings get system three_gesture_horizontal_ltr; settings get system three_gesture_down' | tr '\n' ' ')"
arm c2 0
arm g2 2
arm g4 4
phase_log "V7 follow-up done"
