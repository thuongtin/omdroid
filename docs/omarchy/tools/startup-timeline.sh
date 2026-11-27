#!/bin/bash
# startup-timeline.sh [--stop]  -- install or remove the start-up instruments in the guest.
#
# The instruments (startup-evlog.py, startup-procs.py, beside this script) are started from
# ~/.config/omdroid/session.env, so they run from the first line of start.sh on EVERY session
# start until removed. They write /tmp/r11-evlog.txt and /tmp/r11-procs.txt inside the guest:
#
#   <seconds since mark>  <UTC hh:mm:ss>  openlayer>>omamobile-dock        (evlog)
#   <seconds since mark>  start pid=.. ppid=.. cmd=..                     (procs, 0.1 s poll)
#
# Reading them: gx.sh 'cat /tmp/r11-evlog.txt'  (gx.sh is beside this script)
# Touch /tmp/r11-evlog.mark and /tmp/r11-procs.mark in the guest to start a new segment.
#
#   --stop   remove both instruments from the guest and the session.env lines that start them.
#
# The owner's session.env is left as it was when it is taken away by --stop only if it was
# this script that wrote it: the file it writes carries a marker line.
export PATH="$HOME/Android/Sdk/platform-tools:$PATH"
T=${TABLET_SERIAL:?set TABLET_SERIAL to the adb serial of the test device}
HERE=$(cd "$(dirname "$0")" && pwd)
GUEST_HOME=/home/omarchy
ENVFILE=$GUEST_HOME/.config/omdroid/session.env
MARK="# written by startup-timeline.sh"

if [ "${1:-}" = "--stop" ]; then
    "$HERE/gx.sh" "rm -f $GUEST_HOME/.cache/startup-evlog.py $GUEST_HOME/.cache/startup-procs.py" 2>&1 | tail -1
    if "$HERE/gx.sh" "grep -c '$MARK' $ENVFILE 2>/dev/null" 2>/dev/null | tail -1 | grep -qx 1; then
        "$HERE/gx.sh" "rm -f $ENVFILE" 2>&1 | tail -1
    fi
    echo "instruments removed (a running session keeps its python processes until it ends)"
    exit 0
fi

"$HERE/gpush.sh" "$HERE/startup-evlog.py" "$GUEST_HOME/.cache/startup-evlog.py" > /dev/null 2>&1
"$HERE/gpush.sh" "$HERE/startup-procs.py" "$GUEST_HOME/.cache/startup-procs.py" > /dev/null 2>&1
tmp=$(mktemp)
printf '%s\n' "$MARK" \
    'python3 /home/omarchy/.cache/startup-evlog.py >/dev/null 2>&1 &' \
    'python3 /home/omarchy/.cache/startup-procs.py >/dev/null 2>&1 &' > "$tmp"
"$HERE/gpush.sh" "$tmp" "$ENVFILE" > /dev/null 2>&1
rm -f "$tmp"
echo "instruments installed: they start with the next session and run for 1500 s"
echo "  gx.sh 'cat /tmp/r11-evlog.txt'   gx.sh 'cat /tmp/r11-procs.txt'"
