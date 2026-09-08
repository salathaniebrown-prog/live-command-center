"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  ShellCatcher,
  analyzeEvent,
  runShellCatcherSelfTest
} = require("../shell-catcher");

test("benign API health observation stays clear", () => {
  const result = analyzeEvent({
    domain: "api",
    method: "GET",
    path: "/api/health",
    payload: { probe: "status" }
  });
  assert.equal(result.flagged, false);
  assert.equal(result.risk, "clear");
});

test("shell chain marker is caught without executing anything", () => {
  const result = analyzeEvent({
    domain: "shell",
    payload: "echo probe && echo second"
  });
  assert.equal(result.flagged, true);
  assert.ok(result.indicators.includes("shell-chain-operator"));
});

test("path traversal marker is caught", () => {
  const result = analyzeEvent({ domain: "api", path: "/safe/../../example" });
  assert.equal(result.flagged, true);
  assert.ok(result.indicators.includes("path-traversal"));
});

test("air water and ground upstream alerts are first-class domains", () => {
  assert.equal(analyzeEvent({ domain: "air", thresholdExceeded: true }).flagged, true);
  assert.equal(analyzeEvent({ domain: "water", severity: "critical" }).flagged, true);
  const ground = analyzeEvent({ domain: "ground", magnitude: 4.6 });
  assert.equal(ground.flagged, true);
  assert.ok(ground.indicators.includes("ground-magnitude-m4-plus"));
});

test("records retain hashes and findings but not raw payloads", () => {
  const catcher = new ShellCatcher({ maxRecords: 50 });
  const record = catcher.ingest({ domain: "shell", payload: "$(echo probe)" });
  assert.equal(record.flagged, true);
  assert.equal(typeof record.payloadHash, "string");
  assert.equal("payload" in record, false);
});

test("built-in corpus reports full coverage", () => {
  const result = runShellCatcherSelfTest();
  assert.equal(result.ok, true);
  assert.equal(result.misses.length, 0);
  assert.equal(result.passed, result.total);
});
