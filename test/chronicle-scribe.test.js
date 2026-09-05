"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildChronicleScribe,
  normalizedRecord,
  fingerprint
} = require("../chronicle-scribe");

function feed(source, events, extra = {}) {
  return {
    ok: true,
    source,
    simulated: false,
    count: events.length,
    events,
    ...extra
  };
}

function usgs(id, magnitude, updatedAt = "2026-09-05T18:00:00.000Z") {
  return {
    id,
    title: `M${magnitude} test quake`,
    magnitude,
    time: "2026-09-05T17:55:00.000Z",
    updatedAt,
    url: `https://earthquake.usgs.gov/${id}`,
    spine: {
      source: "usgs",
      sourceId: id,
      eventType: "earthquake",
      title: `M${magnitude} test quake`,
      magnitude,
      occurredAt: "2026-09-05T17:55:00.000Z",
      updatedAt,
      sourceUrl: `https://earthquake.usgs.gov/${id}`,
      retrievedAt: "2026-09-05T18:01:00.000Z"
    }
  };
}

function nws(id, severity = "Severe") {
  return {
    id,
    event: "Severe Thunderstorm Warning",
    headline: "Severe Thunderstorm Warning",
    severity,
    area: "Test County",
    expires: "2026-09-05T19:00:00.000Z",
    spine: {
      source: "nws",
      sourceId: id,
      eventType: "Severe Thunderstorm Warning",
      title: "Severe Thunderstorm Warning",
      severity,
      occurredAt: "2026-09-05T17:50:00.000Z",
      expiresAt: "2026-09-05T19:00:00.000Z",
      sourceUrl: `https://api.weather.gov/alerts/${id}`,
      retrievedAt: "2026-09-05T18:01:00.000Z",
      sourceMetadata: {
        area: "Test County"
      }
    }
  };
}

function eonet(id) {
  return {
    id,
    title: "Test Wildfire",
    categories: ["Wildfires"],
    time: "2026-09-05T15:00:00.000Z",
    link: `https://eonet.gsfc.nasa.gov/${id}`,
    spine: {
      source: "eonet",
      sourceId: id,
      eventType: "Wildfires",
      title: "Test Wildfire",
      occurredAt: "2026-09-05T15:00:00.000Z",
      sourceUrl: `https://eonet.gsfc.nasa.gov/${id}`,
      retrievedAt: "2026-09-05T18:01:00.000Z"
    }
  };
}

function snapshot({ usgsEvents = [], nwsEvents = [], eonetEvents = [], overrides = {} } = {}) {
  return {
    feeds: {
      usgs: feed("usgs", usgsEvents),
      nws: feed("nws", nwsEvents),
      eonet: feed("eonet", eonetEvents),
      ...overrides
    }
  };
}

test("normalized records remain observation-only and preserve provenance", () => {
  const record = normalizedRecord(usgs("q1", 5.2), "usgs");

  assert.equal(record.authority, "observation");
  assert.equal(record.commandEligible, false);
  assert.equal(record.verification, "DIRECT_SOURCE_NORMALIZED");
  assert.equal(record.sourceUrl, "https://earthquake.usgs.gov/q1");
  assert.equal(record.magnitude, 5.2);
});

test("first Scribe cycle establishes a baseline without inventing changes", () => {
  const report = buildChronicleScribe(
    snapshot({
      usgsEvents: [usgs("q1", 5.2)],
      nwsEvents: [nws("n1")],
      eonetEvents: [eonet("e1")]
    }),
    null,
    new Date("2026-09-05T18:05:00.000Z")
  );

  assert.equal(report.changeState, "BASELINE");
  assert.equal(report.comparisonAvailable, false);
  assert.equal(report.changes.total, 0);
  assert.equal(report.coverage.total, 3);
  assert.equal(report.simulated, false);
  assert.match(report.text, /Baseline established/);
});

test("subsequent Scribe cycle detects new, updated, and window-exit records", () => {
  const first = buildChronicleScribe(
    snapshot({
      usgsEvents: [usgs("q1", 4.5)],
      nwsEvents: [nws("n1")],
      eonetEvents: [eonet("e1")]
    }),
    null,
    new Date("2026-09-05T18:05:00.000Z")
  );

  const second = buildChronicleScribe(
    snapshot({
      usgsEvents: [usgs("q1", 5.1, "2026-09-05T18:08:00.000Z"), usgs("q2", 4.2)],
      nwsEvents: [nws("n1")],
      eonetEvents: []
    }),
    first.baseline,
    new Date("2026-09-05T18:10:00.000Z")
  );

  assert.equal(second.changeState, "DELTA");
  assert.equal(second.changes.newEvents.length, 1);
  assert.equal(second.changes.updatedEvents.length, 1);
  assert.equal(second.changes.notReturned.length, 1);
  assert.equal(second.changes.notReturned[0].kind, "not_returned");
  assert.match(second.changes.notReturned[0].note, /not treated as resolved/i);
  assert.doesNotMatch(second.text, /resolved\.$/m);
});

test("simulated feed data is excluded from Scribe coverage and facts", () => {
  const report = buildChronicleScribe(
    snapshot({
      usgsEvents: [usgs("q1", 6.2)],
      overrides: {
        usgs: {
          ok: true,
          source: "usgs",
          simulated: true,
          count: 1,
          events: [usgs("fake", 9.9)]
        }
      }
    }),
    null,
    new Date("2026-09-05T18:05:00.000Z")
  );

  assert.equal(report.coverage.usgs.ok, false);
  assert.equal(report.coverage.usgs.count, 0);
  assert.equal(report.verifiedFacts.some((fact) => fact.statement.includes("9.9")), false);
  assert.match(report.unknowns.join("\n"), /simulated data and was excluded/i);
});

test("Severe NWS alerts outrank moderate context while large earthquakes remain elevated", () => {
  const report = buildChronicleScribe(
    snapshot({
      usgsEvents: [usgs("q1", 5.3)],
      nwsEvents: [nws("n1", "Severe")],
      eonetEvents: [eonet("e1")]
    }),
    null,
    new Date("2026-09-05T18:05:00.000Z")
  );

  assert.equal(report.priorities[0].source, "nws");
  assert.ok(report.priorities.find((item) => item.source === "usgs" && item.score >= 80));
});

test("fingerprint changes only when source-significant record fields change", () => {
  const a = normalizedRecord(usgs("q1", 4.2), "usgs");
  const b = normalizedRecord(usgs("q1", 4.2), "usgs");
  const c = normalizedRecord(usgs("q1", 4.8), "usgs");

  assert.equal(fingerprint(a), fingerprint(b));
  assert.notEqual(fingerprint(a), fingerprint(c));
});
