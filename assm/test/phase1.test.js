"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { toStateEnvelope, distanceBetween } = require("../src/state-adapter");
const { analyzeAgainstBaseline } = require("../src/anomaly-engine");
const { Metrics } = require("../src/metrics");
const { processRecord } = require("../src/worker");

function sampleRecord() {
  return {
    source: "assm-test",
    eventType: "telemetry",
    title: "sample",
    severity: "moderate",
    magnitude: 3.2,
    position: { latitude: 35.8, longitude: -78.6, depth: 4 },
    occurredAt: "2026-09-07T00:00:00Z",
    updatedAt: "2026-09-07T00:01:00Z",
    retrievedAt: "2026-09-07T00:02:00Z",
    sourceMetadata: {
      urgency: "expected",
      certainty: "observed",
      status: "actual",
      significance: 100
    },
    geometry: { type: "Point" }
  };
}

test("ASSM adapter reuses Eagle Eyes deterministic 10-D state embedding", () => {
  const first = toStateEnvelope(sampleRecord());
  const second = toStateEnvelope(sampleRecord());

  assert.equal(first.readOnly, true);
  assert.equal(first.persisted, false);
  assert.equal(first.stateEmbedding.dimensions, 10);
  assert.equal(first.stateEmbedding.featureDim, 16);
  assert.equal(first.stateEmbedding.trained, false);
  assert.equal(first.stateEmbedding.vector.length, 10);
  assert.ok(first.stateEmbedding.vector.every((bit) => bit === 0 || bit === 1));
  assert.equal(distanceBetween(first, second), 0);
});

test("ASSM anomaly engine uses Hamming distance with an explicit threshold", () => {
  const baseline = { stateEmbedding: Array(10).fill(0) };
  const candidate = { stateEmbedding: [1, 1, 1, 1, 1, 0, 0, 0, 0, 0] };
  const analysis = analyzeAgainstBaseline(candidate, baseline, 5);

  assert.equal(analysis.distance, 5);
  assert.equal(analysis.threshold, 5);
  assert.equal(analysis.anomalous, true);
});

test("single worker establishes an in-memory baseline without persistence", () => {
  const context = { baseline: null, threshold: 5, metrics: new Metrics() };
  context.metrics.recordReceived();
  const result = processRecord(sampleRecord(), context);

  assert.equal(result.ok, true);
  assert.equal(result.readOnly, true);
  assert.equal(result.persisted, false);
  assert.equal(result.analysis.baselineEstablished, true);
  assert.equal(result.metrics.processed, 1);
  assert.ok(context.baseline);
});
