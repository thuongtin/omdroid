#!/usr/bin/env bash
# verify-p9-repaint2.sh -- R11 S5 phase 9 (run under the tablet lock; see verify-common.sh): V2 REDONE.
#   Phase 2 (and R10 run 5) forced the repaint with `hl.config({ debug = { vfr = false } })`. S1 measured
#   that this step damages nothing (0 damaged commits of 233 and 256), so those diffs compared the
#   after-event frame with itself. This phase
#     1. finds a forcing step that PROVABLY repaints the whole output, in a session with the commit
#        trace on: a remnant is painted straight into cage's X window (verify-xcorrupt.py), the bare
#        `vfr = false` re-assert must leave it (control: the instrument sees a remnant and the old step
#        repaints nothing), the candidate step must remove it and show non-empty damage commits in the
#        trace. Candidates in order: damage_tracking 0 then 2; vfr true then false; a monitor re-apply.
#     2. in a second session without the trace, with the same two controls repeated, judges toast fade,
#        foot open and close, a scrolling terminal, rotation and back, each THREE times, against the
#        proven forcing step AND against the frame taken before the event where the screen returns to
#        the earlier state. Every non-zero diff leaves a before | after | diff crop.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
T_START=$(date +%s)
DEADLINE=$((T_START + 1140))
: > "$PHASE_OUT/diffs.tsv"
TRACE=""
FORCE=none
p9_cleanup() { gx 'rm -f /etc/phoshdroid/trace' > /dev/null 2>&1; true; }
trap 'p9_cleanup; owner_restore' EXIT
trap 'exit 130' INT TERM

adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache
gpush_to "$VT/verify-xcorrupt.py" /home/omarchy/.cache/verify-xcorrupt.py
gpush_to "$VT/verify-scroll.sh" /home/omarchy/.cache/verify-scroll.sh

