#!/bin/bash
# R11 mem: session-start hook. start.sh runs it after session.env is read and before
# cage starts, as a plain script (its exports do not reach the session). It must return
# within a few seconds and starts anything long-lived in the background.
#
# Switches (session.env):
#   OMDROID_MEM=0           turns every change in this tree off (the R10 behaviour)
#   OMDROID_MEM_QML=0       leaves the Quickshell files of the image alone (restores them)
#   OMDROID_SOFT_DIET=0     software-GPU mode keeps blur, shadows and animations
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

# Software GPU (llvmpipe): a helper turns blur, shadows and animations off in the running
# compositor once Hyprland is up. Never edits a dotfile.
if [ "${OMDROID_MEM:-1}" != 0 ] && [ "${OMDROID_GPU:-}" = software ] && [ "${OMDROID_SOFT_DIET:-1}" != 0 ]; then
    python3 "$dir/soft-diet.py" > /tmp/omdroid-soft-diet.log 2>&1 &
    echo "mem: software diet helper started pid $!"
fi
exit 0
