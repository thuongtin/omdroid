#!/usr/bin/env bash
# verify-p4-fresh-sudo.sh -- R11 S5 phase 4 (run under the tablet lock; see verify-common.sh):
#   V4  the fresh-image path for the patched aquamarine: the owner guest is parked, the app
#       extracts a fresh one, and in the very first session Hyprland must map
#       /etc/phoshdroid/lib/libaquamarine.so.13 and `hc.sh j/devices` must list wl_touch.
#   V5  sudo beyond `sudo id`, on that fresh guest (nothing of the owner's is touched): the
#       interactive prompt, Ctrl+C during `sudo sleep 30`, `omarchy-pkg-add` of one small package
#       and its removal. Keys are typed into a foot shell with `input text` / `input keycombination`.
#   The test guest this phase creates is deleted at the end; the owner guest is put back first.
set -u
VT=$(cd "$(dirname "$0")" && pwd)
. "$VT/verify-common.sh"
ensure_r10
REPO=$(cd "$TOOLS/../../.." && pwd)
LIB_REPO_SHA=$(sha256sum "$REPO/rootfs/overlay/etc/phoshdroid/lib/libaquamarine.so.13" | cut -c1-64)
BEFORE=" $(adb_ shell run-as $PKG ls $ROOTS | tr -d '\r' | grep '^omarchy-r11-test-' | tr '\n' ' ')"
phase_log "repo lib sha256 $LIB_REPO_SHA; test guests before: [$BEFORE]; installed-rootfs: $(adb_ shell run-as $PKG ls $ROOTS | tr -d '\r' | tr '\n' ' ')"

p4_cleanup() {
    owner_restore
    local d
    for d in $(adb_ shell run-as $PKG ls $ROOTS | tr -d '\r' | grep '^omarchy-r11-test-'); do
        case "$BEFORE" in *" $d "*) ;; *)
            phase_log "deleting the test guest this phase created: $d"
            adb_ shell run-as $PKG chmod -R u+rwX $ROOTS/$d > /dev/null 2>&1
            adb_ shell run-as $PKG rm -rf $ROOTS/$d
            phase_log "deleted rc=$?" ;;
        esac
    done
    phase_log "installed-rootfs now: $(adb_ shell run-as $PKG ls $ROOTS | tr -d '\r' | tr '\n' ' ')"
}
trap p4_cleanup EXIT
trap 'exit 130' INT TERM

type_text() { adb_ shell "input text '$(printf '%s' "$1" | sed 's/ /%s/g')'"; }
enter() { adb_ shell input keyevent KEYCODE_ENTER; }
wait_file() { # $1 name in the prefix tmp, $2 seconds
    local i
    for i in $(seq 1 "$2"); do
        adb_ shell run-as $PKG ls files/usr/tmp/$1 > /dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}
rc_file() { adb_ shell run-as $PKG cat files/usr/tmp/$1 2>&1 | tr -d '\r' | sed 's/^/    /'; }

phase_log "=== V4: fresh extraction"
park_owner_guest
adb_ logcat -c
adb_ shell input keyevent KEYCODE_WAKEUP
adb_ shell wm dismiss-keyguard > /dev/null 2>&1
T0=$(date +%s)
adb_ shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $PKG/.LauncherActivity > /dev/null 2>&1
for i in $(seq 1 130); do
    adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -aqE 'handover done|launch: failed|ended-screen' && break
    sleep 5
done
phase_log "launch finished after $(( $(date +%s) - T0 )) s (poll $i)"
adb_ logcat -d -v time -s Phoshdroid:I 2> /dev/null | grep -aE 'launch:' | cut -c1-170 | sed 's/^/    log: /' | head -40
for i in $(seq 1 40); do probe_q | grep -q 'VERDICT: PASS' && break; sleep 3; done
phase_log "fresh guest: $(probe_q), top $(top_activity)"
android_shot v4-fresh-desktop
phase_log "first-session count (session-started lines since the park): $(adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -ac 'session-started')"
phase_log "$(devices_line)"
arm_check fresh
H=$(hypr_pid)
F=$(mktemp)
cat > "$F" << EOF
echo "maps inode: \$(grep -a libaquamarine /proc/$H/maps | head -1 | awk '{print \$5}')"
echo "guest overlay lib inode: \$(stat -c %i $ROOTS/omarchy/etc/phoshdroid/lib/libaquamarine.so.13)"
echo "guest overlay lib sha256: \$(sha256sum $ROOTS/omarchy/etc/phoshdroid/lib/libaquamarine.so.13 | cut -c1-64)"
echo "image copy sha256 (/opt, stock): \$(sha256sum $ROOTS/omarchy/opt/omarchy-android/aquamarine/lib/libaquamarine.so.13 | cut -c1-64)"
EOF
runas "$F" | sed 's/^/    /'; rm -f "$F"
phase_log "repo lib sha256 $LIB_REPO_SHA (the guest overlay copy above must equal it)"
phase_log "overlay files the APK had to rewrite on this fresh guest: $(adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -ac 'guest-overlay updated') (0 = the image already carried the same bytes)"
adb_ logcat -d -s Phoshdroid:I 2> /dev/null | grep -a 'guest-overlay' | cut -c1-150 | head -12 | sed 's/^/    /'

