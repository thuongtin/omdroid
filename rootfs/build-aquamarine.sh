#!/bin/bash
# Builds the patched aquamarine (0.14.0 + this project's four-patch series) for
# aarch64 and prints the ABI comparison against the library the guest image
# already ships.
#
# Why: the guest runs Hyprland nested under cage, so its input comes from
# aquamarine's Wayland backend, which in 0.14.0 binds wl_pointer and
# wl_keyboard and never wl_touch. A finger therefore reaches the guest as XI2
# touch, becomes wl_touch under cage, and dies in aquamarine: hyprctl -j devices
# reports an empty touch list, so no QML gesture or Hyprland touch gesture can
# ever fire. 0002 adds CWaylandTouch, modelled on CWaylandPointer.
# Analysis and proof: docs/omarchy/r5-touch-patch-report.md.
#
# 0003 stops every commit from claiming the whole surface changed: it sends the
# damage Hyprland committed, so cage and the X server copy only that region.
# AQ_WAYLAND_FULL_DAMAGE=1 in the guest restores the old behaviour.
# Analysis: docs/omarchy/r10-damage.md.
#
# 0004 caps a Wayland swapchain at two buffers instead of Hyprland's three: one
# 25 MB frame buffer less in Hyprland, the app process and the X server's present
# path. AQ_WAYLAND_SWAPCHAIN=3 in the guest restores the three-buffer ring.
# Analysis: docs/omarchy/r11-memory.md.
#
# Usage: ./rootfs/build-aquamarine.sh [--no-build] [--keep] [--jobs N]
#   --no-build   prepare the reference and the source tree only
#   --keep       leave the builder container running
#
# Outputs (outside the repo):
#   $OMDROID_AQUAMARINE_WORK (default ~/.cache/omdroid/aquamarine)
#     reference/            the image's own library plus the Hyprland binaries that import it
#     src/aquamarine        the patched checkout
#     out/                  install tree mirroring /opt/omarchy-android/aquamarine
#   The packager installs the result with:
#     cp -a .../out/. <stage>/opt/omarchy-android/aquamarine/
#
# Compiler: clang by default. The image's gcc 16 builds everything else fine,
# but its cc1plus segfaults under qemu-user 11.1.2 on src/backend/drm/DRM.cpp
# (reproducible at -O0..-O3), so a qemu-based build cannot use it. On a native
# aarch64 host set OMDROID_AQUAMARINE_COMPILER=gcc to use the bundle's own
# toolchain; the ABI checks below are what decide whether the result is usable.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

AQUAMARINE_REV="a79fb21b2e2a82dd061a6d071802bcf38bd5c383"
PATCH_DIR="$SCRIPT_DIR/patches/aquamarine"
PATCH_0001="0001-wayland-carry-proven-Android-KGSL-buffer-pipeline.patch"
PATCH_0001_SHA256="86ff2be2254760fde311d3adf0e0a416028922fe51b9004dd00e5ea93042196e"
PATCH_0002="0002-wayland-add-wl_touch-input.patch"
PATCH_0002_SHA256="48448110cf8e15ba43abdd9650f5c7093d8ee2f6dd8724dc7613528404d9d787"
PATCH_0003="0003-wayland-send-committed-damage.patch"
PATCH_0003_SHA256="61dc6fc6176ef9013a05b6c19694e77fecdac9a678dc6c0f84b1d80741687daf"
PATCH_0004="0004-wayland-cap-the-nested-swapchain-at-two-buffers.patch"
PATCH_0004_SHA256="a09c8d84aea80aa018c93872ebfc549d79df94992ca0e6b93fb2379df7dff545"

ROOTFS="$PROJECT_DIR/app/src/main/assets/rootfs.bin"
PREFIX="/opt/omarchy-android/aquamarine"
INSTALLED_LIB="./opt/omarchy-android/aquamarine/lib/libaquamarine.so.0.14.0"
CONSUMERS=("./opt/omarchy-android/hyprland/bin/Hyprland" "./opt/omarchy-android/hyprland/bin/hyprctl")
IMAGE="omdroid-aquamarine:0.0.14"
CONTAINER="${OMDROID_AQUAMARINE_CONTAINER:-omdroid-aquamarine-builder}"

