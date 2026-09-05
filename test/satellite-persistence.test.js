"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const {
  CACHE_MS,
  fetchWeatherElements,
  resetCache
} = require("../satellites");

const sample = {
  OBJECT_NAME: "TEST WEATHER SAT",
  NORAD_CAT_ID: 99999,
  EPOCH: "2026-09-04T20:00:00.000000"
};

test("recovers persisted CelesTrak elements when the live source is unavailable", async (t) => {
  const dir = await fs.mkdtemp(
    path.join(os.tmpdir(), "eagle-eyes-satellite-state-")
  );
  const statePath = path.join(dir, "weather-elements.json");

  t.after(async () => {
    await fs.rm(dir, { recursive: true, force: true });
  });

  resetCache();

  const online = await fetchWeatherElements({
    statePath,
    nowMs: Date.parse("2026-09-04T20:00:00.000Z"),
    fetchImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => [sample]
    })
  });

  assert.equal(online.persistentSaved, true);
  assert.equal(online.persistentFallback, false);

  resetCache();

  const offline = await fetchWeatherElements({
    statePath,
    nowMs:
      Date.parse("2026-09-04T20:00:00.000Z") +
      CACHE_MS +
      1,
    fetchImpl: async () => {
      throw new Error("test upstream offline");
    }
  });

  assert.equal(offline.persistentFallback, true);
  assert.equal(offline.cached, true);
  assert.equal(offline.records.length, 1);
  assert.equal(offline.records[0].OBJECT_NAME, sample.OBJECT_NAME);
  assert.match(offline.fallbackReason, /upstream offline/);
});
