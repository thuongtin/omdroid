#!/usr/bin/env python3
"""Exercise the actual rotation QML block with QtTest and an isolated Android bridge.

Run with python3 docs/omarchy/tools/test-rotation-tile.py. Requires Qt 6's
qmltestrunner (on PATH or at /usr/lib/qt6/bin/qmltestrunner) and QtTest.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[3]
PLUGINS = ROOT / "rootfs/overlay/etc/phoshdroid/omamobile/plugins"
SOURCE = PLUGINS / "omamobile.quicksettings/QuickSettings.qml"
MODEL = PLUGINS / "omdroid.android/AndroidModel.js"


def main():
    # Use the shipping tile, acknowledgement handler and timeout without loading
    # the full shell or contacting Linux/Android services on the test machine.
    source = SOURCE.read_text()
    start = source.index("  QtObject {\n    id: rotationLock")
    end = source.index("  Process {\n    id: rotationRead", start)
    tile = source[start:end]
    harness = """
import QtQuick
import QtTest
import MODEL_PATH as Model

Item {
  id: root
  width: 100
  height: 100
  property int dismissals: 0
  function openAndroid(page) { dismissals++; android.open(page) }
  QtObject {
    id: android
    property bool hosted: true
    property var snapshot: ({})
    property double now: 2000
    property var requests: []
    function value(key) { return Model.fresh(snapshot, key, now) ? snapshot[key] : undefined }
    function known(key) { return value(key) !== undefined }
    function open(action) { requests = requests.concat([action]) }
  }
  QtObject { id: rotationRead; property bool running: false }
  QtObject { id: rotationWrite; property bool running: false; property var command: [] }
TILE_SOURCE
  TestCase {
    name: "OmdroidRotationTile"
    when: windowShown
    function reading(value) {
      android.snapshot = Model.parse(JSON.stringify({schema: 2, timestamp: android.now,
        observed: {rotationLocked: android.now}, rotationLocked: value}))
    }
    function init() {
      rotationPendingTimeout.stop()
      rotationLock.pendingValue = null
      android.hosted = true
      android.snapshot = ({})
      android.requests = []
      android.now = 2000
      root.dismissals = 0
      rotationLock.linuxAvailable = false
      rotationLock.linuxEnabled = false
      rotationRead.running = false
      rotationWrite.running = false
      rotationWrite.command = []
    }
    function test_unknown_does_not_send_a_request() {
      verify(!rotationLock.available)
      compare(rotationLock.enabled, undefined)
      compare(rotationLock.icon, "")
      rotationLock.toggle()
      compare(android.requests.length, 0)
      verify(!rotationLock.busy)
    }
    function test_expired_state_does_not_send_a_request() {
      reading(false)
      verify(rotationLock.available)
      android.now += 10000
      verify(!rotationLock.available)
      compare(rotationLock.enabled, undefined)
      rotationLock.toggle()
      compare(android.requests.length, 0)
    }
    function test_explicit_directions_wait_for_acknowledgement_without_dismissal() {
      reading(false)
      rotationLock.toggle()
      compare(android.requests[0], "rotation-lock")
      verify(rotationLock.busy)
      compare(root.dismissals, 0)
      rotationLock.toggle()
      compare(android.requests.length, 1)
      reading(false)
      verify(rotationLock.busy)
      reading(true)
      verify(!rotationLock.busy)
      verify(!rotationPendingTimeout.running)
      rotationLock.toggle()
      compare(android.requests[1], "rotation-auto")
      verify(rotationLock.busy)
      reading(false)
      verify(!rotationLock.busy)
      compare(root.dismissals, 0)
    }
    function test_missing_acknowledgement_allows_retry_after_timeout() {
      reading(false)
      rotationLock.toggle()
      verify(rotationLock.busy)
      compare(rotationPendingTimeout.interval, 2000)
      tryCompare(rotationLock, "busy", false, 3000)
      rotationLock.toggle()
      compare(android.requests.length, 2)
      compare(android.requests[1], "rotation-lock")
    }
    function test_linux_controls_keep_their_existing_backend() {
      android.hosted = false
      rotationLock.linuxAvailable = true
      rotationLock.refresh()
      verify(rotationRead.running)
      rotationLock.toggle()
      verify(rotationWrite.running)
      verify(rotationWrite.command[2].indexOf("touch") >= 0)
      rotationWrite.running = false
      rotationLock.linuxEnabled = true
      rotationLock.toggle()
      verify(rotationWrite.command[2].indexOf("enable --now omamobile-autorotate.service") >= 0)
      compare(android.requests.length, 0)
    }
  }
}
""".replace("MODEL_PATH", json.dumps(MODEL.as_uri())).replace("TILE_SOURCE", tile)
    runner = shutil.which("qmltestrunner") or "/usr/lib/qt6/bin/qmltestrunner"
    with tempfile.TemporaryDirectory(prefix="omdroid-rotation-test-") as temporary:
        directory = Path(temporary)
        (directory / "tst_rotation.qml").write_text(harness)
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
               "XDG_RUNTIME_DIR": str(directory)}
        return subprocess.run([runner, "-input", str(directory)], env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
