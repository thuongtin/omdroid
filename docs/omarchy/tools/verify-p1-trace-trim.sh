#!/usr/bin/env bash
# verify-p1-trace-trim.sh -- R11 S5 phase 1 (run under the tablet lock; see verify-common.sh):
#   V3  onTrimMemory: every level the app logs, the log line, and whether the session survives.
#   V1  AQ_TRACE commit rhythm (r10-damage.md check 5): idle commits carry 0 rects, a keypress
#       carries N, the cadence matches the panel rate, no stall over 100 ms with a window open.
#       Arm B = the shipped damage patch, arm A = AQ_WAYLAND_FULL_DAMAGE=1 as the positive control.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
TRACE_DIR=$PHASE_OUT/trace
mkdir -p "$TRACE_DIR"

p1_cleanup() { gx 'rm -f /etc/phoshdroid/trace' > /dev/null 2>&1; true; }
trap 'p1_cleanup; owner_restore' EXIT
trap 'exit 130' INT TERM

# ---------------------------------------------------------------- V3
phase_log "=== V3: onTrimMemory"
"$TOOLS/coldstart.sh" 1 --tag v3-base 2>&1 | grep -E '^(RUN|SUMMARY)'
APP0=$(app_pid); HYP0=$(hypr_pid)
phase_log "V3 before: app pid $APP0, Hyprland pid $HYP0, top $(top_activity), $(probe_q), $(clients_line)"
for lvl in RUNNING_MODERATE RUNNING_LOW RUNNING_CRITICAL HIDDEN BACKGROUND MODERATE COMPLETE; do
    adb_ logcat -c
    r=$(adb_ shell am send-trim-memory $PKG $lvl 2>&1 | tr -d '\r' | head -2 | tr '\n' ' ')
    sleep 2
    lines=$(adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -a 'memory:' | cut -c1-140 | tr '\n' '|')
    phase_log "V3 $lvl: am said [$r] log [$lines] app=$(app_pid) hypr=$(hypr_pid) top=$(top_activity)"
done
phase_log "V3 after all levels: app pid $(app_pid) (was $APP0), Hyprland pid $(hypr_pid) (was $HYP0), $(probe_q), $(clients_line)"
adb_ logcat -c
adb_ shell am send-trim-memory $PKG 7 2>&1 | head -2
sleep 2
phase_log "V3 odd level 7 (no named level): log [$(adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -a 'memory:' | cut -c1-140 | tr '\n' '|')]"
android_shot v3-after

# ---------------------------------------------------------------- V1
phase_log "=== V1: AQ_TRACE commit rhythm"
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache
gpush_to "$VTOOLS/verify-ts.py" /home/omarchy/.cache/verify-ts.py
gx 'touch /etc/phoshdroid/trace; ls -l /etc/phoshdroid/trace'

trace_window() { # $1 label, $2 seconds, $3 "typing" to type while it runs
    local label=$1 secs=$2 typing=${3:-} tp=""
    if [ "$typing" = typing ]; then
        adb_ shell 'i=0; while [ $i -lt 26 ]; do input text a; sleep 0.15; i=$((i+1)); done' > /dev/null 2>&1 &
        tp=$!
    fi
    gx "L=\$(ls -t /run/user/1000/hypr/*/hypr*.log 2>/dev/null | head -1); echo log=\$L size_before=\$(stat -c %s \$L); timeout $secs tail -n0 -F \$L 2>/dev/null | python3 /home/omarchy/.cache/verify-ts.py > /tmp/ts-$label.txt; echo size_after=\$(stat -c %s \$L)"
    [ -n "$tp" ] && wait "$tp" 2> /dev/null
    adb_ shell run-as $PKG cat files/usr/tmp/ts-$label.txt > "$TRACE_DIR/$label.txt"
    echo "--- $label"
    python3 "$VTOOLS/verify-trace.py" "$TRACE_DIR/$label.txt" --show 3 --expect-ms 8.33
}

run_arm() { # $1 label, $2 windows: B (full set) or A (control set)
    local arm=$1
    "$TOOLS/coldstart.sh" 1 --tag "v1-$arm" 2>&1 | grep -E '^(RUN|SUMMARY)'
    sleep 20
    arm_check "$arm"
    phase_log "$(devices_line); $(monitor_line)"
    gx 'ls -la /run/user/1000/hypr/*/ | head; ls -l /tmp/omarchy-session.log; grep -c "commit damage" /tmp/omarchy-session.log' 2>&1 | sed 's/^/    /'
    trace_window "$arm-idle-bare" 12
    hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null
    sleep 4
    phase_log "$(clients_line)"
    if [ "$arm" = B ]; then trace_window "$arm-foot-idle" 12; fi
    trace_window "$arm-foot-typing" 12 typing
    gx 'pkill -x foot; echo foot closed'
    gx 'tail -n 12 /tmp/omarchy-session.log' 2>&1 | cut -c1-200 | sed 's/^/    session.log: /'
    gx 'L=$(ls -t /run/user/1000/hypr/*/hypr*.log | head -1); echo "whole-surface lines in the whole log: $(grep -c "whole surface" $L)"; echo "zero-rect lines: $(grep -c "damage 0 rect" $L)"; echo "log bytes: $(stat -c %s $L)"'
    android_shot "v1-$arm"
}

run_arm B

phase_log "--- arm A (control): AQ_WAYLAND_FULL_DAMAGE=1 added to session.env"
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.config/omdroid
{ grep -v '^__ABSENT__$' "$SAVED/guest_.config_omdroid_session.env" 2> /dev/null; echo 'AQ_WAYLAND_FULL_DAMAGE=1'; } > "$PHASE_OUT/session.env.A"
gpush_to "$PHASE_OUT/session.env.A" /home/omarchy/.config/omdroid/session.env
run_arm A
phase_log "V1/V3 done"
