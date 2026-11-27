#!/bin/bash
# verify-flood.sh -- started inside foot by verify-p6-stall.sh (`foot bash <this>`): keep the terminal
# changing on every frame (a continuous flood of output) until /tmp/verify-flood-stop appears, so
# the client asks for a frame callback after every frame and the callback cadence is the
# compositor's frame loop. Leaves an interactive shell behind.
rm -f /tmp/verify-flood-stop
while [ ! -e /tmp/verify-flood-stop ]; do
    seq 1 400
done
exec bash
