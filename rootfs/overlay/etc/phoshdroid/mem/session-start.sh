#!/bin/bash
# R11 mem: session-start hook. start.sh runs it after session.env is read and before
# cage starts, as a plain script (its exports do not reach the session). It must return
# within a few seconds and starts anything long-lived in the background.
#
# Switches (session.env):
#   OMDROID_MEM=0           turns every change in this tree off (the R10 behaviour)
#   OMDROID_MEM_QML=0       leaves the Quickshell files of the image alone (restores them)
# The libaquamarine buffer cap is the library own switch, AQ_WAYLAND_SWAPCHAIN=3 (set in
# start.sh) restores the three-buffer ring.
dir=/etc/phoshdroid/mem

if [ "${OMDROID_MEM:-1}" = 0 ]; then
    echo "mem: OMDROID_MEM=0, restoring originals and starting nothing"
fi

# Quickshell files: patched copies over the image ones, originals kept beside them.
if [ -f "$dir/qml-apply.sh" ]; then
    bash "$dir/qml-apply.sh" || echo "mem: qml-apply rc=$?"
fi
exit 0
