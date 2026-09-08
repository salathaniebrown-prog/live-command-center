"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { futureCommandLabStatus } = require("../future-command-lab");

test("Future Command Lab tracks planned work without command authority", () => {
  const status = futureCommandLabStatus();

  assert.equal(status.lab, "PROJECT FUTURE COMMAND LAB");
  assert.equal(status.authority, "planning");
  assert.equal(status.observationOnly, true);
  assert.equal(status.commandAuthority, false);
  assert.equal(status.liveExecution, false);
  assert.equal(status.productionMutation, false);
  assert.ok(status.items.some((item) => item.id === "project-builder"));
  assert.ok(status.items.some((item) => item.id === "github-operator"));
  assert.ok(status.items.some((item) => item.id === "deployment-operator"));
  assert.ok(
    status.items.some(
      (item) =>
        item.id === "bci-telemetry" &&
        item.boundary === "single-self-candidate-read-only-observation"
    )
  );
  assert.ok(
    status.items.some((item) => item.id === "supercomputer-nexusbrown-command-center")
  );
});
