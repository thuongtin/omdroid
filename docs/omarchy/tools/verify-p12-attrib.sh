#!/usr/bin/env bash
# verify-p12-attrib.sh -- R11 S5 phase 12 (run under the tablet lock; see verify-common.sh): attribution of V2's residue.
#   Phase 10 could not settle it: in arm A (AQ_WAYLAND_FULL_DAMAGE=1) the painted control is REPAIRED before any
#   screenshot lands. B1 shows the 400x250 rectangle, A1 and A2 show the clean desktop, same window id and geometry
#   (0,0,3200,1970): a frame landed between the paint and the shot, ~1.5 s = ~90 commits. A paint widget can never
#   survive in that arm, so arm A gets a control that does not need it to survive:
#     - `verify-xcorrupt.py paint-read` reads the rectangle back out of cage's window with XGetImage, ms after the
#       draw: magenta present in the WINDOW while the SCREEN stays clean = the paint landed and the screen repainted
#       over it. Plus the commit trace: with FULL_DAMAGE every commit must read whole_surface.
#   Arm B keeps the pixel control (paint visible, survives 3 s, erased by the forcing step).
#   The event: the cursor is parked at a fixed spot before every shot (the pointer image was 2037 of the 2322 px
#   that phase 10 read as an event difference), the foot client must be gone from Hyprland's client list before the
#   after frame, and each run also takes a STEADY control (two shots 3 s apart, no event) so a 1-level difference
#   can be told from an event-caused one.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
. "$VT/verify-repaint-lib.sh"
ensure_r10
: > "$PHASE_OUT/diffs.tsv"
T_START=$(date +%s); DEADLINE=$((T_START + 780))
TRACE=""
p12_cleanup() { gx 'rm -f /etc/phoshdroid/trace' > /dev/null 2>&1; true; }
trap 'p12_cleanup; owner_restore' EXIT
trap 'exit 130' INT TERM
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache $ROOTS/omarchy/home/omarchy/.config/omdroid
gpush_to "$VT/verify-xcorrupt.py" /home/omarchy/.cache/verify-xcorrupt.py
printf '%s\n' 'AQ_WAYLAND_FULL_DAMAGE=1' > "$PHASE_OUT/session.env.A"
printf '%s\n' '# r11 verify: arm B, no switches' > "$PHASE_OUT/session.env.B"

park() { hcq '/dispatch movecursor 3160 1760' > /dev/null 2>&1; sleep 0.6; }
clients() { hcq j/clients 2>/dev/null | python3 -c 'import json,sys
t=sys.stdin.read()
try: c=json.loads(t[t.find("["):])
except Exception: print("clients=unknown"); raise SystemExit
print("clients=%d %s" % (len(c), ",".join(sorted(x.get("class","?") for x in c))))' 2>/dev/null || echo "clients=unknown"; }
close_foot() { # kill foot and wait for Hyprland to drop the client
    gx 'pkill -x foot; echo foot closed' > /dev/null; local i
    for i in $(seq 1 12); do
        case "$(clients)" in *foot*) sleep 1 ;; *) phase_log "foot gone from the client list after ~${i}s ($(clients))"; return 0 ;; esac
    done
    phase_log "foot still in the client list after 12 s: $(clients); killactive"
    hcq '/dispatch killactive' > /dev/null; sleep 2; phase_log "after killactive: $(clients)"
}
hlog_path() { gx 'ls -t /run/user/1000/hypr/*/hypr*.log | head -1' | tail -1 | tr -d '\r '; }
hlog_size() { gx "stat -c %s $HL" | tail -1 | tr -d '\r '; }
hlog_counts() { gx "tail -c +$(( $1 + 1 )) $HL | awk '/commit damage/{ if (\$0 ~ /whole surface/) w++; else if (\$0 ~ /damage 0 rect/) z++; else n++ } END{print \"zero_rect=\" z+0 \" with_rects=\" n+0 \" whole_surface=\" w+0}'" | tail -1 | tr -d '\r'; }

