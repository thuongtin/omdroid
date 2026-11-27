#!/usr/bin/env bash
# verify-p6-stall.sh -- R11 S5 phase 6 (run under the tablet lock; see verify-common.sh):
#   V3  second half: the exact refusal text of `am send-trim-memory` for each level, the process
#       state behind it, and the one background level that Android delivers by itself
#       (TRIM_MEMORY_UI_HIDDEN when the app goes to the home screen), with the session alive after.
#   V1  second half: the commit-loop stall check with an instrument that has a time resolution
#       (a foot client with WAYLAND_DEBUG=1 flooding its terminal; its wl_callback.done events are
#       the compositor's frame loop in real time) and a POSITIVE CONTROL (Hyprland stopped with
#       SIGSTOP for 200 and 400 ms in the session this phase started). Arms in the order
#       B A A B (B = shipped damage patch, A = AQ_WAYLAND_FULL_DAMAGE=1), same hour.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
TRACE_DIR=$PHASE_OUT/trace
mkdir -p "$TRACE_DIR" "$PHASE_OUT/wl"
p6_cleanup() { gx 'rm -f /etc/phoshdroid/trace' > /dev/null 2>&1; true; }
trap 'p6_cleanup; owner_restore' EXIT
trap 'exit 130' INT TERM

adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache
for f in verify-ts.py verify-flood.sh verify-wlfoot.sh; do gpush_to "$VT/$f" /home/omarchy/.cache/$f; done
printf '%s\n' '#!/bin/bash' \
    ': > /tmp/verify-stalls.txt' \
    'p=$(pgrep -x Hyprland | head -1)' \
    'for ms in "$@"; do' \
    '    sleep 3' \
    '    s=$(date +%s.%N)' \
    '    kill -STOP "$p"; sleep "$((ms / 1000)).$(printf %03d $((ms % 1000)))"; kill -CONT "$p"' \
    '    echo "$s STOP $ms" >> /tmp/verify-stalls.txt' \
    'done' > "$PHASE_OUT/verify-stall.sh"
gpush_to "$PHASE_OUT/verify-stall.sh" /home/omarchy/.cache/verify-stall.sh

# ---------------------------------------------------------------- V3
phase_log "=== V3 part 2: send-trim-memory refusals, process state, natural UI_HIDDEN"
"$TOOLS/coldstart.sh" 1 --tag v3b-base 2>&1 | grep -E '^(RUN|SUMMARY)'
APP0=$(app_pid); HYP0=$(hypr_pid)
proc_state() { adb_ shell 'dumpsys activity processes 2>/dev/null | grep -A40 "ProcessRecord{.*com.phoshdroid.app" | grep -E "trimMemoryLevel|curProcState|mHasForegroundServices" | head -4' | tr -d '\r' | sed 's/^ */    /'; }
trim() { # $1 level; prints the FULL am answer and the app log
    adb_ logcat -c
    local out; out=$(adb_ shell am send-trim-memory $PKG $1 2>&1 | tr -d '\r' | grep -vE '^\s+at ' | tr '\n' '|')
    sleep 1.5
    phase_log "trim $1: am answer [${out:-ok, no output}] app log [$(adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -a 'memory:' | sed 's/.*memory: //' | tr '\n' '|')]"
}
phase_log "foreground, X display on top ($(top_activity)); process state:"; proc_state
for lvl in RUNNING_MODERATE RUNNING_LOW RUNNING_CRITICAL RUNNING_MODERATE HIDDEN BACKGROUND MODERATE COMPLETE 7; do trim $lvl; done
phase_log "process state after the foreground attempts:"; proc_state
phase_log "after: app pid $(app_pid) (was $APP0), Hyprland pid $(hypr_pid) (was $HYP0), $(probe_q)"

phase_log "-- the app goes to the home screen (Android sends UI_HIDDEN itself)"
adb_ logcat -c
adb_ shell input keyevent KEYCODE_HOME
sleep 4
phase_log "top $(top_activity); app log [$(adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -a 'memory:' | sed 's/.*memory: //' | tr '\n' '|')]"
proc_state
phase_log "session behind the home screen: app pid $(app_pid), Hyprland pid $(hypr_pid), $(probe_q), $(clients_line)"
for lvl in HIDDEN BACKGROUND MODERATE COMPLETE; do trim $lvl; done
phase_log "session after the backgrounded attempts: app pid $(app_pid), Hyprland pid $(hypr_pid), $(probe_q)"
adb_ shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $PKG/.LauncherActivity > /dev/null 2>&1
sleep 5
phase_log "icon tap back: top $(top_activity), app pid $(app_pid) (was $APP0), $(probe_q)"
android_shot v3b-back

