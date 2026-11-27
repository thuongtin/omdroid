# verify-v5-ctrlc-plain.sh -- SOURCED in an interactive foot shell: the control for the Ctrl+C
# injection. A plain `sleep 30` must die on Ctrl+C (rc 130) within seconds, or the injection
# (and not sudo) is what a failed sudo case would be measuring.
rm -f /tmp/v5-ctrlc-plain.rc
touch /tmp/v5-ctrlc-plain.started
t0=$EPOCHREALTIME; sleep 30; echo "plain sleep rc=$? t0=$t0 t1=$EPOCHREALTIME" > /tmp/v5-ctrlc-plain.rc
