#!/usr/bin/env bash
# verify-p5-multitouch.sh -- R11 S5 phase 5 (run under the tablet lock; see verify-common.sh):
#   V7  pinch and three-finger touch with a synthetic multi-touch screen (Android `uinput`):
#       which touch points reach a client (touchlog overlay: ids, positions, cancels), and
#       whether Hyprland's touch workspace swipe is configured and what a three-finger swipe does
#       to the workspace, the window and Android (top activity) with and without it enabled.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
trap 'owner_restore' EXIT
trap 'exit 130' INT TERM

MT=/data/local/tmp/verify-mt.json
tl_run() { # $1 name, then verify-mkuinput.py arguments
    local name=$1; shift
    python3 "$VTOOLS/verify-mkuinput.py" "$PHASE_OUT/$name.json" "$@" | tail -1
    adb_ push "$PHASE_OUT/$name.json" $MT > /dev/null 2>&1
    gx 'rm -f /tmp/touchlog.out'
    hcq '/dispatch hl.dsp.exec_cmd("/tmp/touchlog 16 > /tmp/touchlog.out 2>&1")' > /dev/null
    sleep 2
    adb_ shell uinput $MT > /dev/null 2>&1
    sleep 12
    adb_ shell run-as $PKG cat files/usr/tmp/touchlog.out > "$PHASE_OUT/$name.touchlog" 2> /dev/null
    echo "== $name"
    python3 "$VTOOLS/verify-touchlog.py" "$PHASE_OUT/$name.touchlog"
}
ws_line() {
    hcq j/activeworkspace | python3 -c 'import json,sys
t=sys.stdin.read(); i=t.find("{")
try: w=json.loads(t[i:]); print("workspace id=%s windows=%s" % (w.get("id"), w.get("windows")))
except ValueError: print("workspace: unparsable")'
}

phase_log "screen: $("$TOOLS/screen.sh" show 2>&1 | tr '\n' ' ' | cut -c1-260)"
"$TOOLS/coldstart.sh" 1 --tag v7-base 2>&1 | grep -E '^(RUN|SUMMARY)'
sleep 25
phase_log "$(probe_q); $(devices_line); $(monitor_line)"
phase_log "touchlog on the tablet: $(adb_ shell run-as $PKG sha256sum files/usr/tmp/touchlog | cut -c1-64) (R5 build, 75,824 B expected)"

phase_log "=== V7.0 is the touch workspace swipe configured?"
"$TOOLS/sx.sh" 'hyprctl getoption gestures:workspace_swipe_touch; hyprctl getoption gestures:workspace_swipe_fingers; hyprctl getoption gestures:workspace_swipe; hyprctl getoption input:touchdevice:enabled' 15 2>&1 | sed 's/^/    sx: /' | head -24
gx 'grep -rInE "workspace_swipe|hl\.gesture|gesture *\(" /home/omarchy/.config /usr/share/omarchy 2>/dev/null | cut -c1-200 | head -20; echo "grep rc done"' 2>&1 | sed 's/^/    cfg: /'
gx 'ls ~/.local/state/omarchy/toggles/hypr/ 2>&1 | head -5' 2>&1 | sed 's/^/    toggles: /'

phase_log "=== V7.1 which points reach a client (touchlog overlay, layer 3)"
tl_run cal --steps 1 tap 1600 1000
tl_run pinch-out --steps 30 move 1500 1000 1100 1000 1700 1000 2100 1000
tl_run pinch-in --steps 30 move 1100 1000 1500 1000 2100 1000 1700 1000
tl_run three-swipe --steps 30 move 1000 1000 1800 1000 1500 1000 2300 1000 2000 1000 2800 1000
tl_run three-swipe-back --steps 30 move 1800 1000 1000 1000 2300 1000 1500 1000 2800 1000 2000 1000
phase_log "synthetic devices left behind: $(adb_ shell dumpsys input | grep -c 'Test Touchscreen')"
phase_log "top after: $(top_activity)"

