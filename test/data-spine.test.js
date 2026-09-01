"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  SCHEMA_VERSION,
  normalizeUsgs,
  normalizeEonet,
  normalizeNws
} = require("../data-spine");

test("USGS spine preserves coordinates, depth, source IDs, source time, and legacy fields", () => {
  const result = normalizeUsgs({
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
        detail: "https://example.test/us123.geojson",
        sig: 355,
        felt: 12,
        tsunami: 0,
        status: "reviewed",
        type: "earthquake",
        title: "M 4.8 - Test location"
      }
    }]
  }, "https://earthquake.usgs.gov/feed", 10, "2026-09-01T23:30:00.000Z");

  const event = result.events[0];
  assert.equal(result.schemaVersion, SCHEMA_VERSION);
  assert.equal(event.id, "us123");
  assert.equal(event.magnitude, 4.8);
  assert.equal(event.coordinates.latitude, 35.8);
  assert.equal(event.coordinates.longitude, -78.6);
  assert.equal(event.coordinates.depthKm, 12.4);
  assert.equal(event.spine.sourceId, "us123");
  assert.equal(event.spine.position.depth, 12.4);
  assert.equal(event.spine.position.depthUnit, "km");
  assert.equal(event.spine.geometry.type, "Point");
});

test("EONET spine preserves latest geometry and the complete geometry history", () => {
  const result = normalizeEonet({
    events: [{
      id: "EONET_1",
      title: "Test wildfire",
      link: "https://example.test/eonet/1",
      categories: [{ id: "wildfires", title: "Wildfires" }],
      sources: [{ id: "src", url: "https://example.test/source" }],
      geometry: [
        { date: "2026-08-31T12:00:00Z", type: "Point", coordinates: [-120, 35] },
        { date: "2026-09-01T12:00:00Z", type: "Point", coordinates: [-119.5, 35.5] }
      ]
    }]
  }, "https://eonet.gsfc.nasa.gov/api/v3/events", 10, "2026-09-01T23:30:00.000Z");

  const event = result.events[0];
  assert.equal(event.coordinates.latitude, 35.5);
  assert.equal(event.coordinates.longitude, -119.5);
  assert.equal(event.geometryHistory.length, 2);
  assert.equal(event.sourceRecord.sources.length, 1);
  assert.equal(event.spine.eventType, "Wildfires");
  assert.equal(event.spine.occurredAt, "2026-09-01T12:00:00Z");
});

test("NWS spine preserves alert geometry and operational alert metadata", () => {
  const result = normalizeNws({
    title: "Current watches, warnings, and advisories",
    updated: "2026-09-01T23:20:00Z",
    features: [{
      id: "https://api.weather.gov/alerts/abc",
      type: "Feature",
      geometry: {
        type: "Polygon",
        coordinates: [[[-79, 35], [-78, 35], [-78, 36], [-79, 35]]]
      },
      properties: {
        id: "urn:oid:abc",
        event: "Severe Thunderstorm Warning",
        headline: "Severe Thunderstorm Warning issued",
        severity: "Severe",
        certainty: "Observed",
        urgency: "Immediate",
        status: "Actual",
        messageType: "Alert",
        areaDesc: "Test County",
        sent: "2026-09-01T23:10:00Z",
        effective: "2026-09-01T23:10:00Z",
        onset: "2026-09-01T23:12:00Z",
        expires: "2026-09-02T00:00:00Z",
        web: "https://weather.gov/example"
      }
    }]
  }, "https://api.weather.gov/alerts/active", 10, "2026-09-01T23:30:00.000Z");

  const event = result.events[0];
  assert.equal(event.event, "Severe Thunderstorm Warning");
  assert.equal(event.severity, "Severe");
  assert.equal(event.spine.geometry.type, "Polygon");
  assert.equal(event.spine.sourceId, "urn:oid:abc");
  assert.equal(event.spine.occurredAt, "2026-09-01T23:12:00Z");
  assert.equal(event.spine.expiresAt, "2026-09-02T00:00:00Z");
  assert.equal(event.sourceRecord.properties.certainty, "Observed");
});
