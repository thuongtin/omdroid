# verify-v5-int.sh -- SOURCED in an interactive foot shell (`. /home/omarchy/.cache/verify-v5-int.sh`)
# by verify-p4-fresh-sudo.sh: the sudo prompt path with a real answer typed at the prompt.
rm -f /tmp/v5-int.rc /tmp/v5-at-prompt
sudo pacman -Syy --noconfirm > /tmp/v5-sync.log 2>&1; echo "sync rc=$?" > /tmp/v5-int.rc
V5PKG=
for c in sl figlet cowsay; do
    if pacman -Si $c > /dev/null 2>&1; then V5PKG=$c; break; fi
done
echo "pkg=$V5PKG installed-before=$(pacman -Q $V5PKG 2>&1 | head -1)" >> /tmp/v5-int.rc
touch /tmp/v5-at-prompt
sudo pacman -S $V5PKG
echo "pacman rc=$? t=$EPOCHREALTIME installed-after=$(pacman -Q $V5PKG 2>&1 | head -1)" >> /tmp/v5-int.rc
touch /tmp/v5-int.done
