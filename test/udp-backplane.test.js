"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  makeState,
  snapshotState,
  validateControlCommand
} = require("../server-udp");

test("UDP control accepts only bounded THROTTLE commands", () => {
  assert.equal(validateControlCommand({ cmd: "THROTTLE", val: 0 }), 0);
  assert.equal(validateControlCommand({ cmd: "THROTTLE", val: 250 }), 250);
  assert.throws(() => validateControlCommand({ cmd: "THROTTLE", val: 251 }));
  assert.throws(() => validateControlCommand({ cmd: "OTHER", val: 10 }));
});

test("UDP state keeps live and simulation observations separate", () => {
  const state = makeState();
  state.livePackets = 2;
  state.simulatedPackets = 3;
  state.liveNodes.add("node-live");
  state.simulationNodes.add("sim-node");
  const snapshot = snapshotState(state);
  assert.equal(snapshot.liveObservedNodes, 1);
  assert.equal(snapshot.simulationObservedNodes, 1);
  assert.equal(snapshot.livePackets, 2);
  assert.equal(snapshot.simulatedPackets, 3);
});