phase_log "=== V5: sudo on the fresh guest"
sleep 20
"$TOOLS/sx.sh" 'sudo id; sudo -u omarchy id; sudo false; echo false-rc=$?' 15 2>&1 | sed 's/^/    sx: /'
adb_ shell run-as $PKG mkdir -p $ROOTS/omarchy/home/omarchy/.cache
for f in verify-v5-int.sh verify-v5-ctrlc-plain.sh verify-v5-ctrlc-sudo.sh verify-v5-pkgadd.sh; do gpush_to "$VT/$f" /home/omarchy/.cache/$f; done
hcq '/dispatch hl.dsp.exec_cmd("foot")' > /dev/null
sleep 6
phase_log "$(clients_line)"

phase_log "--- V5.1 the interactive prompt"
type_text ". /home/omarchy/.cache/verify-v5-int.sh"; enter
if wait_file v5-at-prompt 150; then
    sleep 5
    "$TOOLS/shot.sh" v5-1-at-prompt > /dev/null 2>&1
    type_text "n"
    sleep 1; "$TOOLS/shot.sh" v5-1-typed-n > /dev/null 2>&1
    enter
    wait_file v5-int.done 20 || phase_log "v5-int.done never appeared"
    sleep 1; "$TOOLS/shot.sh" v5-1-after > /dev/null 2>&1
else
    phase_log "the prompt marker never appeared (sync or install step stuck)"
    "$TOOLS/shot.sh" v5-1-stuck > /dev/null 2>&1
fi
rc_file v5-int.rc

phase_log "--- V5.2a control: plain sleep + Ctrl+C injection"
type_text ". /home/omarchy/.cache/verify-v5-ctrlc-plain.sh"; enter
wait_file v5-ctrlc-plain.started 15; sleep 3
adb_ shell input keycombination KEYCODE_CTRL_LEFT KEYCODE_C
sleep 2
rc_file v5-ctrlc-plain.rc
"$TOOLS/shot.sh" v5-2a-after-plain > /dev/null 2>&1

phase_log "--- V5.2b Ctrl+C during sudo sleep 30"
type_text ". /home/omarchy/.cache/verify-v5-ctrlc-sudo.sh"; enter
wait_file v5-ctrlc-sudo.started 15; sleep 4
"$TOOLS/shot.sh" v5-2b-sleeping > /dev/null 2>&1
adb_ shell input keycombination KEYCODE_CTRL_LEFT KEYCODE_C
sleep 3
rc_file v5-ctrlc-sudo.rc
echo "    stty flags after: $(adb_ shell run-as $PKG cat files/usr/tmp/v5-stty.txt 2>&1 | grep -oE '(-?echo|-?icanon|-?isig)( |;|$)' | tr '\n' ' ')"
type_text "echo typed-ok > /tmp/v5-typed.txt"
sleep 1; "$TOOLS/shot.sh" v5-2b-typed-line > /dev/null 2>&1
enter; sleep 2
rc_file v5-typed.txt
"$TOOLS/shot.sh" v5-2b-after-typed > /dev/null 2>&1
phase_log "bridge still alive: $("$TOOLS/sx.sh" 'sudo id' 15 2>&1 | head -1)"

phase_log "--- V5.3 omarchy-pkg-add and removal"
type_text ". /home/omarchy/.cache/verify-v5-pkgadd.sh"; enter
wait_file v5-pkgadd.done 240 || phase_log "pkg-add did not finish in 240 s"
sleep 1; "$TOOLS/shot.sh" v5-3-after > /dev/null 2>&1
rc_file v5-pkgadd.rc
adb_ shell run-as $PKG tail -n 5 files/usr/tmp/v5-remove.log 2>&1 | sed 's/^/    remove.log: /'
gx 'pkill -x foot; echo foot closed'
phase_log "V4/V5 done"
