#!/usr/bin/env bash
# verify-p3-session-end.sh -- R11 S5 phase 3 (run under the tablet lock; see verify-common.sh):
#   V6  session end and the error screen (r3-host-report.md rows H10-H15):
#       (1) the guest ends cleanly from inside (Hyprland exits 0): ended screen, Start again;
#       (2) Hyprland is killed after 30 s (non-zero exit, no retry): ended screen with the code;
#       (3) the session dies at launch (session.env `exit 7`): failed-launch error screen, then the
#           file is put back and Start again brings the desktop back.
#       Every screen is dumped (uiautomator text) and screenshotted for viewing.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
trap 'owner_restore' EXIT
trap 'exit 130' INT TERM

wait_launcher() { # $1 seconds: wait for the launcher activity on top
    local i
    for i in $(seq 1 "$1"); do
        case "$(top_activity)" in *LauncherActivity*) echo "launcher on top after ~${i}s"; return 0 ;; esac
        sleep 1
    done
    echo "launcher never on top in $1 s (top=$(top_activity))"; return 1
}
launch_logs() { adb_ logcat -d -v time -s Phoshdroid:I ProotService:I 2> /dev/null | grep -aE 'launch:|ProotService' | cut -c1-190 | tail -${1:-14} | sed 's/^/    log: /'; }
press_start_again() { # $1 name of the ui dump
    if ! ui_tap 'Start again' "$1"; then
        phase_log "no Start again node on screen; using the launcher icon path instead"
        adb_ shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $PKG/.LauncherActivity > /dev/null 2>&1
    fi
    local i t0; t0=$(date +%s)
    for i in $(seq 1 90); do
        case "$(top_activity)" in *MainActivity*) if probe_q | grep -q 'VERDICT: PASS'; then phase_log "desktop back after $(( $(date +%s) - t0 )) s: $(probe_q)"; return 0; fi ;; esac
        sleep 1
    done
    phase_log "desktop NOT back after 90 s: top=$(top_activity) $(probe_q)"; return 1
}

"$TOOLS/coldstart.sh" 1 --tag v6-base 2>&1 | grep -E '^(RUN|SUMMARY)'
APP0=$(app_pid)
phase_log "baseline: app pid $APP0, Hyprland pid $(hypr_pid), $(probe_q), top $(top_activity)"

phase_log "=== V6.1: clean exit from inside (Hyprland exit, rc 0)"
sleep 35
adb_ logcat -c
hcq '/dispatch hl.dsp.exit()' > /dev/null
sleep 3
phase_log "Hyprland pid after exit request: '$(hypr_pid)'"
if [ -n "$(hypr_pid)" ]; then phase_log "exit dispatch did not end it; SIGTERM to the session's own Hyprland"; gx 'pkill -TERM -x Hyprland; echo sent'; fi
wait_launcher 40
sleep 3
android_shot v6-1-ended-clean
ui_dump v6-1
launch_logs 14
press_start_again v6-1
android_shot v6-1-restarted
phase_log "after: app pid $(app_pid) (was $APP0), Hyprland pid $(hypr_pid)"
launch_logs 14

phase_log "=== V6.2: Hyprland killed 35 s into the session (non-zero exit, past the retry window)"
sleep 35
adb_ logcat -c
gx 'pkill -KILL -x Hyprland; echo killed'
wait_launcher 40
sleep 3
android_shot v6-2-ended-kill
ui_dump v6-2
launch_logs 14
press_start_again v6-2
android_shot v6-2-restarted
phase_log "after: app pid $(app_pid) (was $APP0), Hyprland pid $(hypr_pid)"

phase_log "=== V6.3: the session dies at launch (session.env: exit 7)"
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.config/omdroid
printf 'echo r11-verify-forced-exit\nexit 7\n' > "$PHASE_OUT/session.env.die"
adb_ shell am force-stop $PKG; sleep 2
gpush_to "$PHASE_OUT/session.env.die" /home/omarchy/.config/omdroid/session.env
adb_ logcat -c
adb_ shell input keyevent KEYCODE_WAKEUP
adb_ shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $PKG/.LauncherActivity > /dev/null 2>&1
phase_log "launched with the dying session.env"
for i in $(seq 1 60); do
    if adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -aqE 'launch: (failed|ended-screen)'; then break; fi
    sleep 1
done
sleep 4
phase_log "after ~${i}s: top $(top_activity), app pid $(app_pid)"
android_shot v6-3-failed-launch
ui_dump v6-3
launch_logs 24
phase_log "putting the owner's session.env back, then Start again"
_restore_guest_file .config/omdroid/session.env
press_start_again v6-3
android_shot v6-3-recovered
launch_logs 8
phase_log "V6 done"
