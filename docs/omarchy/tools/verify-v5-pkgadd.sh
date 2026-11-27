# verify-v5-pkgadd.sh -- SOURCED in an interactive foot shell: omarchy-pkg-add of one small
# package, checked with pacman -Q, then removed again (omarchy-pkg-remove is an fzf picker, so
# the removal runs the same `sudo pacman -Rns --noconfirm` its last step runs).
rm -f /tmp/v5-pkgadd.rc /tmp/v5-pkgadd.done
V5PKG=$(sed -n 's/^pkg=\([a-z]*\).*/\1/p' /tmp/v5-int.rc)
omarchy-pkg-add $V5PKG; echo "pkg-add $V5PKG rc=$?" > /tmp/v5-pkgadd.rc
pacman -Q $V5PKG >> /tmp/v5-pkgadd.rc 2>&1
sudo pacman -Rns --noconfirm $V5PKG > /tmp/v5-remove.log 2>&1; echo "remove rc=$?" >> /tmp/v5-pkgadd.rc
pacman -Q $V5PKG >> /tmp/v5-pkgadd.rc 2>&1; echo "pacman -Q after remove rc=$? (1 = gone)" >> /tmp/v5-pkgadd.rc
touch /tmp/v5-pkgadd.done
