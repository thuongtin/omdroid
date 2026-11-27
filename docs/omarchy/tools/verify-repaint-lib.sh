#!/usr/bin/env bash
# verify-repaint-lib.sh -- the proven forced-repaint method of V2 (phase 9), as functions for later phases.
# Source after verify-common.sh. Needs HL/TRACE unset or set as in phase 9; works with the trace off.
#   forcing step: debug.damage_tracking 0 for 1.5 s, then 2 (proved in phase 9: it erases a remnant painted
#   straight into cage's X window and shows damaged commits in the trace; the bare vfr=false re-assert
#   does neither).
shot() { "$TOOLS/shot.sh" "$1" > /dev/null 2>&1; }
verdict_of() { sed -n 's/.*verdict=\([A-Z_]*\).*/\1/p'; }
sdiff() { # $1 row name, $2 and $3 shot names: prints the row, remembers the verdict in LAST_VERDICT
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
dt_readback() { "$TOOLS/sx.sh" 'hyprctl getoption debug:damage_tracking' 12 2>&1 | grep -aE 'int:' | head -1 | tr -d '\r'; }
cmp3() { # $1 name, $2 the frame taken before the event (or "-"): after-event frame, forced frame, diffs
    local n=$1 p=$2
    sleep 3; shot "$n-A"
    force_A; sleep 2; shot "$n-F"
    sdiff "$n-after-vs-forced" "$n-A" "$n-F"
    if [ "$p" != - ]; then
        sdiff "$n-before-vs-after" "$p" "$n-A"
        sdiff "$n-before-vs-forced" "$p" "$n-F"
    fi
}
