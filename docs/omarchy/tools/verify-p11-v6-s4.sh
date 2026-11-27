#!/usr/bin/env bash
# verify-p11-v6-s4.sh -- R11 S5 phase 11 (run under the tablet lock; see verify-common.sh): V6 RE-VERIFIED on S4's build.
#   Build: the APK in <scratch>/r11/complete/apk/ whose sha256 starts 9dae471b (omdroid-complete-60d0b95.apk), installed
#   as the build under test; the EXIT trap puts the owner's R10 build and state back.
#   S4's claims to re-check independently: a session exit from inside shows the ended screen with the reason within
#   2 s, no ANR, Start again brings the desktop back; exit 7 at launch shows the error text. Run three clean exits to
#   see the exit codes (S4 saw a Hyprland segfault at exit, exit 139, in 4 of 9) and record what this run shows.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
. "$VT/verify-session-lib.sh"
ensure_r10
: > "$PHASE_OUT/diffs.tsv"
trap 'owner_restore' EXIT
trap 'exit 130' INT TERM
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.config/omdroid

clean_exit() { # $1 run number: exit from inside, screenshot at +2 s, ANR check, Start again
    local n=$1 t0
    sleep 30
    adb_ logcat -c
    t0=$(date +%s)
    hcq '/dispatch hl.dsp.exit()' > /dev/null
    sleep 10
    if [ -n "$(hypr_pid)" ]; then phase_log "run $n: the exit dispatch did not end Hyprland; SIGTERM to the session's own Hyprland"; gx 'pkill -TERM -x Hyprland; echo sent'; fi
    wait_launcher 30
    for i in $(seq 1 12); do
        adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -aq 'launch: ended-screen' && break
        sleep 1
    done
    phase_log "run $n: launcher/screen after $(( $(date +%s) - t0 )) s; Hyprland pid '$(hypr_pid)'"
    sleep 1
    android_shot "v6s-$n-ended-2s"
    screen_report "v6s-$n"
    exit_timing "v6s-$n"
    press_start_again "v6s-$n"
    android_shot "v6s-$n-restarted"
    phase_log "run $n after restart: app pid $(app_pid), Hyprland pid $(hypr_pid), $(probe_q)"
}

phase_log "=== V6.1/6.2: clean exit from inside, three runs"
"$TOOLS/coldstart.sh" 1 --tag v6s-base 2>&1 | grep -E '^(RUN|SUMMARY)'
phase_log "baseline: app pid $(app_pid), Hyprland pid $(hypr_pid), $(probe_q), top $(top_activity)"
for n in 1 2 3; do
    phase_log "--- clean exit run $n"
    clean_exit "$n"
done

phase_log "=== V6.3: the session dies at launch (session.env: exit 7)"
printf 'echo r11-verify-forced-exit\nexit 7\n' > "$PHASE_OUT/session.env.die"
adb_ shell am force-stop $PKG; sleep 2
gpush_to "$PHASE_OUT/session.env.die" /home/omarchy/.config/omdroid/session.env
adb_ logcat -c
adb_ shell input keyevent KEYCODE_WAKEUP
adb_ shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $PKG/.LauncherActivity > /dev/null 2>&1
for i in $(seq 1 60); do
    adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -aqE 'launch: (failed|ended-screen)' && break
    sleep 1
done
sleep 3
phase_log "after ~${i}s: top $(top_activity), app pid $(app_pid)"
android_shot "v6s-3-failed-launch"
screen_report "v6s-3"
exit_timing "v6s-3"
phase_log "putting the owner's session.env back, then Start again"
_restore_guest_file .config/omdroid/session.env
press_start_again "v6s-3"
android_shot "v6s-3-recovered"
exit_timing "v6s-3-recovered"
phase_log "V6 on S4's build done"
