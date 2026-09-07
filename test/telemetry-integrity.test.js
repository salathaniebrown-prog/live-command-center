"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  urlAllowed,
  resolveTelemetryHealthUrl,
  sanitizeIntegrityHealth,
  getTelemetryIntegrity
} = require("../telemetry-integrity");

test("telemetry health URL only allows HTTPS or trusted local/internal HTTP", () => {
  assert.equal(urlAllowed("https://example.com/health"), true);
  assert.equal(urlAllowed("http://127.0.0.1:8080/health"), true);
  assert.equal(urlAllowed("http://telemetry.railway.internal:8080/health"), true);
  assert.equal(urlAllowed("http://example.com/health"), false);
  assert.equal(urlAllowed("file:///tmp/health"), false);
});

test("health URL derives from the configured relay without retaining ingest path", () => {
  assert.equal(
    resolveTelemetryHealthUrl({
      relayUrl: "http://telemetry.railway.internal:8080/ingest/px4"
    }),
    "http://telemetry.railway.internal:8080/health"
  );
});

test("sanitized health exposes integrity facts but not raw infrastructure details", () => {
  const result = sanitizeIntegrityHealth({
    ok: true,
    kafka_connected: true,
    assigned_partitions: ["secret-topic:0"],
    signed_ingest_configured: true,
    signed_ingest_schema: "eagle-eyes.signed-telemetry.v1",
    signed_live_publish_rule: "sourceMode=LIVE and simulated=false only",
    signed_replay_protection: "sourceId+nonce unique ledger key",
    signed_ledger_wal: true,
    signed_ledger_records: { total: 4, live: 2 }
  });

  assert.equal(result.state, "LIVE_VERIFIED");
  assert.equal(result.integrity.hmacConfigured, true);
  assert.equal(result.integrity.replayProtected, true);
  assert.equal(result.integrity.ledgerWal, true);
  assert.deepEqual(result.records, { total: 4, live: 2 });
  assert.equal(result.authority.type, "observation");
  assert.equal(result.authority.commandEligible, false);
  assert.equal("kafka_connected" in result, false);
  assert.equal("assigned_partitions" in result, false);
});

test("configured secure spine without live records reports SIGNED_READY, not LIVE", () => {
  const result = sanitizeIntegrityHealth({
    ok: true,
    signed_ingest_configured: true,
    signed_replay_protection: "sourceId+nonce unique ledger key",
    signed_ledger_wal: true,
    signed_ledger_records: { total: 0, live: 0 }
  });
  assert.equal(result.state, "SIGNED_READY");
});

test("unconfigured command center does not fabricate secure telemetry state", async () => {
  const result = await getTelemetryIntegrity({
    healthUrl: "",
    relayUrl: ""
  });
  assert.equal(result.state, "UNCONFIGURED");
  assert.equal(result.configured, false);
  assert.equal(result.records.live, null);
});

test("health fetch failure reports UNAVAILABLE instead of VERIFIED", async () => {
  const result = await getTelemetryIntegrity({
    healthUrl: "https://telemetry.example/health",
    fetchImpl: async () => {
      throw new Error("offline");
    }
  });
  assert.equal(result.state, "UNAVAILABLE");
  assert.equal(result.ok, false);
});
