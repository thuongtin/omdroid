#!/bin/bash
# rootd-device-check.sh <rootd.py on the build machine> [label]
# On the device, under the device own proot binary: start the given broker in a proot -0 (as
# ProotService does) on a private test socket, then run sudo id, sudo sh -c and sudo false
# from a session-like proot (-i 1000:1000), then stop the broker. Needs TABLET_SERIAL.
# Control: pass the shipped broker (git show <rev>:rootfs/overlay/etc/phoshdroid/omdroid-rootd.py).
export PATH="$HOME/Android/Sdk/platform-tools:$PATH"
D=${TABLET_SERIAL:?set TABLET_SERIAL}
SRC=${1:?rootd.py}; LABEL=${2:-test}
O=$(cd "$(dirname "$0")/../../../rootfs/overlay/etc/phoshdroid" && pwd)
APK=$(adb -s "$D" shell pm path com.phoshdroid.app | head -1 | sed 's/package://; s#/base.apk##' | tr -d '\r')
NL="$APK/lib/arm64"
P=/data/data/com.phoshdroid.app/files/usr
R=$P/var/lib/proot-distro/installed-rootfs/omarchy
for f in "$SRC:omdroid-rootd.py" "$O/sudo:sudo" "$O/omdroid_root.py:omdroid_root.py"; do
  adb -s "$D" push "${f%%:*}" "/data/local/tmp/rt-${f##*:}" >/dev/null
done
cat > /tmp/rt-run.sh <<EOF
#!/system/bin/sh
export PROOT_TMP_DIR=$P/tmp PROOT_LOADER=$NL/libproot-loader.so LD_LIBRARY_PATH=$NL TMPDIR=$P/tmp
T=$P/tmp/rootd-test
rm -rf \$T; mkdir -p \$T
for f in omdroid-rootd.py sudo omdroid_root.py; do cp /data/local/tmp/rt-\$f \$T/\$f; done
chmod 755 \$T/sudo
COMMON="--kill-on-exit --link2symlink -r $R -b /dev -b /proc -b /sys -b $P/tmp:/tmp"
$NL/libproot.so \$COMMON -0 -w /root /usr/bin/env -i HOME=/root PATH=/usr/bin:/bin LANG=C.UTF-8 \\
  /usr/bin/python3 -B /tmp/rootd-test/omdroid-rootd.py --socket /tmp/rootd-test/s/sock > \$T/broker.out 2>&1 &
B=\$!
i=0; while [ ! -S \$T/s/sock ] && [ \$i -lt 100 ]; do sleep 0.1; i=\$((i+1)); done
echo "[$LABEL] broker \$( [ -S \$T/s/sock ] && echo up || echo MISSING ) after \$i ticks"
$NL/libproot.so \$COMMON -i 1000:1000 -w /home/omarchy /usr/bin/env -i HOME=/home/omarchy USER=omarchy \\
  PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 OMDROID_ROOTD_SOCK=/tmp/rootd-test/s/sock /bin/bash -c '
  echo "client getuid \$(id -u)"
  /tmp/rootd-test/sudo id; echo "sudo id exit=\$?"
  /tmp/rootd-test/sudo sh -c "whoami; touch /root/.rootd-test && ls -ln /root/.rootd-test && rm /root/.rootd-test"; echo "sudo sh exit=\$?"
  /tmp/rootd-test/sudo false; echo "sudo false exit=\$? (want 1)"
' 2>&1
echo "--- rootd.log"; tail -5 \$T/s/rootd.log 2>/dev/null; echo "--- broker.out"; tail -3 \$T/broker.out
kill \$B 2>/dev/null; sleep 0.5; kill -9 \$B 2>/dev/null
rm -rf \$T
EOF
adb -s "$D" push /tmp/rt-run.sh /data/local/tmp/rt-run.sh >/dev/null
adb -s "$D" shell run-as com.phoshdroid.app sh /data/local/tmp/rt-run.sh 2>&1
adb -s "$D" shell rm -f /data/local/tmp/rt-run.sh /data/local/tmp/rt-omdroid-rootd.py /data/local/tmp/rt-sudo /data/local/tmp/rt-omdroid_root.py
