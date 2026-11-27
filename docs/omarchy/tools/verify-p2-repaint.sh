#!/usr/bin/env bash
# verify-p2-repaint.sh -- R11 S5 phase 2 (run under the tablet lock; see verify-common.sh):
#   V2  correctness against a forced full repaint, three runs each of: a toast fade, a window
#       open and close, a scrolling terminal stopped, a rotation and back. Plus two controls:
#       (a) a real change must show as CHANGED, (b) with debug.vfr=true a toast fade is the
#       known stale-pixel case, so the instrument must be able to see a remnant there.
#       Every non-zero diff leaves a before|after|diff crop in $PHASE_OUT/crops to be viewed.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
: > "$PHASE_OUT/diffs.tsv"
trap 'owner_restore' EXIT
trap 'exit 130' INT TERM

adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache
gpush_to "$VT/verify-scroll.sh" /home/omarchy/.cache/verify-scroll.sh
"$TOOLS/coldstart.sh" 1 --tag v2-base 2>&1 | grep -E '^(RUN|SUMMARY)'
sleep 30
phase_log "session: $(probe_q); $(devices_line); $(monitor_line)"
"$TOOLS/sx.sh" 'hyprctl getoption debug:vfr; hyprctl getoption debug:damage_tracking' 10 2>&1 | tr '\n' ' ' | cut -c1-300
echo

phase_log "--- control a: a real change must read CHANGED"
"$TOOLS/shot.sh" ctl-real-before > /dev/null 2>&1
hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
"$TOOLS/shot.sh" ctl-real-after > /dev/null 2>&1
echo "ctl-real: $(python3 "$VTOOLS/verify-scrdiff.py" "$OMARCHY_SHOTS/ctl-real-before.png" "$OMARCHY_SHOTS/ctl-real-after.png" --crop "$PHASE_OUT/crops/ctl-real.png")"
gx 'pkill -x foot; echo foot closed'

phase_log "--- control b: debug.vfr=true then a toast fade (the case that left a remnant in R10)"
for i in 1 2 3; do
    hcq '/eval hl.config({ debug = { vfr = true } })' > /dev/null; sleep 2
    "$TOOLS/sx.sh" "notify-send -t 2500 'R11 V2 control $i' 'vfr true toast'" 10 > /dev/null 2>&1
    sleep 10
    repaint_diff "ctl-vfr-$i"
done

phase_log "--- V2 toast fade x3 (vfr=false as shipped)"
for i in 1 2 3; do
    "$TOOLS/sx.sh" "notify-send -t 2500 'R11 V2 toast $i' 'this toast fades out'" 10 > /dev/null 2>&1
    sleep 1; "$TOOLS/shot.sh" "toast-$i-showing" > /dev/null 2>&1
    sleep 9
    repaint_diff "toast-$i"
done

phase_log "--- V2 window open and close x3"
for i in 1 2 3; do
    hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
    phase_log "$(clients_line)"
    repaint_diff "open-$i"
    gx 'pkill -x foot; echo foot closed'
    repaint_diff "close-$i"
done

phase_log "--- V2 scrolling terminal stopped x3"
for i in 1 2 3; do
    gx 'rm -f /tmp/verify-scroll-stop'
    hcq '/dispatch hl.dsp.exec_cmd("foot bash /home/omarchy/.cache/verify-scroll.sh")' > /dev/null; sleep 6
    "$TOOLS/shot.sh" "scroll-$i-running" > /dev/null 2>&1
    gx 'touch /tmp/verify-scroll-stop'; sleep 1
    phase_log "$(clients_line)"
    repaint_diff "scroll-stop-$i"
    gx 'pkill -x foot; echo foot closed'
    repaint_diff "scroll-close-$i"
done

phase_log "--- V2 rotation and back x3 (window opened first, closed after the rotation)"
for i in 1 2 3; do
    hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
    "$TOOLS/screen.sh" rot 0 2>&1 | grep -E 'cur=|rotation' | tr '\n' ' '; echo
    sleep 12
    phase_log "after rotate: $(probe_q) pid=$(app_pid) $(clients_line)"
    repaint_diff "rot-$i-portrait-open"
    gx 'pkill -x foot; echo foot closed'
    repaint_diff "rot-$i-portrait-closed"
    "$TOOLS/screen.sh" rot 1 2>&1 | grep -E 'cur=|rotation' | tr '\n' ' '; echo
    sleep 12
    phase_log "after rotate back: $(probe_q) pid=$(app_pid)"
    repaint_diff "rot-$i-landscape"
done
phase_log "--- diffs.tsv"
cut -c1-170 "$PHASE_OUT/diffs.tsv"
phase_log "V2 done"
