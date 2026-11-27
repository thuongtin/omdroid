// SPDX-License-Identifier: MIT
.pragma library

var FLAGS = ["wifiEnabled", "wifiConnected", "bluetoothEnabled", "airplaneMode",
             "rotationLocked", "powerSave", "charging", "full"]

// The snapshot the host publishes (contract section 13): every field's value, and the time the
// host observed it. A field without a finite observation time is dropped, so a malformed file can
// only make a field unknown, never wrong.
function parse(text) {
  if (typeof text !== "string" || text.length > 8192) return ({})
  var raw
  try { raw = JSON.parse(text) } catch (_) { return ({}) }
  if (!raw || raw.schema !== 2 || typeof raw.timestamp !== "number" || !isFinite(raw.timestamp)) return ({})
  var at = raw.observed
  if (!at || typeof at !== "object") return ({})
  var result = {schema: 2, timestamp: raw.timestamp, observed: {}}
  FLAGS.forEach(function(key) {
    if (typeof at[key] !== "number" || !isFinite(at[key])) return
    if (typeof raw[key] !== "boolean") return
    result[key] = raw[key]
    result.observed[key] = at[key]
  })
  var n = raw.batteryPercent
  if (typeof n === "number" && isFinite(n) && n >= 0 && n <= 100
      && typeof at.batteryPercent === "number" && isFinite(at.batteryPercent)) {
    result.batteryPercent = Math.round(n)
    result.observed.batteryPercent = at.batteryPercent
  }
  return result
}

// A field is known while the host's observation of it is younger than TTL_MS. The host
// re-confirms every reading at 8 s, so a value that has not changed stays known; a host that
// stopped publishing expires field by field without the file being rewritten.
var TTL_MS = 10000

function fresh(state, key, now) {
  if (!state || state.schema !== 2 || !state.observed) return false
  var at = state.observed[key]
  return typeof at === "number" && isFinite(at) && now >= at && now - at < TTL_MS
}
