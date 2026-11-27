#!/usr/bin/env bash
# verify-p10-sliver.sh -- R11 S5 phase 10 (run under the tablet lock; see verify-common.sh): the ONE counter-check for V2.
#   Phase 9 (the redo with a proven forcing step) found every comparison exact except one repeatable
#   thing: after a window CLOSE (and once after a rotation back) the damage-limited frame differs from the
#   full repaint in 24 pixels of the first wallpaper row under the bar (x 3057-3082, y 88), by ONE level of
#   one channel (131 -> 132). The frame taken before the window opened equals the full repaint, so the
#   after-close frame is the odd one out. Question: does the damage patch cause it?
#   Arms B A A B (B = shipped, A = AQ_WAYLAND_FULL_DAMAGE=1, which makes aquamarine send the whole
#   surface on every commit): in each arm, three open/close cycles judged against the full repaint
#   (damage_tracking 0 then 2) and against the frame before the window opened. In arm A a remnant
#   painted into cage's window must vanish by itself (the control that arm A really sends everything);
#   in arm B it must stay until the forcing step removes it (the phase-9 control).
#   If the sliver shows in both arms it is Hyprland's own damage-limited render, not the patch.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
. "$VT/verify-repaint-lib.sh"
ensure_r10
: > "$PHASE_OUT/diffs.tsv"
trap 'owner_restore' EXIT
trap 'exit 130' INT TERM
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache $ROOTS/omarchy/home/omarchy/.config/omdroid
gpush_to "$VT/verify-xcorrupt.py" /home/omarchy/.cache/verify-xcorrupt.py
printf '%s\n' 'AQ_WAYLAND_FULL_DAMAGE=1' > "$PHASE_OUT/session.env.A"
printf '%s\n' '# r11 verify: arm B, no switches' > "$PHASE_OUT/session.env.B"

run_arm() { # $1 arm letter, $2 tag
    local arm=$1 tag=$2 i c0 c1 c2
    gpush_to "$PHASE_OUT/session.env.$arm" /home/omarchy/.config/omdroid/session.env
    "$TOOLS/coldstart.sh" 1 --tag "v10-$tag" 2>&1 | grep -E '^(RUN|SUMMARY)'
    sleep 25
    arm_check "$tag($arm)"
    phase_log "$(probe_q); $(monitor_line); $(dt_readback)"
    sleep 3; shot "$tag-ctl-s0"
    phase_log "$tag: $(corrupt)"
    sleep 1.5; shot "$tag-ctl-s1"
    sdiff "$tag-ctl1-clean-vs-painted" "$tag-ctl-s0" "$tag-ctl-s1"
    c0=$LAST_VERDICT
    sleep 3; shot "$tag-ctl-s2"
    sdiff "$tag-ctl2-painted-vs-3s-later" "$tag-ctl-s1" "$tag-ctl-s2"
    c1=$LAST_VERDICT
    if [ "$arm" = B ]; then
        phase_log "$tag(B): remnant after 3 s: $c1 (ZERO or CLOCK_ONLY = still there, as the shipped damage path should leave it)"
        force_A; sleep 1.5; shot "$tag-ctl-s3"
        sdiff "$tag-ctl3-forced-vs-clean" "$tag-ctl-s0" "$tag-ctl-s3"
    else
        phase_log "$tag(A): remnant after 3 s: $c1 (CHANGED = gone by itself: whole-surface commits repaint everything)"
        sdiff "$tag-ctl3-3s-later-vs-clean" "$tag-ctl-s0" "$tag-ctl-s2"
    fi
    for i in 1 2 3; do
        phase_log "--- $tag($arm) open and close $i"
        shot "$tag-oc$i-P"
        hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
        gx 'pkill -x foot; echo foot closed' > /dev/null; sleep 1.5
        cmp3 "$tag-close$i" "$tag-oc$i-P"
    done
    phase_log "$tag($arm): damage_tracking $(dt_readback)"
}
run_arm B B1
run_arm A A1
run_arm A A2
run_arm B B2
phase_log "--- verdicts"
awk -F'\t' '{ v=$2; sub(/.*verdict=/,"",v); b=$2; sub(/.*bbox_outside=/,"",b); sub(/ .*/,"",b); printf "%-44s %-11s outside-clock bbox %s\n", $1, v, b }' "$PHASE_OUT/diffs.tsv"
phase_log "V2 counter-check done"
