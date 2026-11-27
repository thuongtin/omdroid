#!/bin/bash
# cage's only client. Starts Hyprland with no fixed sleep: fit-x11.py --wait
# resizes cage's X11 window to the X root (each side rounded down to even) and
# returns as soon as that geometry is confirmed, capped at FIT_WAIT seconds (on
# the cap it logs one line and Hyprland starts anyway).
#
# The confirmed size is then handed to Hyprland as OMARCHY_OUTPUT_WIDTH/HEIGHT,
# which is what monitors.lua turns into its mode: the mode is exactly the size
# cage has (never the odd host prediction, which cannot match the even-rounded
# window) and the refresh hint start.sh exported is kept.
#
# GPU fallback (launch-contract section 9): when the host chose the KGSL path
# itself from the device (OMDROID_GPU_SOURCE=auto) and Hyprland dies with an error
# within OMDROID_GPU_FALLBACK_WINDOW seconds (default 15) of starting, the GPU
# driver is the likely cause (an Adreno chip the patched Mesa does not know, a
# KGSL node that opens but cannot create a context). Hyprland is then started
# once more in software mode and a marker is left in the runtime dir so that a
# host retry of the whole session goes straight to software. A user who chose a
# mode in Settings never gets a fallback, and OMDROID_GPU_FALLBACK=0 turns it
# off. Every other case still execs Hyprland, exactly as before.
#
# Runs inside dbus-run-session, with the guest environment already exported.
X=${PHOSHDROID_XDISPLAY:-:0}
rm -f /tmp/omarchy-fit
python3 /etc/phoshdroid/fit-x11.py --wait "${FIT_WAIT:-10}" "$X"
if read -r fw fh < /tmp/omarchy-fit; then
    export OMARCHY_OUTPUT_WIDTH=$fw OMARCHY_OUTPUT_HEIGHT=$fh
fi

HYPRLAND=/opt/omarchy-android/hyprland/bin/Hyprland
HYPRLAND_CONFIG=/home/omarchy/.config/hypr/hyprland.lua

# The software block of start.sh, for the one case where this script switches mode.
gpu_software_env() {
    export OMDROID_GPU=software
    export OMARCHY_GPU_MODE=software
    export MESA_LOADER_DRIVER_OVERRIDE=swrast LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
    unset VK_ICD_FILENAMES FD_KGSL_ENABLE_DMABUF HYPRLAND_ANDROID_DMABUF
}

if [ "${OMDROID_GPU:-}" = kgsl ] && [ "${OMDROID_GPU_SOURCE:-}" = auto ] \
        && [ "${OMDROID_GPU_FALLBACK:-1}" != 0 ]; then
    stopping=0
    started=$SECONDS
    "$HYPRLAND" --config "$HYPRLAND_CONFIG" &
    hypr=$!
    # cage ends its client with a signal: pass it on, and never mistake it for a crash.
    trap 'stopping=1; kill -TERM "$hypr" 2>/dev/null' TERM INT HUP
    wait "$hypr"
    rc=$?
    while kill -0 "$hypr" 2>/dev/null; do
        wait "$hypr"
        rc=$?
    done
    trap - TERM INT HUP
    ran=$((SECONDS - started))
    if [ "$rc" -eq 0 ] || [ "$stopping" -eq 1 ] || [ "$ran" -ge "${OMDROID_GPU_FALLBACK_WINDOW:-15}" ]; then
        exit "$rc"
    fi
    echo "gpu: Hyprland exited $rc after ${ran}s in kgsl mode; starting it once more in software mode"
    : > "$XDG_RUNTIME_DIR/omdroid-gpu-fallback"
    # Whatever the failed start left behind: its instance dir, and a shell that holds
    # the one-shot launch lock the next Hyprland config takes.
    pkill -x quickshell 2>/dev/null
    pkill -f omarchy-launch-shell 2>/dev/null
    rm -rf "$XDG_RUNTIME_DIR"/hypr/* "$XDG_RUNTIME_DIR/omarchy-shell-launch.lock"
    gpu_software_env
    echo "gpu: mode=software source=auto from=fallback"
fi
exec "$HYPRLAND" --config "$HYPRLAND_CONFIG"
