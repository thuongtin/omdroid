// SPDX-License-Identifier: MIT
import QtQuick
import Quickshell
import Quickshell.Io
import "AndroidModel.js" as Model

Item {
  id: root
  readonly property bool hosted: Quickshell.env("OMARCHY_PROOT") === "1"
  property var snapshot: ({})
  property double now: Date.now()
  readonly property bool available: hosted && snapshot.schema === 2
  // The bundled shell predates Commons.Translations; keep labels Qt-translatable.
  function t(key) {
    switch (key) {
      case "on": return qsTr("On")
      case "off": return qsTr("Off")
      case "connected": return qsTr("Connected")
      case "displaySettings": return qsTr("Display & brightness settings")
      case "volumeSettings": return qsTr("Android volume")
      default: return qsTr("Android settings")
    }
  }
  // A field is known only while the host's observation of it is inside the guest's window
  // (contract section 13); a field that has aged out is unknown, not false.
  function value(key) { return hosted && Model.fresh(snapshot, key, now) ? snapshot[key] : undefined }
  function known(key) { return value(key) !== undefined }
  function status(key) { return value(key) === true ? t("on") : value(key) === false ? t("off") : t("settings") }
  function open(page) {
    if (!hosted) return
    Quickshell.execDetached(["python3", String(Qt.resolvedUrl("android-control.py")).replace(/^file:\/\//, ""), page])
  }
  FileView {
    id: data
    path: root.hosted ? "/tmp/omdroid-android/state.json" : ""
    watchChanges: root.hosted
    onFileChanged: reload()
    onLoaded: { root.now = Date.now(); root.snapshot = Model.parse(text()) }
    onLoadFailed: root.snapshot = ({})
  }
  Timer {
    interval: 3000
    repeat: true
    running: root.hosted
    // The file's own watch reloads it. The timer only ages the readings, which is what makes a
    // field expire when the host has stopped publishing (contract section 13) - one timer, no
    // re-parse per tick.
    onTriggered: root.now = Date.now()
  }
}