phase_log "=== V7.2 what a three-finger swipe does to Hyprland and Android (foot open, no overlay)"
hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
phase_log "$(clients_line); $(ws_line); top $(top_activity)"
hcq '/dispatch hl.dsp.focus({ workspace = "2" })' > /dev/null; sleep 1
phase_log "control: after switching to workspace 2 by IPC: $(ws_line)"
hcq '/dispatch hl.dsp.focus({ workspace = "1" })' > /dev/null; sleep 1
for run in 1 2; do
    python3 "$VTOOLS/verify-mkuinput.py" "$PHASE_OUT/ws$run.json" --steps 30 move 1000 1000 1800 1000 1500 1000 2300 1000 2000 1000 2800 1000 | tail -1
    adb_ push "$PHASE_OUT/ws$run.json" $MT > /dev/null 2>&1
    before="$(ws_line) $(clients_line) top=$(top_activity)"
    "$TOOLS/shot.sh" "ws$run-before" > /dev/null 2>&1
    adb_ shell uinput $MT > /dev/null 2>&1
    sleep 2
    phase_log "three-finger swipe $run: before [$before] after [$(ws_line) $(clients_line) top=$(top_activity)]"
    "$TOOLS/shot.sh" "ws$run-after" > /dev/null 2>&1
    hcq '/dispatch hl.dsp.focus({ workspace = "1" })' > /dev/null
    case "$(top_activity)" in *com.termux.x11.MainActivity*) ;; *) phase_log "Android took the gesture (top is $(top_activity)); bringing the display back"; adb_ shell am start -n $PKG/com.termux.x11.MainActivity > /dev/null 2>&1; sleep 3 ;; esac
done

phase_log "=== V7.3 informational: workspace_swipe_touch enabled at runtime, same swipe"
hcq '/eval hl.config({ gestures = { workspace_swipe_touch = true } })' | head -3
"$TOOLS/sx.sh" 'hyprctl getoption gestures:workspace_swipe_touch' 10 2>&1 | head -4 | sed 's/^/    sx: /'
python3 "$VTOOLS/verify-mkuinput.py" "$PHASE_OUT/ws3.json" --steps 30 move 1000 1000 1800 1000 1500 1000 2300 1000 2000 1000 2800 1000 | tail -1
adb_ push "$PHASE_OUT/ws3.json" $MT > /dev/null 2>&1
before="$(ws_line) top=$(top_activity)"
adb_ shell uinput $MT > /dev/null 2>&1
sleep 2
phase_log "enabled, three-finger swipe: before [$before] after [$(ws_line) $(clients_line) top=$(top_activity)]"
"$TOOLS/shot.sh" ws3-after > /dev/null 2>&1
tl_run three-swipe-enabled --steps 30 move 1000 1000 1800 1000 1500 1000 2300 1000 2000 1000 2800 1000
hcq '/eval hl.config({ gestures = { workspace_swipe_touch = false } })' > /dev/null

phase_log "=== V7.4 informational: the Hyprland 0.5x gesture binding (hl.gesture, three fingers horizontal)"
phase_log "eval answer: $(hcq '/eval hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })' | head -3 | tr '\n' ' ')"
hcq '/dispatch hl.dsp.focus({ workspace = "1" })' > /dev/null; sleep 1
before="$(ws_line) top=$(top_activity)"
adb_ shell uinput $MT > /dev/null 2>&1
sleep 2
phase_log "gesture bound, three-finger swipe: before [$before] after [$(ws_line) $(clients_line) top=$(top_activity)]"
"$TOOLS/shot.sh" ws4-after > /dev/null 2>&1
gx 'pkill -x foot; echo foot closed'
case "$(top_activity)" in *com.termux.x11.MainActivity*) ;; *) adb_ shell am start -n $PKG/com.termux.x11.MainActivity > /dev/null 2>&1 ;; esac
phase_log "V7 done; synthetic devices left behind: $(adb_ shell dumpsys input | grep -c 'Test Touchscreen')"
