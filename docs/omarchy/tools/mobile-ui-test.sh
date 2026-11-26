#!/bin/bash
# Host test for the mobile UI block in omdroid-ui.sh (no device, no image).
#
# Copies one looknfeel.lua into a scratch guest tree and runs the real
# omdroid-ui.sh against it with OMDROID_ROOT, then proves:
#   - mobile writes the block, disables animations, and is idempotent
#   - luac -p accepts the result
#   - desktop restores the original bytes (sha256)
#   - OMDROID_ANIMATIONS=1 (on the command line, or in session.env, which the
#     script reads itself) keeps the animations
#
# usage: mobile-ui-test.sh <looknfeel.lua>
# Exit status 0 when every check passes.
set -u

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
ui="$root/rootfs/overlay/etc/phoshdroid/omdroid-ui.sh"
src="${1:-}"
if [ -z "$src" ] || [ ! -f "$src" ]; then
  echo "usage: mobile-ui-test.sh <looknfeel.lua>" >&2
  exit 2
fi
luac=""
for candidate in /usr/bin/luac /usr/sbin/luac luac; do
  if command -v "$candidate" >/dev/null 2>&1; then luac="$candidate"; break; fi
done
if [ -z "$luac" ]; then
  echo "FAIL no luac on this host" >&2
  exit 1
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/mobile-ui-test.XXXXXX")" || exit 1
trap 'rm -rf "$work"' EXIT
tree="$work/root"
home="$tree/home/omarchy"
look="$home/.config/hypr/looknfeel.lua"
mkdir -p "$home/.config/hypr" "$home/.config/omdroid" "$home/.config/omarchy"
cp "$src" "$look"
orig="$(sha256sum "$look" | cut -d' ' -f1)"
fail=0

check() { # label expected actual
  if [ "$2" = "$3" ]; then
    echo "PASS $1 ($3)"
  else
    echo "FAIL $1: expected [$2], got [$3]"
    fail=1
  fi
}
sum() { sha256sum "$look" | cut -d' ' -f1; }
has_animations() { grep -q 'animations = { enabled = false }' "$look"; }

run_ui() { # mode [VAR=value ...]
  local mode="$1"; shift
  printf '%s\n' "$mode" > "$home/.config/omdroid/ui"
  env OMDROID_ROOT="$tree" "$@" bash "$ui" > "$work/ui-$mode.log" 2>&1
}

bash -n "$ui" && echo "PASS bash -n omdroid-ui.sh" || { echo "FAIL bash -n"; exit 1; }

# --- mobile, defaults
run_ui mobile
first="$(sum)"
if has_animations; then echo "PASS mobile block disables animations"; else echo "FAIL no animations line in mobile"; fail=1; fi
if "$luac" -p "$look"; then echo "PASS luac -p accepts the mobile file"; else echo "FAIL luac -p rejected the mobile file"; fail=1; fi
run_ui mobile
check "mobile applied twice is byte-identical" "$first" "$(sum)"

# --- desktop restores the original bytes
run_ui desktop
check "desktop restores the original bytes" "$orig" "$(sum)"
if grep -q 'omdroid mobile ui' "$look"; then echo "FAIL desktop left the marker block"; fail=1; else echo "PASS desktop leaves no marker block"; fi

# --- OMDROID_ANIMATIONS=1 overrides on the command line
run_ui mobile OMDROID_ANIMATIONS=1
if has_animations; then echo "FAIL OMDROID_ANIMATIONS=1 still disabled animations"; fail=1; else echo "PASS OMDROID_ANIMATIONS=1 keeps the animations"; fi
if "$luac" -p "$look"; then echo "PASS luac -p accepts the file without the animations line"; else echo "FAIL luac -p"; fail=1; fi
run_ui desktop
check "desktop restores the original bytes after the override" "$orig" "$(sum)"

# --- the same switch from session.env, which the script reads itself
printf '%s\n' 'OMDROID_ANIMATIONS=1' > "$home/.config/omdroid/session.env"
run_ui mobile
if has_animations; then echo "FAIL session.env OMDROID_ANIMATIONS=1 was not honoured"; fail=1; else echo "PASS session.env OMDROID_ANIMATIONS=1 is honoured by the script itself"; fi
grep -q "session.env: read" "$work/ui-mobile.log" && echo "PASS session.env read is logged" || { echo "FAIL no session.env log line"; fail=1; }
run_ui desktop
check "desktop restores the original bytes after the session.env run" "$orig" "$(sum)"
rm -f "$home/.config/omdroid/session.env"

if [ "$fail" -eq 0 ]; then
  echo "VERDICT: PASS"
  exit 0
fi
echo "VERDICT: FAIL"
exit 1
