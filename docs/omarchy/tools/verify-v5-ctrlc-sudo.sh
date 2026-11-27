# verify-v5-ctrlc-sudo.sh -- SOURCED in an interactive foot shell: Ctrl+C during `sudo sleep 30`.
# Pass = rc 130 within seconds of the key, the prompt comes back, and the terminal is restored
# (stty shows echo and icanon on); typing afterwards is checked by the host.
rm -f /tmp/v5-ctrlc-sudo.rc /tmp/v5-stty.txt
touch /tmp/v5-ctrlc-sudo.started
t0=$EPOCHREALTIME; sudo sleep 30; echo "sudo sleep rc=$? t0=$t0 t1=$EPOCHREALTIME" > /tmp/v5-ctrlc-sudo.rc
stty -a > /tmp/v5-stty.txt 2>&1