WORK="${OMDROID_AQUAMARINE_WORK:-${XDG_CACHE_HOME:-$HOME/.cache}/omdroid/aquamarine}"
OUT="$WORK/out"
REF="$WORK/reference"
JOBS="${OMDROID_AQUAMARINE_JOBS:-4}"
COMPILER="${OMDROID_AQUAMARINE_COMPILER:-clang}"
BUILD=1
KEEP=0

while [ $# -gt 0 ]; do
    case "$1" in
        --no-build) BUILD=0 ;;
        --keep) KEEP=1 ;;
        --jobs) JOBS="$2"; shift ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

say() { printf '\n=== %s ===\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

soname() { readelf -d "$1" | awk '/.*SONAME.*/ {print $NF}' | tr -d '[]'; }
needed() { readelf -d "$1" | awk '/.*NEEDED.*/ {print $NF}' | tr -d '[]' | sort -u; }
strong_symbols() { nm -D --defined-only "$1" 2>/dev/null | awk '$2 ~ /^[TDBR]$/ {print $3}' | sort -u; }
all_symbols() { nm -D --defined-only "$1" 2>/dev/null | awk 'NF == 3 {print $3}' | sort -u; }
glibc_max() { readelf -V "$1" | grep -oE 'GLIBC_[0-9]+\.[0-9]+(\.[0-9]+)?' | sed 's/GLIBC_//' | sort -V | tail -1; }

# ---------------------------------------------------------------- reference
say "Extracting the reference library and its consumers from the guest image"
mkdir -p "$REF"
if [ ! -f "$REF/$INSTALLED_LIB" ]; then
    [ -f "$ROOTFS" ] || fail "missing $ROOTFS (run rootfs/package-omarchy-rootfs.sh first)"
    tar -xzf "$ROOTFS" -C "$REF" "$INSTALLED_LIB" "${CONSUMERS[@]}" \
        || fail "could not extract the reference files from $ROOTFS"
fi
OLD="$REF/$INSTALLED_LIB"
echo "reference: $OLD ($(stat -c %s "$OLD") bytes)"

# ---------------------------------------------------------------- source
say "Preparing the aquamarine source at $AQUAMARINE_REV"
mkdir -p "$WORK/src"
SRC="$WORK/src/aquamarine"
if [ ! -d "$SRC/.git" ]; then
    git clone https://github.com/hyprwm/aquamarine.git "$SRC"
fi
git -C "$SRC" fetch --tags --quiet origin
git -C "$SRC" checkout --quiet --force "$AQUAMARINE_REV"
git -C "$SRC" reset --quiet --hard "$AQUAMARINE_REV"
# The build tree lives inside the source dir (upstream generates protocols/
# there), so a previous run leaves root-owned files the host git cannot remove;
# that is not a reason to fail, they are regenerated.
git -C "$SRC" clean -qfdx || true

for patch in "$PATCH_0001" "$PATCH_0002" "$PATCH_0003" "$PATCH_0004"; do
    [ -f "$PATCH_DIR/$patch" ] || fail "missing $PATCH_DIR/$patch"
done
actual_0001="$(sha256sum "$PATCH_DIR/$PATCH_0001" | awk '{print $1}')"
actual_0002="$(sha256sum "$PATCH_DIR/$PATCH_0002" | awk '{print $1}')"
actual_0003="$(sha256sum "$PATCH_DIR/$PATCH_0003" | awk '{print $1}')"
actual_0004="$(sha256sum "$PATCH_DIR/$PATCH_0004" | awk '{print $1}')"
[ "$actual_0001" = "$PATCH_0001_SHA256" ] || fail "$PATCH_0001 checksum mismatch: $actual_0001"
[ "$actual_0002" = "$PATCH_0002_SHA256" ] || fail "$PATCH_0002 checksum mismatch: $actual_0002"
[ "$actual_0003" = "$PATCH_0003_SHA256" ] || fail "$PATCH_0003 checksum mismatch: $actual_0003"
[ "$actual_0004" = "$PATCH_0004_SHA256" ] || fail "$PATCH_0004 checksum mismatch: $actual_0004"
echo "patch series checksums verified"

git -C "$SRC" -c user.name=omdroid -c user.email=dev@omdroid.invalid \
    am --quiet "$PATCH_DIR/$PATCH_0001" "$PATCH_DIR/$PATCH_0002" "$PATCH_DIR/$PATCH_0003" "$PATCH_DIR/$PATCH_0004"
echo "applied: $(git -C "$SRC" log --oneline "$AQUAMARINE_REV..HEAD" | tr '\n' ' ')"

if [ "$BUILD" = "0" ]; then
    say "Skipping the build (--no-build)"
    exit 0
fi

# ---------------------------------------------------------------- container
command -v docker >/dev/null || fail "docker is required"

say "Builder container ($CONTAINER)"
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
    echo "reusing the existing builder container"
else
    docker image inspect "$IMAGE" >/dev/null 2>&1 || {
        echo "importing $ROOTFS as $IMAGE (a few minutes)"
        docker import --platform linux/arm64 "$ROOTFS" "$IMAGE"
    }
    docker run -d --name "$CONTAINER" --platform linux/arm64 \
        -v "$WORK/src:/build/src" -v "$OUT:/build/out" "$IMAGE" sleep infinity
fi

if ! docker exec "$CONTAINER" bash -lc 'command -v clang++ >/dev/null && command -v cmake >/dev/null && command -v ninja >/dev/null' 2>/dev/null; then
    echo "installing build tools (clang, cmake, ninja, pkgconf, vulkan headers)"
    docker exec "$CONTAINER" bash -lc '
        set -e
        # The image ships a runtime set only: sync the db, then add the tools
        # the bundle builder/guest/packages.txt assumes. --needed keeps this a
        # no-op on a prepared container.
        pacman -Sy --noconfirm
        pacman -S --needed --noconfirm clang llvm-libs cmake ninja pkgconf vulkan-headers
        clang++ --version | head -1
    '
fi

# ---------------------------------------------------------------- build
say "Building with $COMPILER"
mkdir -p "$OUT" "$WORK/logs"
COMPILER_ARGS=""
if [ "$COMPILER" = "clang" ]; then
    COMPILER_ARGS="-DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++"
fi

docker exec "$CONTAINER" bash -lc "
    set -eo pipefail
    rm -rf /build/src/aquamarine/build
    # Same environment the bundle's builder/guest/build-graphics.sh gives its
    # aquamarine step: the image's staged Mesa first, then the system libs.
    export PKG_CONFIG_PATH=/opt/omarchy-android/mesa/root/usr/lib/pkgconfig
    export CMAKE_PREFIX_PATH=/opt/omarchy-android/mesa/root/usr
    export LD_LIBRARY_PATH=/opt/omarchy-android/mesa/root/usr/lib
    cmake -S /build/src/aquamarine -B /build/src/aquamarine/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=$PREFIX $COMPILER_ARGS
    cmake --build /build/src/aquamarine/build --parallel $JOBS
    DESTDIR=/build/out cmake --install /build/src/aquamarine/build
" 2>&1 | tee "$WORK/logs/build.log" | tail -25

NEW_LIB="$OUT$PREFIX/lib/libaquamarine.so.0.14.0"
[ -f "$NEW_LIB" ] || fail "build produced no $NEW_LIB"

# ---------------------------------------------------------------- compare
say "ABI comparison against the library in the image"
status=0

old_soname="$(soname "$OLD")"
new_soname="$(soname "$NEW_LIB")"
echo "SONAME:        $old_soname -> $new_soname"
[ "$old_soname" = "$new_soname" ] || { echo "FAIL: SONAME changed"; status=1; }

needed "$OLD" > "$WORK/needed.old"
needed "$NEW_LIB" > "$WORK/needed.new"
if diff -u "$WORK/needed.old" "$WORK/needed.new" > "$WORK/needed.diff"; then
    echo "NEEDED:        identical ($(wc -l < "$WORK/needed.old") entries)"
else
    echo "FAIL: NEEDED changed:"; cat "$WORK/needed.diff"; status=1
fi

# Weakly-linked template and destructor instantiations (the D1/D2 destructor
# variants, CWeakPointer<T>::decrementWeak, __gnu_cxx::__stoa) differ between
# gcc and clang builds of identical source and are never imported by a
# consumer, so the strong (T/D/B/R) set is the one that has to survive.
strong_symbols "$OLD" > "$WORK/strong.old"
strong_symbols "$NEW_LIB" > "$WORK/strong.new"
lost="$(comm -23 "$WORK/strong.old" "$WORK/strong.new" | wc -l)"
gained="$(comm -13 "$WORK/strong.old" "$WORK/strong.new" | wc -l)"
echo "strong symbols: $(wc -l < "$WORK/strong.old") -> $(wc -l < "$WORK/strong.new") (+$gained)"
if [ "$lost" -ne 0 ]; then
    echo "FAIL: $lost strong symbols disappeared:"; comm -23 "$WORK/strong.old" "$WORK/strong.new" | head -20; status=1
fi
all_symbols "$NEW_LIB" > "$WORK/all.new"
echo "all symbols:   $(all_symbols "$OLD" | wc -l) -> $(wc -l < "$WORK/all.new") (weak instantiations differ by compiler)"

# The decisive set: what the one real consumer imports has to resolve.
imports="$WORK/consumer-imports.txt"
: > "$imports"
for consumer in "${CONSUMERS[@]}"; do
    nm -D --undefined-only "$REF/$consumer" 2>/dev/null | awk '{print $NF}' | grep -E '^_ZNK?10Aquamarine' >> "$imports" || true
done
sort -u -o "$imports" "$imports"
missing="$(comm -23 "$imports" "$WORK/all.new" | wc -l)"
echo "consumer:      Hyprland + hyprctl import $(wc -l < "$imports") aquamarine symbols, $missing missing"
if [ "$missing" -ne 0 ]; then
    echo "FAIL: consumer imports the new library cannot resolve:"
    comm -23 "$imports" "$WORK/all.new" | head -20
    status=1
fi

old_glibc="$(glibc_max "$OLD")"
new_glibc="$(glibc_max "$NEW_LIB")"
guest_glibc="$(docker exec "$CONTAINER" bash -lc 'pacman -Q glibc' | awk '{print $2}' | cut -d+ -f1)"
echo "GLIBC max:     $old_glibc -> $new_glibc (the image has $guest_glibc)"
if [ "$(printf '%s\n%s\n' "$new_glibc" "$guest_glibc" | sort -V | tail -1)" != "$guest_glibc" ]; then
    echo "FAIL: the build needs a newer glibc than the image provides"; status=1
fi

echo "sha256:        $(sha256sum "$NEW_LIB" | awk '{print $1}')"
echo "size:          $(stat -c %s "$NEW_LIB") bytes"

say "Result"
find "$OUT" -name 'libaquamarine.so*' -o -name 'aquamarine.pc' | sort
echo "install with: cp -a \"$OUT/.\" <stage>$PREFIX/"

if [ "$KEEP" = "0" ] && [ "${OMDROID_AQUAMARINE_CONTAINER:-}" = "" ]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    echo "removed the builder container (pass --keep to keep it)"
fi

if [ "$status" -ne 0 ]; then
    echo "ABI COMPARISON FAILED" >&2
    exit 1
fi
echo "ABI OK"
