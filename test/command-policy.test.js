"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  OBSERVATION_AUTHORITY,
  isProhibitedCommandName,
  assertObservationTool,
  assertObservationToolset,
  markObservationPayload
} = require("../command-policy");

test("observation authority can never authorize commands", () => {
  assert.equal(OBSERVATION_AUTHORITY.authority, "observation");
  assert.equal(OBSERVATION_AUTHORITY.commandEligible, false);
});

test("prohibited PX4 command names are rejected", () => {
  const prohibited = [
    "arm_vehicle",
    "takeoff",
    "land_vehicle",
    "goto_waypoint",
    "set_velocity",
    "mission_execute"
  ];

  for (const name of prohibited) {
    assert.equal(isProhibitedCommandName(name), true, name);
    assert.throws(
      () => assertObservationTool({ name }),
      /not permitted in observation mode/
    );
  }
});

test("read-only tool names remain allowed", () => {
  const tools = [
    { name: "get_px4_telemetry" },
    { name: "get_world_events" },
    { name: "get_weather_satellites" },
    { name: "search_world_knowledge" }
  ];

  assert.equal(assertObservationToolset(tools), tools);
});

test("observation payloads carry explicit non-command authority", () => {
  const payload = markObservationPayload(
    { source: "nws", eventType: "Tornado Warning" },
    { provenance: { authoritativeSource: "NOAA/NWS" } }
  );

  assert.equal(payload.authority, "observation");
  assert.equal(payload.commandEligible, false);
  assert.equal(payload.provenance.authoritativeSource, "NOAA/NWS");
});