# ---------------------------------------------------------------- V1
phase_log "=== V1 part 2: frame-loop stalls with a real-time instrument and a positive control"
gx 'touch /etc/phoshdroid/trace'
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.config/omdroid
printf '%s\n' 'AQ_WAYLAND_FULL_DAMAGE=1' > "$PHASE_OUT/session.env.A"
printf '%s\n' '# r11 verify: arm B, no switches' > "$PHASE_OUT/session.env.B"

run_arm() { # $1 arm letter, $2 tag
    local arm=$1 tag=$2
    gpush_to "$PHASE_OUT/session.env.$arm" /home/omarchy/.config/omdroid/session.env
    "$TOOLS/coldstart.sh" 1 --tag "v1b-$tag" 2>&1 | grep -E '^(RUN|SUMMARY)'
    sleep 20
    arm_check "$tag($arm)"
    gx 'rm -f /tmp/verify-wl.log /tmp/verify-flood-stop'
    hcq '/dispatch hl.dsp.exec_cmd("bash /home/omarchy/.cache/verify-wlfoot.sh")' > /dev/null
    sleep 5
    phase_log "$(clients_line)"
    # window 1: baseline flood
    gx "L=\$(ls -t /run/user/1000/hypr/*/hypr*.log | head -1); timeout 14 tail -n0 -F \$L 2>/dev/null | python3 /home/omarchy/.cache/verify-ts.py > /tmp/ts-$tag-base.txt; echo window1-done"
    adb_ shell run-as $PKG cat files/usr/tmp/ts-$tag-base.txt > "$TRACE_DIR/$tag-base.txt"
    S1=$(adb_ shell run-as $PKG stat -c %s files/usr/tmp/verify-wl.log | tr -d '\r')
    # window 2: the same flood with two injected stalls (positive control)
    ( gx 'bash /home/omarchy/.cache/verify-stall.sh 200 400' > /dev/null 2>&1 ) &
    sp=$!
    gx "L=\$(ls -t /run/user/1000/hypr/*/hypr*.log | head -1); timeout 14 tail -n0 -F \$L 2>/dev/null | python3 /home/omarchy/.cache/verify-ts.py > /tmp/ts-$tag-stall.txt; echo window2-done"
    wait "$sp" 2> /dev/null
    adb_ shell run-as $PKG cat files/usr/tmp/ts-$tag-stall.txt > "$TRACE_DIR/$tag-stall.txt"
    adb_ shell run-as $PKG cat files/usr/tmp/verify-wl.log > "$PHASE_OUT/wl/$tag-all.log"
    adb_ shell run-as $PKG cat files/usr/tmp/verify-stalls.txt > "$PHASE_OUT/wl/$tag-stalls.txt" 2> /dev/null
    head -c "$S1" "$PHASE_OUT/wl/$tag-all.log" > "$PHASE_OUT/wl/$tag-base.log"
    tail -c +"$((S1 + 1))" "$PHASE_OUT/wl/$tag-all.log" > "$PHASE_OUT/wl/$tag-stall.log"
    gx 'touch /tmp/verify-flood-stop; sleep 1; pkill -x foot; echo foot closed'
    phase_log "arm $tag($arm): probe $(probe_q), Hyprland still $(hypr_pid)"
    for w in base stall; do
        echo "--- $tag($arm) $w: wayland callbacks (real time)"
        python3 "$VTOOLS/verify-wl.py" "$PHASE_OUT/wl/$tag-$w.log" --stalls "$PHASE_OUT/wl/$tag-stalls.txt"
        echo "--- $tag($arm) $w: aquamarine commit trace (block resolution)"
        python3 "$VTOOLS/verify-trace.py" "$TRACE_DIR/$tag-$w.txt" --expect-ms 16.67
    done
    android_shot "v1b-$tag"
}
run_arm B B1
run_arm A A1
run_arm A A2
run_arm B B2
phase_log "V3/V1 part 2 done"
# my scratch files in the app's prefix tmp (NOT under installed-rootfs): the V5 markers, trace windows and wayland logs
cf=$(mktemp)
printf '%s\n' 'rm -f files/usr/tmp/v5-* files/usr/tmp/ts-B* files/usr/tmp/ts-A* files/usr/tmp/verify-* files/usr/tmp/touchlog.out' > "$cf"
runas "$cf"; rm -f "$cf"
phase_log "prefix tmp scratch files left: $(adb_ shell run-as $PKG ls files/usr/tmp | tr -d '\r' | grep -cE '^(v5-|ts-[AB]|verify-|touchlog.out)')"
