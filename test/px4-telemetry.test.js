"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  SCHEMA_VERSION,
  normalizePx4Telemetry,
  Px4TelemetryStore,
  formatPx4Telemetry
} = require("../px4-telemetry");

test("normalizes a real PX4 telemetry snapshot without inventing missing values", () => {
  const result = normalizePx4Telemetry({
    vehicleId: "eagle-1",
    autopilot: "PX4",
    transport: "mavlink-companion",
    observedAt: "2026-09-02T02:30:00Z",
    flightMode: "POSCTL",
    armed: true,
    landed: false,
    systemId: 1,
    componentId: 1,
    px4Version: "1.16.0",
    position: {
      latitude: 35.7796,
      longitude: -78.6382,
      altitudeM: 121.4,
      relativeAltitudeM: 42.8
    },
    gps: {
      fixType: 3,
      satellites: 18,
      hdop: 0.8
    },
    attitude: {
      rollDeg: 2.5,
      pitchDeg: -1.2,
      yawDeg: 183.4
    },
    velocity: {
      northMps: 4.2,
      eastMps: 1.1,
      downMps: -0.2,
      groundSpeedMps: 4.34
    },
    battery: {
      voltageV: 15.7,
      currentA: 8.4,
      remainingPct: 72
    },
    link: {
      rssiPct: 91,
      packetLossPct: 0.2,
      latencyMs: 38
    }
  }, "2026-09-02T02:30:01Z");

  assert.equal(result.schemaVersion, SCHEMA_VERSION);
  assert.equal(result.simulated, false);
  assert.equal(result.vehicleId, "eagle-1");
  assert.equal(result.position.latitude, 35.7796);
  assert.equal(result.position.longitude, -78.6382);
  assert.equal(result.battery.remainingPct, 72);
  assert.equal(result.link.rssiPct, 91);
  assert.equal(result.gps.vdop, null);
});

test("rejects impossible coordinates instead of silently accepting bad telemetry", () => {
  assert.throws(
    () => normalizePx4Telemetry({
      vehicleId: "eagle-1",
      position: {
        latitude: 95,
        longitude: -78
      }
    }),
    /position\.latitude/
  );
});

test("requires at least one actual telemetry field", () => {
  assert.throws(
    () => normalizePx4Telemetry({
      vehicleId: "eagle-1",
      px4Version: "1.16.0"
    }),
    /at least one telemetry field/
  );
});

test("reports UNCONFIGURED, WAITING, LIVE and STALE honestly", () => {
  const store = new Px4TelemetryStore({
    staleAfterMs: 15000
  });

  assert.equal(
    store.status({
      configured: false,
      now: "2026-09-02T02:30:00Z"
    }).state,
    "UNCONFIGURED"
  );

  assert.equal(
    store.status({
      configured: true,
      now: "2026-09-02T02:30:00Z"
    }).state,
    "WAITING"
  );

  store.ingest({
    vehicleId: "eagle-1",
    armed: false,
    flightMode: "MANUAL"
  }, "2026-09-02T02:30:00Z");

  assert.equal(
    store.status({
      configured: true,
      now: "2026-09-02T02:30:10Z"
    }).state,
    "LIVE"
  );

  assert.equal(
    store.status({
      configured: true,
      now: "2026-09-02T02:30:20Z"
    }).state,
    "STALE"
  );
});

test("marks delayed source observations stale even when they were just received", () => {
  const store = new Px4TelemetryStore({
    staleAfterMs: 15000
  });

  store.ingest({
    vehicleId: "eagle-1",
    observedAt: "2026-09-02T02:29:00Z",
    armed: true
  }, "2026-09-02T02:30:00Z");

  const status = store.status({
    configured: true,
    now: "2026-09-02T02:30:01Z"
  });

  assert.equal(status.receivedAgeMs, 1000);
  assert.equal(status.sourceAgeMs, 61000);
  assert.equal(status.state, "STALE");
});

test("formatted stale telemetry warns that it is not current vehicle state", () => {
  const store = new Px4TelemetryStore({
    staleAfterMs: 1000
  });

  store.ingest({
    vehicleId: "eagle-1",
    armed: true,
    battery: {
      remainingPct: 50
    }
  }, "2026-09-02T02:30:00Z");

  const status = store.status({
    configured: true,
    now: "2026-09-02T02:30:10Z"
  });

  const text = formatPx4Telemetry(status);

  assert.match(text, /State: STALE/);
  assert.match(text, /WARNING: telemetry is stale/);
  assert.match(text, /Simulation: OFF/);
});
