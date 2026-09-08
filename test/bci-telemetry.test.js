"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { bciTelemetryStatus } = require("../bci-telemetry");

test("BCI telemetry is registered as observation-only and locked by default", () => {
  const status = bciTelemetryStatus({});

  assert.equal(status.status, "UNCONFIGURED");
  assert.equal(status.candidateMode, "single-self-candidate");
  assert.equal(status.authorizedCandidate, "Salathaniel Brown Sr");
  assert.equal(status.enrollmentOpen, false);
  assert.equal(status.selfUseOnly, true);
  assert.equal(status.observationOnly, true);
  assert.equal(status.commandAuthority, false);
  assert.equal(status.medicalDevice, false);
  assert.equal(status.diagnosis, false);
  assert.equal(status.controlOutput, false);
  assert.equal(status.ingestConfigured, false);
});

test("BCI telemetry waits for validated observations when ingest is configured", () => {
  const status = bciTelemetryStatus({
    BCI_TELEMETRY_INGEST_TOKEN: "configured",
    BCI_DEVICE_PROFILE: "research-headband",
    BCI_SELF_CANDIDATE_NAME: "Salathaniel Brown Sr"
  });

  assert.equal(status.status, "WAITING");
  assert.equal(status.deviceProfile, "research-headband");
  assert.equal(status.authorizedCandidate, "Salathaniel Brown Sr");
  assert.equal(status.ingestConfigured, true);
  assert.equal(status.commandAuthority, false);
});