shot() { "$TOOLS/shot.sh" "$1" > /dev/null 2>&1; }
verdict_of() { sed -n 's/.*verdict=\([A-Z_]*\).*/\1/p'; }
sdiff() { # $1 row name, $2 and $3 shot names: prints the row, remembers the verdict
    local r tmp; tmp=$(mktemp)
    python3 "$VTOOLS/verify-scrdiff.py" "$OMARCHY_SHOTS/$2.png" "$OMARCHY_SHOTS/$3.png" --crop "$PHASE_OUT/crops/$1.png" > "$tmp" 2>&1
    r=$(head -1 "$tmp"); rm -f "$tmp"
    echo "  $1: $r"
    printf '%s\t%s\n' "$1" "$r" >> "$PHASE_OUT/diffs.tsv"
    LAST_VERDICT=$(echo "$r" | verdict_of)
}
corrupt() { gx 'DISPLAY=:0 python3 /home/omarchy/.cache/verify-xcorrupt.py 1400 900 400 250' 2>&1 | tail -1; }
bare_reassert() { hcq '/eval hl.config({ debug = { vfr = false } })' > /dev/null; }
force_A() { hcq '/eval hl.config({ debug = { damage_tracking = 0 } })' > /dev/null; sleep 1.5; hcq '/eval hl.config({ debug = { damage_tracking = 2 } })' > /dev/null; sleep 1; }
force_B() { hcq '/eval hl.config({ debug = { vfr = true } })' > /dev/null; sleep 1; hcq '/eval hl.config({ debug = { vfr = false } })' > /dev/null; sleep 1; }
force_D() {
    local mode
    mode=$(hcq j/monitors | python3 -c 'import json,sys
t=sys.stdin.read(); m=json.loads(t[t.find("["):])[0]; print("%dx%d@%.2f" % (m["width"], m["height"], m["refreshRate"]))')
    hcq "/eval hl.monitor({ output = \"\", mode = \"$mode\", position = \"auto\", scale = 2, transform = 0 })" > /dev/null
    sleep 3
}
dt_readback() { "$TOOLS/sx.sh" 'hyprctl getoption debug:damage_tracking' 12 2>&1 | grep -aE 'int:' | head -1 | tr -d '\r'; }
# commit trace helpers (session 1 only)
hlog_path() { gx 'ls -t /run/user/1000/hypr/*/hypr*.log | head -1' | tail -1 | tr -d '\r '; }
hlog_size() { gx "stat -c %s $HL" | tail -1 | tr -d '\r '; }
hlog_counts() { # $1 offset
    gx "tail -c +$(( $1 + 1 )) $HL | awk '/commit damage/{ if (\$0 ~ /whole surface/) w++; else if (\$0 ~ /damage 0 rect/) z++; else n++ } END{print \"zero_rect=\" z+0 \" with_rects=\" n+0 \" whole_surface=\" w+0}'" | tail -1 | tr -d '\r'
}

try_force() { # $1 name, $2 function: one corruption cycle; sets TRY_OK=1 when the step proved itself
    local name=$1 fn=$2 off cb cs d
    TRY_OK=0
    sleep 3; shot "$name-s0"
    phase_log "$name: $(corrupt)"
    sleep 1.5; shot "$name-s1"
    sdiff "$name-ctl1-clean-vs-painted" "$name-s0" "$name-s1"; [ "$LAST_VERDICT" = CHANGED ] || phase_log "$name: CONTROL 1 FAILED, the painted remnant is not visible to the diff"
    local c1=$LAST_VERDICT
    [ -n "$TRACE" ] && off=$(hlog_size)
    bare_reassert; sleep 2.5
    [ -n "$TRACE" ] && cb=$(hlog_counts "$off") || cb="trace off"
    shot "$name-s2"
    sdiff "$name-ctl2-bare-reassert-painted-vs-after" "$name-s1" "$name-s2"; local c2=$LAST_VERDICT
    phase_log "$name: bare vfr=false re-assert: commits [$cb]; remnant $([ "$c2" = ZERO ] || [ "$c2" = CLOCK_ONLY ] && echo "STILL THERE (the step repaints nothing)" || echo "changed: $c2")"
    [ -n "$TRACE" ] && off=$(hlog_size)
    $fn
    sleep 1.5
    [ -n "$TRACE" ] && cs=$(hlog_counts "$off") || cs="trace off"
    shot "$name-s3"
    sdiff "$name-forced-vs-clean" "$name-s0" "$name-s3"; local c3=$LAST_VERDICT
    phase_log "$name: forcing step $fn: commits [$cs]; screen vs the clean frame: $c3; $(dt_readback)"
    # the bar clock may turn over between two shots, so CLOCK_ONLY counts as "nothing but the clock"
    if [ "$c1" = CHANGED ] && { [ "$c2" = ZERO ] || [ "$c2" = CLOCK_ONLY ]; } && { [ "$c3" = ZERO ] || [ "$c3" = CLOCK_ONLY ]; }; then TRY_OK=1; fi
}

# ---------------------------------------------------------------- session 1: prove the forcing step with the trace
phase_log "=== part 1: a forcing step that provably repaints (trace on)"
gx 'touch /etc/phoshdroid/trace'
TRACE=1
"$TOOLS/coldstart.sh" 1 --tag v9-s1 2>&1 | grep -E '^(RUN|SUMMARY)'
sleep 25
HL=$(hlog_path)
arm_check "session 1 (trace)"
phase_log "$(probe_q); $(devices_line); $(monitor_line); log $HL; $(dt_readback)"
for cand in A B D; do
    try_force "try-$cand" "force_$cand"
    if [ "$TRY_OK" = 1 ]; then FORCE=force_$cand; phase_log "forcing step chosen: $FORCE"; break; fi
    phase_log "candidate $cand did not prove itself (see the rows above)"
done
if [ "$FORCE" != none ]; then
    try_force "repeat-$cand" "$FORCE"
    phase_log "repeat of the chosen step: TRY_OK=$TRY_OK"
    [ "$TRY_OK" = 1 ] || FORCE=none
fi
phase_log "forcing step after part 1: $FORCE"

# ---------------------------------------------------------------- session 2: the scenarios, no trace
phase_log "=== part 2: scenarios (no trace)"
gx 'rm -f /etc/phoshdroid/trace'
TRACE=""
"$TOOLS/coldstart.sh" 1 --tag v9-s2 2>&1 | grep -E '^(RUN|SUMMARY)'
sleep 25
phase_log "$(probe_q); $(monitor_line); $(dt_readback)"
if [ "$FORCE" != none ]; then
    try_force "ctl-s2" "$FORCE"
    phase_log "controls repeated in the scenario session: TRY_OK=$TRY_OK"
fi

wait_probe() { # $1 label: poll probe.sh every 2 s (max 40 s) and say when the desktop was whole again
    local t0 i v; t0=$(date +%s)
    sleep 6
    for i in $(seq 1 17); do
        v=$(probe_q); case "$v" in *PASS*) break ;; esac; sleep 2
    done
    phase_log "$1: $v after $(( $(date +%s) - t0 )) s, app pid $(app_pid)"
    sleep 2
}
time_left() { [ "$(date +%s)" -lt "$DEADLINE" ]; }
cmp3() { # $1 name, $2 the frame taken before the event (or "-"): after-event frame, forced frame, three diffs
    local n=$1 p=$2
    sleep 3; shot "$n-A"
    if [ "$FORCE" != none ]; then
        $FORCE; sleep 2; shot "$n-F"
        sdiff "$n-after-vs-forced" "$n-A" "$n-F"
    else
        echo "  $n: no forcing step proved, only the before-frame comparison below"
    fi
    if [ "$p" != - ]; then
        sdiff "$n-before-vs-after" "$p" "$n-A"
        [ "$FORCE" != none ] && sdiff "$n-before-vs-forced" "$p" "$n-F"
    fi
}
for i in 1 2 3; do
    time_left || { phase_log "deadline reached, toast $i skipped"; continue; }
    phase_log "--- toast fade run $i"
    shot "toast-$i-P"
    "$TOOLS/sx.sh" "notify-send -t 2500 'R11 V2 redo toast $i' 'this toast fades out'" 10 > /dev/null 2>&1
    sleep 1; shot "toast-$i-showing"; sleep 9
    cmp3 "toast-$i" "toast-$i-P"
