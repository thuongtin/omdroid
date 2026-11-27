#!/bin/bash
# Host test for the session environment block in start.sh (no device needed).
#
# Extracts the block that starts at the comment "Session environment for
# everything started below." and sources it exactly as start.sh does, with HOME
# pointed at a scratch tree, and checks the defaults and the optional
# $HOME/.config/omdroid/session.env override.
#
# usage: session-env-test.sh
# Exit status 0 when every check passes.
set -u

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
start="$root/rootfs/overlay/etc/phoshdroid/start.sh"
fail=0

say() { printf '%s %s\n' "$1" "$2"; }
check() { # label expected actual
  if [ "$2" = "$3" ]; then
    say PASS "$1 ($3)"
  else
    say FAIL "$1: expected [$2], got [$3]"
    fail=1
  fi
}

if bash -n "$start"; then
  say PASS "bash -n start.sh"
else
  say FAIL "bash -n start.sh"
  exit 1
fi

block="$(awk '/^# Session environment for everything started below\./ { on = 1 } on { print } on && /^fi$/ { exit }' "$start")"
if [ -z "$block" ]; then
  say FAIL "no session environment block in start.sh"
  exit 1
fi
say PASS "session environment block found ($(printf '%s\n' "$block" | wc -l) lines)"

if printf '%s\n' "$block" | grep -qE 'MALLOC_(MMAP|TRIM)_THRESHOLD_'; then
  say FAIL "the block sets a malloc mmap/trim threshold"
else
  say PASS "no MALLOC_MMAP_THRESHOLD_ / MALLOC_TRIM_THRESHOLD_"
fi

env_line="$(grep -n '^python3 /etc/phoshdroid/omarchy-watch.py' "$start" | cut -d: -f1)"
block_line="$(grep -n '^# Session environment for everything started below\.' "$start" | cut -d: -f1)"
gpu_line="$(grep -n '^# GPU path:' "$start" | cut -d: -f1)"
if [ -n "$env_line" ] && [ -n "$block_line" ] && [ -n "$gpu_line" ] &&
   [ "$block_line" -lt "$env_line" ] && [ "$block_line" -gt "$gpu_line" ]; then
  say PASS "block at line $block_line, watcher at $env_line, GPU block at $gpu_line"
else
  say FAIL "block position: block=$block_line watcher=$env_line gpu=$gpu_line"
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/session-env-test.XXXXXX")" || exit 1
trap 'rm -rf "$work"' EXIT
home="$work/home"
mkdir -p "$home/.config/omdroid"

run_block() { # extra printf of the values this block exports
  HOME="$home" bash -c "$block"$'\n''printf "values:%s|%s|%s|%s\n" "${MALLOC_ARENA_MAX-}" "${MESA_SHADER_CACHE_MAX_SIZE-}" "${OMDROID_WATCH_LEGACY-}" "${OMDROID_ANIMATIONS-}"'
}

out="$(run_block)"
check "default MALLOC_ARENA_MAX|MESA_SHADER_CACHE_MAX_SIZE|legacy|animations" \
  "values:2|128M||" "$(printf '%s\n' "$out" | grep '^values:')"
if printf '%s\n' "$out" | grep -q "session.env: read"; then
  say FAIL "the block announced a session.env that does not exist"
else
  say PASS "no session.env: nothing sourced, no log line"
fi

printf '%s\n' 'MALLOC_ARENA_MAX=4' 'OMDROID_WATCH_LEGACY=1' 'OMDROID_ANIMATIONS=1' \
  > "$home/.config/omdroid/session.env"
out="$(run_block)"
check "session.env overrides arenas and switches" \
  "values:4|128M|1|1" "$(printf '%s\n' "$out" | grep '^values:')"
if printf '%s\n' "$out" | grep -q "session.env: read $home/.config/omdroid/session.env"; then
  say PASS "the read file is named in the session log line"
else
  say FAIL "no log line naming $home/.config/omdroid/session.env"
fi

printf '%s\n' 'MALLOC_ARENA_MAX=' > "$home/.config/omdroid/session.env"
out="$(run_block)"
check "an empty MALLOC_ARENA_MAX drops the cap" \
  "values:|128M||" "$(printf '%s\n' "$out" | grep '^values:')"

if [ "$fail" -eq 0 ]; then
  echo "VERDICT: PASS"
  exit 0
fi
echo "VERDICT: FAIL"
exit 1
