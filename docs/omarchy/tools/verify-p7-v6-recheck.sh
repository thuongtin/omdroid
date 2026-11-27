#!/usr/bin/env bash
# verify-p7-v6-recheck.sh -- R11 S5 phase 7 (run under the tablet lock; see verify-common.sh):
#   V6 counter-check. Phase 3 found that after the guest session ended the Omdroid screen was blank,
#   Android showed "Omdroid isn't responding" (an ANR trace was written) and the Start button never
#   appeared. This phase repeats the three ways a session ends WITHOUT touching the screen first
#   (no uiautomator, no screencap) and captures, for each, what the app's main thread is doing: its
#   state under /proc, the Java stacks of every thread through JDWP (jdb, needs the debuggable build
#   under test and JDB pointing at a jdb binary), the app's own log lines and whether the system
#   raised an ANR. The previous phase's V6.2 never ran (the app was already wedged by V6.1, so there
#   was no Hyprland to kill); each case here starts from a force-stop.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
JDB=${JDB:-jdb}
PORT=8761
trap 'adb_ forward --remove tcp:$PORT > /dev/null 2>&1; owner_restore' EXIT
trap 'exit 130' INT TERM

state_script=$PHASE_OUT/state.sh
cat > "$state_script.tpl" << 'EOF'
pid=__PID__
echo "main thread: state=$(cut -d' ' -f3 /proc/$pid/task/$pid/stat) wchan=$(cat /proc/$pid/task/$pid/wchan) syscall=$(cut -c1-40 /proc/$pid/task/$pid/syscall)"
for t in /proc/$pid/task/*; do echo "$(cut -d' ' -f2,3 $t/stat) wchan=$(cat $t/wchan)"; done | sort | uniq -c | sort -rn | head -10
EOF
main_state() { # $1 label
    local pid; pid=$(app_pid)
    [ -n "$pid" ] || { phase_log "$1: no app process"; return; }
    sed "s/__PID__/$pid/" "$state_script.tpl" > "$state_script"
    phase_log "$1: app pid $pid"
    runas "$state_script" 2>&1 | sed 's/^/    /'
}
java_stacks() { # $1 label
    local pid; pid=$(app_pid)
    [ -n "$pid" ] || { phase_log "$1: no app process for jdb"; return; }
    phase_log "$1: jdwp pids $(adb_ jdwp | tr '\n' ' ')"
    adb_ forward --remove tcp:$PORT > /dev/null 2>&1
    adb_ forward tcp:$PORT jdwp:$pid > /dev/null 2>&1
    { sleep 2; echo suspend; sleep 1; echo 'where all'; sleep 8; echo resume; sleep 1; echo exit; } | timeout 50 "$JDB" -attach localhost:$PORT > "$PHASE_OUT/jdb-$1.txt" 2>&1
    adb_ forward --remove tcp:$PORT > /dev/null 2>&1
    phase_log "$1: jdb wrote $(wc -l < "$PHASE_OUT/jdb-$1.txt") lines (first line: $(head -c 120 "$PHASE_OUT/jdb-$1.txt" | head -1)); the main thread:"
    awk '/^main:/{p=1; print; next} /^[A-Za-z0-9_ .-]+:$/{p=0} p' "$PHASE_OUT/jdb-$1.txt" | head -40 | sed 's/^/    /'
}
anr_check() { # $1 label
    phase_log "$1: system events: [$(adb_ logcat -b events -d 2> /dev/null | grep -aE 'am_anr' | tail -2 | cut -c1-160 | tr '\n' '|')] window: [$(adb_ shell dumpsys window 2> /dev/null | grep -ai 'not responding\|AppNotResponding\|anr' | head -2 | cut -c1-140 | tr '\n' '|')]"
    phase_log "$1: newest exit records: $(adb_ shell dumpsys activity exit-info $PKG 2> /dev/null | grep -aE 'timestamp=|trace=' | head -4 | cut -c1-170 | tr '\n' '|')"
}
app_log() { # $1 label, $2 lines
    phase_log "$1: the app's own log, last $2 lines (all tags, by pid)"
    adb_ logcat -d -v time --pid="$(app_pid)" 2> /dev/null | grep -avE 'removed stale' | tail -"$2" | cut -c1-190 | sed 's/^/    /'
}
settle_ui() { # after the stack work: the first time the screen is touched
    android_shot "$1"
    ui_dump "$1" | head -12
    phase_log "$1: ui dump bytes $(wc -c < "$PHASE_OUT/ui-$1.xml")"
}
cold() { # $1 tag
    "$TOOLS/coldstart.sh" 1 --tag "$1" 2>&1 | grep -E '^(RUN|SUMMARY)'
    sleep 35
    phase_log "baseline: app pid $(app_pid), Hyprland pid $(hypr_pid), $(probe_q)"
}

phase_log "=== A: clean exit from inside (Hyprland exits 0)"
cold v7a-base
adb_ logcat -c; adb_ logcat -b events -c
hcq '/dispatch hl.dsp.exit()' > /dev/null
sleep 3
phase_log "A +3 s: Hyprland pid '$(hypr_pid)', top $(top_activity)"
main_state "A +3 s"
sleep 4
main_state "A +7 s"
java_stacks "A-jdb"
app_log "A" 25
anr_check "A"
settle_ui "v7a-screen"
phase_log "A recovery attempt: icon tap"
adb_ shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $PKG/.LauncherActivity > /dev/null 2>&1
sleep 10
phase_log "A after the icon tap: top $(top_activity), Hyprland pid '$(hypr_pid)', $(probe_q)"
app_log "A after tap" 10

phase_log "=== B: Hyprland killed 40 s into the session"
adb_ shell am force-stop $PKG; sleep 3
cold v7b-base
sleep 8
adb_ logcat -c; adb_ logcat -b events -c
HB=$(hypr_pid)
gx 'pkill -KILL -x Hyprland; echo killed'
sleep 3
phase_log "B +3 s: Hyprland was '$HB', now '$(hypr_pid)', top $(top_activity)"
main_state "B +3 s"
sleep 4
main_state "B +7 s"
java_stacks "B-jdb"
app_log "B" 25
anr_check "B"
settle_ui "v7b-screen"

phase_log "=== C: the session dies at launch (session.env: exit 7)"
adb_ shell am force-stop $PKG; sleep 3
printf 'echo r11-verify-forced-exit\nexit 7\n' > "$PHASE_OUT/session.env.die"
gpush_to "$PHASE_OUT/session.env.die" /home/omarchy/.config/omdroid/session.env
adb_ logcat -c; adb_ logcat -b events -c
adb_ shell input keyevent KEYCODE_WAKEUP
adb_ shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $PKG/.LauncherActivity > /dev/null 2>&1
sleep 4
main_state "C +4 s"
sleep 4
main_state "C +8 s"
java_stacks "C-jdb"
app_log "C" 25
anr_check "C"
settle_ui "v7c-screen"
phase_log "V6 recheck done"
