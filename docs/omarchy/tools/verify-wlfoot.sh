#!/bin/bash
# verify-wlfoot.sh -- run through the session's own exec (`hl.dsp.exec_cmd`) by verify-p6-stall.sh:
# a foot window flooding its terminal, with the Wayland protocol trace of THAT client written
# unbuffered to /tmp/verify-wl.log. The client's `wl_callback.done` events are timestamped with a
# real-time clock, unlike the compositor's block-buffered trace log.
export WAYLAND_DEBUG=1
exec foot --app-id=verifywl bash /home/omarchy/.cache/verify-flood.sh 2> /tmp/verify-wl.log
