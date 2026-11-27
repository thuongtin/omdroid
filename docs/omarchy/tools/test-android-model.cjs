// Run with node docs/omarchy/tools/test-android-model.cjs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const model = {};
vm.createContext(model);
const file = path.resolve(__dirname, '../../../rootfs/overlay/etc/phoshdroid/omamobile/plugins/omdroid.android/AndroidModel.js');
vm.runInContext(fs.readFileSync(file, 'utf8').replace(/^\.pragma library\s*$/m, ''), model);
const read = raw => model.parse(JSON.stringify(raw));
assert.equal(model.parse('broken').schema, undefined);
assert.equal(model.parse('x'.repeat(9000)).schema, undefined);
// The version before this one carried no per-field observation times; it is not read as if it had.
assert.equal(read({schema: 1, timestamp: 1000}).schema, undefined);
assert.equal(read({schema: 2, timestamp: 1000}).schema, undefined);
assert.equal(read({schema: 2, timestamp: 1000, observed: {wifiEnabled: 'now'}}).wifiEnabled, undefined);
const valid = read({schema: 2, timestamp: 2000, observed: {wifiEnabled: 1000, wifiConnected: 1000, batteryPercent: 1000},
                    wifiEnabled: true, wifiConnected: false, batteryPercent: 76.4});
assert.equal(valid.wifiEnabled, true);
assert.equal(valid.wifiConnected, false);
assert.equal(valid.batteryPercent, 76);
// A field is known for ten seconds from the host's observation of it, and not a moment before it.
assert.equal(model.fresh(valid, 'wifiEnabled', 1001), true);
assert.equal(model.fresh(valid, 'wifiEnabled', 10999), true);
assert.equal(model.fresh(valid, 'wifiEnabled', 11000), false);
assert.equal(model.fresh(valid, 'wifiEnabled', 999), false);
// A field the host never observed is unknown while the rest of the snapshot is fresh, and an
// aged-out reading is unknown rather than a stale false.
assert.equal(model.fresh(valid, 'powerSave', 1001), false);
const aged = read({schema: 2, timestamp: 1000, observed: {wifiEnabled: 1000}, wifiEnabled: false});
assert.equal(model.fresh(aged, 'wifiEnabled', 10999), true);
assert.equal(model.fresh(aged, 'wifiEnabled', 11000), false);
const unsafe = read({schema: 2, timestamp: 1000,
                     observed: {wifiEnabled: 1000, bluetoothEnabled: 1000, batteryPercent: 1000, networkName: 1000},
                     wifiEnabled: '<img src="https://invalid/">', bluetoothEnabled: null, batteryPercent: 101,
                     networkName: '<b>network</b>'});
assert.equal(unsafe.wifiEnabled, undefined);
assert.equal(unsafe.bluetoothEnabled, undefined);
assert.equal(unsafe.batteryPercent, undefined);
assert.equal(unsafe.networkName, undefined);
console.log('Android status model: malformed, stale, unknown, and markup input checks passed');
