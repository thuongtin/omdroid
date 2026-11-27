#!/usr/bin/env bash
# verify-session-lib.sh -- session-end helpers for V6 (phases 3, 7, 11). Source after verify-common.sh.
wait_launcher() { # $1 seconds: wait for the launcher activity on top
    local i
    for i in $(seq 1 "$1"); do
        case "$(top_activity)" in *LauncherActivity*) echo "launcher on top after ~${i}s"; return 0 ;; esac
        sleep 1
    done
    echo "launcher never on top in $1 s (top=$(top_activity))"; return 1
}
launch_logs() { adb_ logcat -d -v time -s Phoshdroid:I ProotService:I 2> /dev/null | grep -aE 'launch:|ProotService' | cut -c1-190 | tail -${1:-14} | sed 's/^/    log: /'; }
press_start_again() { # $1 tag: tap Start again (else the icon path), then wait for a PASSing desktop
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
exit_timing() { # $1 tag: from logcat, the exit code(s), the request->screen gap, the ANR line if any
    local f="$PHASE_OUT/log-$1.txt"
    adb_ logcat -d -v time > "$f" 2>/dev/null
    python3 - "$f" <<'PY'
import re, sys
lines = open(sys.argv[1], errors="replace").read().splitlines()
def ts(l):
    m = re.match(r"(\d\d-\d\d) (\d\d:\d\d:\d\d\.\d+)", l)
    return (m.group(1), m.group(2)) if m else None
def secs(t):
    h, m, s = t[1].split(":"); return int(h) * 3600 + int(m) * 60 + float(s)
exits, ended, screen, anr = [], None, None, None
for l in lines:
    if "proot exited" in l or "proot retry exited" in l: exits.append(l.split("ProotService:")[-1].strip())
    if "launch: session ended" in l and ts(l): ended = ts(l)
    if "launch: ended-screen" in l and ts(l) and screen is None:
        screen = ts(l)
    if "ANR in com.phoshdroid.app" in l: anr = l.strip()[:120]
print("exit lines:", "; ".join(exits) or "none")
if ended and screen:
    d = secs(screen) - secs(ended)
    print("session-ended %s -> ended-screen %s = %.2f s" % (ended[1], screen[1], d))
elif screen:
    print("ended-screen seen, no session-ended line before it (solo launch path)")
else:
    print("ended-screen: ABSENT from this log")
print("ANR:", anr or "none in this log")
PY
}
screen_report() { # $1 tag: one ui dump, its text nodes, whether Android's "isn't responding" dialog is up
    local txt; txt=$(ui_dump "$1" 2>/dev/null)
    printf '%s\n' "$txt" | head -${2:-14} | sed 's/^/    ui: /'
    case "$txt" in *"isn't responding"*|*"not responding"*) phase_log "ANR DIALOG on screen";; *) phase_log "no ANR dialog on screen";; esac
    adb_ shell dumpsys activity exit-info $PKG 2> /dev/null | grep -aiE 'reason=|anr|crash' | head -3 | sed 's/^/    exit-info: /'
}