done
for i in 1 2 3; do
    time_left || { phase_log "deadline reached, open/close $i skipped"; continue; }
    phase_log "--- foot open and close run $i"
    shot "oc-$i-P"
    hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
    cmp3 "open-$i" -
    gx 'pkill -x foot; echo foot closed' > /dev/null; sleep 1.5
    cmp3 "close-$i" "oc-$i-P"
done
for i in 1 2 3; do
    time_left || { phase_log "deadline reached, scroll $i skipped"; continue; }
    phase_log "--- scrolling terminal run $i"
    shot "sc-$i-P"
    gx 'rm -f /tmp/verify-scroll-stop'
    hcq '/dispatch hl.dsp.exec_cmd("foot bash /home/omarchy/.cache/verify-scroll.sh")' > /dev/null; sleep 6
    shot "sc-$i-running"
    gx 'touch /tmp/verify-scroll-stop' > /dev/null; sleep 1
    cmp3 "scroll-stop-$i" -
    gx 'pkill -x foot; echo foot closed' > /dev/null; sleep 1.5
    cmp3 "scroll-close-$i" "sc-$i-P"
done
for i in 1 2 3; do
    time_left || { phase_log "deadline reached, rotation $i skipped"; continue; }
    phase_log "--- rotation and back run $i"
    shot "rot-$i-P"
    hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
    "$TOOLS/screen.sh" rot 0 2>&1 | grep -E 'cur=' | head -1
    wait_probe "after rotate"
    cmp3 "rot-$i-portrait-open" -
    gx 'pkill -x foot; echo foot closed' > /dev/null; sleep 1.5
    cmp3 "rot-$i-portrait-closed" -
    "$TOOLS/screen.sh" rot 1 2>&1 | grep -E 'cur=' | head -1
    wait_probe "after rotate back"
    cmp3 "rot-$i-landscape" "rot-$i-P"
done
phase_log "damage_tracking at the end: $(dt_readback)"
phase_log "--- diffs.tsv, verdict column only"
awk -F'\t' '{ v=$2; sub(/.*verdict=/,"",v); printf "%-48s %s\n", $1, v }' "$PHASE_OUT/diffs.tsv"
phase_log "V2 redo done after $(( $(date +%s) - T_START )) s"
