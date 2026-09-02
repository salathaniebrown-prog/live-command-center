"use strict";

const SCHEMA_VERSION = "eagle-eyes.px4-telemetry.v1";
const DEFAULT_STALE_AFTER_MS = 15000;

function finiteOrNull(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : null;
}

function boundedNumber(value, min, max, field) {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${field} must be a finite number`);
  }

  if (value < min || value > max) {
    throw new Error(`${field} must be between ${min} and ${max}`);
  }

  return value;
}

function optionalBoolean(value, field) {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value !== "boolean") {
    throw new Error(`${field} must be boolean`);
  }

  return value;
}

function optionalString(value, field, max = 96) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  if (typeof value !== "string") {
    throw new Error(`${field} must be a string`);
  }

  const cleaned = value.trim();

  if (!cleaned) {
    return null;
  }

  if (cleaned.length > max) {
    throw new Error(`${field} exceeds ${max} characters`);
  }

  return cleaned;
}

function optionalTimestamp(value, field) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const date = new Date(value);

  if (!Number.isFinite(date.getTime())) {
    throw new Error(`${field} must be a valid timestamp`);
  }

  return date.toISOString();
}

function normalizePosition(input) {
  if (!input) {
    return null;
  }

  const latitude = boundedNumber(
    input.latitude,
    -90,
    90,
    "position.latitude"
  );

  const longitude = boundedNumber(
    input.longitude,
    -180,
    180,
    "position.longitude"
  );

  if (latitude === null || longitude === null) {
    throw new Error(
      "position.latitude and position.longitude must be supplied together"
    );
  }

  return {
    latitude,
    longitude,
    altitudeM:
      boundedNumber(
        input.altitudeM,
        -2000,
        100000,
        "position.altitudeM"
      ),
    relativeAltitudeM:
      boundedNumber(
        input.relativeAltitudeM,
        -2000,
        100000,
        "position.relativeAltitudeM"
      )
  };
}

function normalizeGps(input) {
  if (!input) {
    return null;
  }

  return {
    fixType:
      boundedNumber(
        input.fixType,
        0,
        6,
        "gps.fixType"
      ),
    satellites:
      boundedNumber(
        input.satellites,
        0,
        100,
        "gps.satellites"
      ),
    hdop:
      boundedNumber(
        input.hdop,
        0,
        100,
        "gps.hdop"
      ),
    vdop:
      boundedNumber(
        input.vdop,
        0,
        100,
        "gps.vdop"
      )
  };
}

function normalizeAttitude(input) {
  if (!input) {
    return null;
  }

  return {
    rollDeg:
      boundedNumber(
        input.rollDeg,
        -180,
        180,
        "attitude.rollDeg"
      ),
    pitchDeg:
      boundedNumber(
        input.pitchDeg,
        -90,
        90,
        "attitude.pitchDeg"
      ),
    yawDeg:
      boundedNumber(
        input.yawDeg,
        -180,
        360,
        "attitude.yawDeg"
      )
  };
}

function normalizeVelocity(input) {
  if (!input) {
    return null;
  }

  return {
    northMps:
      boundedNumber(
        input.northMps,
        -500,
        500,
        "velocity.northMps"
      ),
    eastMps:
      boundedNumber(
        input.eastMps,
        -500,
        500,
        "velocity.eastMps"
      ),
    downMps:
      boundedNumber(
        input.downMps,
        -500,
        500,
        "velocity.downMps"
      ),
    groundSpeedMps:
      boundedNumber(
        input.groundSpeedMps,
        0,
        500,
        "velocity.groundSpeedMps"
      ),
    verticalSpeedMps:
      boundedNumber(
        input.verticalSpeedMps,
        -500,
        500,
        "velocity.verticalSpeedMps"
      )
  };
}

function normalizeBattery(input) {
  if (!input) {
    return null;
  }

  return {
    voltageV:
      boundedNumber(
        input.voltageV,
        0,
        100,
        "battery.voltageV"
      ),
    currentA:
      boundedNumber(
        input.currentA,
        -1000,
        1000,
        "battery.currentA"
      ),
    remainingPct:
      boundedNumber(
        input.remainingPct,
        0,
        100,
        "battery.remainingPct"
      )
  };
}

function normalizeLink(input) {
  if (!input) {
    return null;
  }

  return {
    rssiPct:
      boundedNumber(
        input.rssiPct,
        0,
        100,
        "link.rssiPct"
      ),
    packetLossPct:
      boundedNumber(
        input.packetLossPct,
        0,
        100,
        "link.packetLossPct"
      ),
    latencyMs:
      boundedNumber(
        input.latencyMs,
        0,
        60000,
        "link.latencyMs"
      )
  };
}

function hasUsefulTelemetry(snapshot) {
  return Boolean(
    snapshot.flightMode ||
    snapshot.armed !== null ||
    snapshot.landed !== null ||
    snapshot.position ||
    snapshot.gps ||
    snapshot.attitude ||
    snapshot.velocity ||
    snapshot.battery ||
    snapshot.link
  );
}

function normalizePx4Telemetry(
  input,
  receivedAt = new Date().toISOString()
) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("telemetry payload must be an object");
  }

  const vehicleId =
    optionalString(
      input.vehicleId,
      "vehicleId",
      64
    );

  if (!vehicleId) {
    throw new Error("vehicleId is required");
  }

  const snapshot = {
    schemaVersion: SCHEMA_VERSION,
    simulated: false,
    vehicleId,
    autopilot:
      optionalString(
        input.autopilot,
        "autopilot",
        32
      ) || "PX4",
    transport:
      optionalString(
        input.transport,
        "transport",
        48
      ),
    sourceObservedAt:
      optionalTimestamp(
        input.observedAt,
        "observedAt"
      ),
    receivedAt:
      optionalTimestamp(
        receivedAt,
        "receivedAt"
      ),
    flightMode:
      optionalString(
        input.flightMode,
        "flightMode",
        48
      ),
    armed:
      optionalBoolean(
        input.armed,
        "armed"
      ),
    landed:
      optionalBoolean(
        input.landed,
        "landed"
      ),
    position:
      normalizePosition(
        input.position
      ),
    gps:
      normalizeGps(
        input.gps
      ),
    attitude:
      normalizeAttitude(
        input.attitude
      ),
    velocity:
      normalizeVelocity(
        input.velocity
      ),
    battery:
      normalizeBattery(
        input.battery
      ),
    link:
      normalizeLink(
        input.link
      ),
    sourceMetadata: {
      systemId:
        boundedNumber(
          input.systemId,
          0,
          255,
          "systemId"
        ),
      componentId:
        boundedNumber(
          input.componentId,
          0,
          255,
          "componentId"
        ),
      px4Version:
        optionalString(
          input.px4Version,
          "px4Version",
          64
        ),
      bridgeVersion:
        optionalString(
          input.bridgeVersion,
          "bridgeVersion",
          64
        )
    }
  };

  if (!hasUsefulTelemetry(snapshot)) {
    throw new Error(
      "payload must include at least one telemetry field"
    );
  }

  return snapshot;
}

class Px4TelemetryStore {
  constructor({
    staleAfterMs = DEFAULT_STALE_AFTER_MS
  } = {}) {
    this.staleAfterMs =
      Number.isFinite(staleAfterMs) &&
      staleAfterMs >= 1000
        ? staleAfterMs
        : DEFAULT_STALE_AFTER_MS;

    this.latest = null;
    this.receivedCount = 0;
  }

  ingest(input, now = new Date()) {
    const receivedAt =
      new Date(now).toISOString();

    const snapshot =
      normalizePx4Telemetry(
        input,
        receivedAt
      );

    this.latest = snapshot;
    this.receivedCount += 1;

    return snapshot;
  }

  status({
    configured = false,
    now = new Date()
  } = {}) {
    const checkedAt =
      new Date(now).toISOString();

    if (!configured) {
      return {
        ok: true,
        configured: false,
        state: "UNCONFIGURED",
        simulated: false,
        schemaVersion: SCHEMA_VERSION,
        staleAfterMs: this.staleAfterMs,
        receivedCount: this.receivedCount,
        telemetry: null,
        ageMs: null,
        checkedAt
      };
    }

    if (!this.latest) {
      return {
        ok: true,
        configured: true,
        state: "WAITING",
        simulated: false,
        schemaVersion: SCHEMA_VERSION,
        staleAfterMs: this.staleAfterMs,
        receivedCount: this.receivedCount,
        telemetry: null,
        ageMs: null,
        checkedAt
      };
    }

    const ageMs = Math.max(
      0,
      new Date(now).getTime() -
      new Date(this.latest.receivedAt).getTime()
    );

    return {
      ok: true,
      configured: true,
      state:
        ageMs <= this.staleAfterMs
          ? "LIVE"
          : "STALE",
      simulated: false,
      schemaVersion: SCHEMA_VERSION,
      staleAfterMs: this.staleAfterMs,
      receivedCount: this.receivedCount,
      telemetry: this.latest,
      ageMs,
      checkedAt
    };
  }
}

function formatPx4Telemetry(status) {
  const t = status?.telemetry;

  const lines = [
    "EAGLE EYES PX4 TELEMETRY",
    `State: ${status?.state || "N/A"}`,
    `Configured: ${status?.configured ? "YES" : "NO"}`,
    "Simulation: OFF"
  ];

  if (!t) {
    if (status?.state === "UNCONFIGURED") {
      lines.push(
        "PX4 telemetry ingest is not configured yet."
      );
    } else if (status?.state === "WAITING") {
      lines.push(
        "PX4 telemetry ingest is configured but no validated snapshot has arrived yet."
      );
    }

    lines.push(
      `Checked: ${status?.checkedAt || "N/A"}`
    );

    return lines.join("\n");
  }

  lines.push(
    `Vehicle: ${t.vehicleId}`,
    `Autopilot: ${t.autopilot || "PX4"}`,
    `Transport: ${t.transport || "N/A"}`,
    `Flight mode: ${t.flightMode || "N/A"}`,
    `Armed: ${t.armed === null ? "N/A" : t.armed ? "YES" : "NO"}`,
    `Landed: ${t.landed === null ? "N/A" : t.landed ? "YES" : "NO"}`,
    `GPS: ${
      t.position
        ? `${t.position.latitude.toFixed(6)}, ${t.position.longitude.toFixed(6)}`
        : "N/A"
    }`,
    `Altitude: ${
      Number.isFinite(t.position?.altitudeM)
        ? `${t.position.altitudeM} m`
        : "N/A"
    }`,
    `Battery: ${
      Number.isFinite(t.battery?.remainingPct)
        ? `${t.battery.remainingPct}%`
        : "N/A"
    }`,
    `Link RSSI: ${
      Number.isFinite(t.link?.rssiPct)
        ? `${t.link.rssiPct}%`
        : "N/A"
    }`,
    `Age: ${
      Number.isFinite(status.ageMs)
        ? `${status.ageMs} ms`
        : "N/A"
    }`,
    `Observed: ${t.sourceObservedAt || "N/A"}`,
    `Received: ${t.receivedAt || "N/A"}`,
    `Checked: ${status.checkedAt || "N/A"}`
  );

  if (status.state === "STALE") {
    lines.push(
      "WARNING: telemetry is stale; do not treat it as current vehicle state."
    );
  }

  return lines.join("\n");
}

module.exports = {
  SCHEMA_VERSION,
  DEFAULT_STALE_AFTER_MS,
  normalizePx4Telemetry,
  Px4TelemetryStore,
  formatPx4Telemetry
};
