#!/bin/bash
# verify-scroll.sh -- started inside foot by verify-p2-repaint.sh (`foot bash <this>`):
# scroll the terminal continuously until /tmp/verify-scroll-stop appears, then leave an
# interactive shell so the (stopped, still open) window can be compared against a repaint.
rm -f /tmp/verify-scroll-stop
while [ ! -e /tmp/verify-scroll-stop ]; do
    seq 1 60
    sleep 0.05
done
exec bash
