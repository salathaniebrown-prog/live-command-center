"use strict";

const DEFAULT_TIMEOUT_MS = 1800;

function urlAllowed(rawUrl) {
  if (!rawUrl) return false;
  try {
    const url = new URL(rawUrl);
    if (url.protocol === "https:") return true;
    return (
      url.protocol === "http:" &&
      (
        url.hostname === "localhost" ||
        url.hostname === "127.0.0.1" ||
        url.hostname.endsWith(".railway.internal")
      )
    );
  } catch {
    return false;
  }
}

function resolveTelemetryHealthUrl({
  healthUrl = process.env.TELEMETRY_HEALTH_URL || "",
  relayUrl = process.env.TELEMETRY_RELAY_URL || ""
} = {}) {
  const explicit = String(healthUrl || "").trim();
  if (explicit) {
    return urlAllowed(explicit) ? explicit : null;
  }

  const relay = String(relayUrl || "").trim();
  if (!urlAllowed(relay)) return null;

  const url = new URL(relay);
  url.pathname = "/health";
  url.search = "";
  url.hash = "";
  return url.toString();
}

function safeInteger(value) {
  return Number.isInteger(value) && value >= 0 ? value : null;
}

function sanitizeIntegrityHealth(raw) {
  const configured = raw?.signed_ingest_configured === true;
  const wal = raw?.signed_ledger_wal === true;
  const records = raw?.signed_ledger_records;
  const total = safeInteger(records?.total);
  const live = safeInteger(records?.live);
  const replayProtection =
    typeof raw?.signed_replay_protection === "string"
      ? raw.signed_replay_protection.slice(0, 160)
      : null;
  const livePublishRule =
    typeof raw?.signed_live_publish_rule === "string"
      ? raw.signed_live_publish_rule.slice(0, 160)
      : null;
  const schema =
    typeof raw?.signed_ingest_schema === "string"
      ? raw.signed_ingest_schema.slice(0, 96)
      : null;

  let state = "UNVERIFIED";
  if (configured && wal && replayProtection) {
    state = live && live > 0 ? "LIVE_VERIFIED" : "SIGNED_READY";
  }

  return {
    ok: raw?.ok === true,
    configured,
    state,
    schema,
    integrity: {
      hmacConfigured: configured,
      replayProtected: Boolean(replayProtection),
      ledgerWal: wal,
      livePublishRule
    },
    records: {
      total,
      live
    },
    authority: {
      type: "observation",
      commandEligible: false
    },
    checkedAt: new Date().toISOString()
  };
}

async function getTelemetryIntegrity({
  fetchImpl = globalThis.fetch,
  healthUrl,
  relayUrl,
  timeoutMs = DEFAULT_TIMEOUT_MS
} = {}) {
  const resolved = resolveTelemetryHealthUrl({ healthUrl, relayUrl });

  if (!resolved) {
    return {
      ok: true,
      configured: false,
      state: "UNCONFIGURED",
      schema: null,
      integrity: {
        hmacConfigured: false,
        replayProtected: false,
        ledgerWal: false,
        livePublishRule: null
      },
      records: { total: null, live: null },
      authority: { type: "observation", commandEligible: false },
      checkedAt: new Date().toISOString()
    };
  }

  try {
    const response = await fetchImpl(resolved, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(
        Math.max(250, Math.min(5000, Number(timeoutMs) || DEFAULT_TIMEOUT_MS))
      )
    });

    if (!response.ok) {
      throw new Error(`telemetry health returned HTTP ${response.status}`);
    }

    return sanitizeIntegrityHealth(await response.json());
  } catch {
    return {
      ok: false,
      configured: true,
      state: "UNAVAILABLE",
      schema: null,
      integrity: {
        hmacConfigured: null,
        replayProtected: null,
        ledgerWal: null,
        livePublishRule: null
      },
      records: { total: null, live: null },
      authority: { type: "observation", commandEligible: false },
      checkedAt: new Date().toISOString()
    };
  }
}

module.exports = {
  urlAllowed,
  resolveTelemetryHealthUrl,
  sanitizeIntegrityHealth,
  getTelemetryIntegrity
};