run_arm() { # $1 arm letter, $2 tag
    local arm=$1 tag=$2 i off
    if [ "$arm" = A ]; then gx 'touch /etc/phoshdroid/trace'; TRACE=1; else gx 'rm -f /etc/phoshdroid/trace'; TRACE=""; fi
    gpush_to "$PHASE_OUT/session.env.$arm" /home/omarchy/.config/omdroid/session.env
    "$TOOLS/coldstart.sh" 1 --tag "v12-$tag" 2>&1 | grep -E '^(RUN|SUMMARY)'
    sleep 25
    arm_check "$tag($arm)"
    [ "$arm" = A ] && HL=$(hlog_path)
    phase_log "$tag($arm): $(probe_q); $(clients); $(dt_readback)"
    phase_log "--- $tag($arm) steady control (two shots 3 s apart, no event)"
    park; phase_log "$tag($arm): cursor at '$(hcq cursorpos 2>/dev/null | tr -d '\r')' (parked at 3160,1760)"
    shot "$tag-steady1"; sleep 3; park; shot "$tag-steady2"
    sdiff "$tag-steady-3s-apart" "$tag-steady1" "$tag-steady2"
    park; sleep 1; shot "$tag-ctl-s0"
    if [ "$arm" = A ]; then
        phase_log "--- $tag(A) control: paint, read the window back, then the screen"
        [ -n "$TRACE" ] && off=$(hlog_size)
        phase_log "$tag: $(gx 'DISPLAY=:0 python3 /home/omarchy/.cache/verify-xcorrupt.py paint-read 1400 900 400 250' 2>&1 | tr '\n' '|')"
        sleep 1.5; park; shot "$tag-ctl-s1"
        sdiff "$tag-ctl-screen-after-paint" "$tag-ctl-s0" "$tag-ctl-s1"
        [ -n "$TRACE" ] && phase_log "$tag(A): commits in the paint window: [$(hlog_counts "$off")] (every commit must be whole_surface)"
        phase_log "$tag(A): the control is the read-back (paint in the window) against the screen (no paint): if the screen diff is ZERO and the read-back found magenta, a frame repaired it"
    else
        phase_log "--- $tag(B) control: paint, visible, survives 3 s, erased by the forcing step"
        phase_log "$tag: $(corrupt)"
        sleep 1.5; park; shot "$tag-ctl-s1"
        sdiff "$tag-ctl-clean-vs-painted" "$tag-ctl-s0" "$tag-ctl-s1"
        sleep 3; park; shot "$tag-ctl-s2"
        sdiff "$tag-ctl-painted-vs-3s-later" "$tag-ctl-s1" "$tag-ctl-s2"
        force_A; sleep 1.5; park; shot "$tag-ctl-s3"
        sdiff "$tag-ctl-forced-vs-clean" "$tag-ctl-s0" "$tag-ctl-s3"
    fi
    for i in 1 2 3; do
        [ "$(date +%s)" -lt "$DEADLINE" ] || { phase_log "$tag: deadline reached, close $i skipped"; continue; }
        phase_log "--- $tag($arm) open and close $i ($(clients))"
        park; shot "$tag-oc$i-P"
        hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null; sleep 4
        phase_log "$tag oc$i with foot open: $(clients)"
        close_foot
        sleep 3; park; shot "$tag-close$i-A"
        sdiff "$tag-close$i-before-vs-after" "$tag-oc$i-P" "$tag-close$i-A"
        force_A; sleep 1.5; park; shot "$tag-close$i-F"
        sdiff "$tag-close$i-after-vs-forced" "$tag-close$i-A" "$tag-close$i-F"
    done
    phase_log "$tag($arm): damage_tracking $(dt_readback)"
}
run_arm B B1
run_arm A A1
phase_log "--- verdicts"
awk -F'\t' '{ v=$2; b=$2; sub(/.*verdict=/,"",v); split(v,a," "); sub(/.*bbox_outside=/,"",b); split(b,c," "); printf "%-40s %-10s outside_clock=%s bbox_outside=%s\n", $1, a[1], c[1], c[2] }' "$PHASE_OUT/diffs.tsv"
phase_log "phase 12 done after $(( $(date +%s) - T_START )) s"
