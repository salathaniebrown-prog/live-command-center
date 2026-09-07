"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { normalizeUsgs } = require("../data-spine");
const {
  STATE_EMBEDDING_VERSION,
  FEATURE_DIM,
  EMBEDDING_DIM,
  extractStateFeatures,
  embedSpineRecord,
  hammingDistance,
  decorateNormalizedResult
} = require("../state-embedding");

function sampleSpine(overrides = {}) {
  return {
    schemaVersion: "eagle-eyes.data-spine.v1",
    source: "usgs",
    sourceId: "us123",
    eventType: "earthquake",
    title: "M 4.8 - Test location",
    severity: "moderate",
    magnitude: 4.8,
    geometry: { type: "Point", coordinates: [-78.6, 35.8, 12.4] },
    position: { latitude: 35.8, longitude: -78.6, depth: 12.4, depthUnit: "km" },
    occurredAt: "2026-09-01T22:30:00.000Z",
    updatedAt: "2026-09-01T23:00:00.000Z",
    expiresAt: null,
    sourceUrl: "https://example.test/us123",
    retrievedAt: "2026-09-01T23:30:00.000Z",
    sourceMetadata: { status: "reviewed", significance: 355 },
    ...overrides
  };
}

test("state embedding produces a deterministic 10-D binary signature", () => {
  const record = sampleSpine();
  const features = extractStateFeatures(record);
  const first = embedSpineRecord(record);
  const second = embedSpineRecord(record);

  assert.equal(features.length, FEATURE_DIM);
  assert.equal(first.version, STATE_EMBEDDING_VERSION);
  assert.equal(first.dimensions, EMBEDDING_DIM);
  assert.equal(first.trained, false);
  assert.equal(first.vector.length, 10);
  assert.ok(first.vector.every((value) => value === 0 || value === 1));
  assert.deepEqual(first, second);
});

test("state embedding responds to materially different event state", () => {
  const earthquake = embedSpineRecord(sampleSpine());
  const severeAlert = embedSpineRecord(sampleSpine({
    source: "nws",
    eventType: "Tornado Warning",
    title: "Tornado Warning",
    severity: "Extreme",
    magnitude: null,
    position: { latitude: 34.1, longitude: -86.8, depth: null },
    sourceMetadata: { urgency: "Immediate", certainty: "Observed", status: "Actual" }
  }));

  assert.ok(hammingDistance(earthquake, severeAlert) > 0);
});

test("decorator adds embeddings without changing the data-spine normalizer", () => {
  const normalized = normalizeUsgs({
    metadata: { generated: 1788300000000, title: "USGS", count: 1, status: 200 },
    features: [{
      id: "us123",
      type: "Feature",
      geometry: { type: "Point", coordinates: [-78.6, 35.8, 12.4] },
      properties: {
        mag: 4.8,
        place: "Test location",
        time: 1788299000000,
        updated: 1788299500000,
        url: "https://example.test/us123",
        sig: 355,
        status: "reviewed",
        type: "earthquake",
        title: "M 4.8 - Test location"
      }
    }]
  }, "https://earthquake.usgs.gov/feed", 10, "2026-09-01T23:30:00.000Z");

  assert.equal(normalized.events[0].spine.stateEmbedding, undefined);

  const decorated = decorateNormalizedResult(normalized);
  assert.equal(decorated.events[0].spine.stateEmbedding.dimensions, 10);
  assert.equal(decorated.events[0].spine.stateEmbedding.vector.length, 10);
  assert.equal(normalized.events[0].spine.stateEmbedding, undefined);
});
