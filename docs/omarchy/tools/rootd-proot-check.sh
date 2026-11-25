#!/bin/bash
# rootd-proot-check.sh: the sudo broker under a real proot -0 on the build machine,
# the way the app runs it (second proot -0 for the broker, session proot -i 1000:1000
# for the client). rootd-selftest.py runs the broker without proot, so it cannot see
# that proot fakes getuid() but not SO_PEERCRED; this script can.
#
#   PROOT=/path/to/proot-x86_64-static docs/omarchy/tools/rootd-proot-check.sh
#
# Static proot: https://github.com/proot-me/proot/releases (proot-v5.3.0-x86_64-static).
# Case D needs docker and the arm64 image omdroid-guest:0.0.14 (qemu binfmt); it is
# skipped when either is missing. Exit status 0 only when every case behaves.
set -u
PROOT=${PROOT:?set PROOT to a proot binary}
O=$(cd "$(dirname "$0")/../../../rootfs/overlay/etc/phoshdroid" && pwd)
S=$(mktemp -d)
fails=0
setsid "$PROOT" -0 python3 -B "$O/omdroid-rootd.py" --socket "$S/sock" </dev/null >"$S/broker.out" 2>&1 &
BROKER=$!
for _ in $(seq 1 50); do [ -S "$S/sock" ] && break; sleep 0.1; done
export OMDROID_ROOTD_SOCK=$S/sock

check() { # name, expected exit, command...
    local name=$1 want=$2; shift 2
    local out; out=$("$@" </dev/null 2>&1); local rc=$?
    if [ "$rc" = "$want" ]; then echo "PASS $name (exit $rc)"; else echo "FAIL $name (exit $rc, want $want): $out"; fails=$((fails+1)); fi
}

check "A plain client, same uid: sudo id" 0 timeout -s KILL 15 python3 -B "$O/sudo" id
check "B session-like client (proot -i 1000:1000): sudo id" 0 timeout -s KILL 15 "$PROOT" -i 1000:1000 python3 -B "$O/sudo" id
check "C session-like client: sudo false keeps the exit code" 1 timeout -s KILL 15 "$PROOT" -i 1000:1000 python3 -B "$O/sudo" false

if command -v docker >/dev/null && docker image inspect omdroid-guest:0.0.14 >/dev/null 2>&1; then
    chmod 777 "$S"; chmod 666 "$S/sock"
    check "D foreign real uid 4242 is refused" 1 timeout -s KILL 120 docker run --rm --platform linux/arm64 \
        -u 4242:4242 -e OMDROID_ROOTD_SOCK="$S/sock" -v "$S:$S" -v "$O:/ov:ro" \
        --entrypoint python3 omdroid-guest:0.0.14 -B /ov/sudo id
    if grep -q 'refused peer uid 4242' "$S/rootd.log" 2>/dev/null; then echo "PASS D logged the refusal"; else echo "FAIL D no refusal line in rootd.log"; fails=$((fails+1)); fi
else
    echo "SKIP D (no docker or no omdroid-guest:0.0.14 image)"
fi

echo "--- rootd.log ---"; tail -6 "$S/rootd.log" 2>/dev/null
kill -KILL -- -"$BROKER" 2>/dev/null
wait "$BROKER" 2>/dev/null
rm -rf "$S"
echo "failures: $fails"
[ "$fails" = 0 ]
