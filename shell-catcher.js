"use strict";

const crypto = require("node:crypto");

const DOMAINS = new Set(["api", "shell", "air", "water", "ground", "system"]);
const SEVERITY_SCORES = {
  info: 0,
  low: 10,
  watch: 20,
  warning: 35,
  moderate: 35,
  high: 60,
  severe: 75,
  critical: 90,
  extreme: 100
};

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function safeString(value, max = 512) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, max);
}

function collectStrings(value, out = [], depth = 0) {
  if (depth > 4 || out.length >= 64) return out;
  if (typeof value === "string") {
    out.push(value.slice(0, 2048));
    return out;
  }
  if (Array.isArray(value)) {
    for (const item of value.slice(0, 32)) collectStrings(item, out, depth + 1);
    return out;
  }
  if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value).slice(0, 64)) {
      out.push(String(key).slice(0, 128));
      collectStrings(item, out, depth + 1);
    }
  }
  return out;
}

function hashPayload(payload) {
  let serialized;
  try {
    serialized = JSON.stringify(payload ?? null);
  } catch {
    serialized = String(payload);
  }
  return crypto.createHash("sha256").update(serialized).digest("hex");
}

function analyzeSecurityStrings(strings) {
  const joined = strings.join("\n");
  const indicators = [];
  let score = 0;

  const rules = [
    ["shell-chain-operator", /(?:&&|\|\|)/, 35],
    ["shell-command-substitution", /\$\([^\n)]{1,180}\)|`[^`\n]{1,180}`/, 45],
    ["shell-interpreter-reference", /(?:^|[\s"'])(?:\/bin\/(?:sh|bash)|powershell(?:\.exe)?|cmd\.exe)(?:$|[\s"'])/i, 30],
    ["command-downloader-reference", /(?:^|[\s"'])(?:curl|wget)(?:$|[\s"'])/i, 20],
    ["path-traversal", /(?:\.\.\/|\.\.\\)/, 40],
    ["encoded-command-marker", /(?:base64\s+-d|frombase64string|encodedcommand)/i, 30],
    ["shell-redirection", /(?:^|\s)(?:>>?|2>|&>)(?:\s|$)/, 20]
  ];

  for (const [name, pattern, points] of rules) {
    if (pattern.test(joined)) {
      indicators.push(name);
      score += points;
    }
  }

  return { score: clamp(score, 0, 100), indicators };
}

function environmentalAnalysis(event) {
  const domain = String(event.domain || "").toLowerCase();
  if (!["air", "water", "ground"].includes(domain)) {
    return { score: 0, indicators: [] };
  }

  const indicators = [];
  let score = 0;
  const severity = String(event.severity || event.status || "").toLowerCase();

  if (severity && Object.prototype.hasOwnProperty.call(SEVERITY_SCORES, severity)) {
    score = Math.max(score, SEVERITY_SCORES[severity]);
    if (SEVERITY_SCORES[severity] >= 35) indicators.push(`${domain}-upstream-${severity}`);
  }

  if (event.thresholdExceeded === true) {
    score = Math.max(score, 65);
    indicators.push(`${domain}-threshold-exceeded`);
  }

  if (domain === "ground") {
    const magnitude = Number(event.magnitude);
    if (Number.isFinite(magnitude) && magnitude >= 4) {
      score = Math.max(score, magnitude >= 6 ? 90 : magnitude >= 5 ? 75 : 55);
      indicators.push("ground-magnitude-m4-plus");
    }
  }

  return { score: clamp(score, 0, 100), indicators };
}

function normalizeEvent(event = {}) {
  if (!event || typeof event !== "object" || Array.isArray(event)) {
    throw new Error("event must be an object");
  }

  const domain = safeString(event.domain || "api", 32).toLowerCase();
  if (!DOMAINS.has(domain)) {
    throw new Error(`unsupported domain: ${domain || "empty"}`);
  }

  return {
    domain,
    source: safeString(event.source || "unknown", 120),
    eventType: safeString(event.eventType || event.type || "observation", 120),
    method: safeString(event.method || "", 16).toUpperCase(),
    path: safeString(event.path || "", 512),
    severity: safeString(event.severity || event.status || "info", 32).toLowerCase(),
    thresholdExceeded: event.thresholdExceeded === true,
    magnitude: Number.isFinite(Number(event.magnitude)) ? Number(event.magnitude) : null,
    observedAt: safeString(event.observedAt || event.timestamp || new Date().toISOString(), 64),
    simulated: event.simulated === true,
    payload: event.payload ?? event.data ?? event.signal ?? null
  };
}

function analyzeEvent(event = {}) {
  const normalized = normalizeEvent(event);
  const strings = collectStrings({
    path: normalized.path,
    eventType: normalized.eventType,
    payload: normalized.payload
  });
  const security = analyzeSecurityStrings(strings);
  const environment = environmentalAnalysis({ ...event, ...normalized });
  const score = Math.max(security.score, environment.score);
  const indicators = [...new Set([...security.indicators, ...environment.indicators])];

  return {
    score,
    indicators,
    flagged: score >= 35,
    risk: score >= 85 ? "critical" : score >= 60 ? "high" : score >= 35 ? "elevated" : score >= 20 ? "watch" : "clear",
    domain: normalized.domain,
    source: normalized.source,
    eventType: normalized.eventType,
    method: normalized.method,
    path: normalized.path,
    severity: normalized.severity,
    thresholdExceeded: normalized.thresholdExceeded,
    magnitude: normalized.magnitude,
    observedAt: normalized.observedAt,
    simulated: normalized.simulated,
    payloadHash: hashPayload(normalized.payload)
  };
}

class ShellCatcher {
  constructor({ maxRecords = 500 } = {}) {
    this.maxRecords = clamp(Number(maxRecords) || 500, 50, 5000);
    this.records = [];
    this.startedAt = new Date().toISOString();
    this.total = 0;
    this.flagged = 0;
  }

  ingest(event) {
    const analysis = analyzeEvent(event);
    const record = {
      id: crypto.randomUUID(),
      receivedAt: new Date().toISOString(),
      ...analysis
    };
    this.total += 1;
    if (record.flagged) this.flagged += 1;
    this.records.push(record);
    if (this.records.length > this.maxRecords) {
      this.records.splice(0, this.records.length - this.maxRecords);
    }
    return record;
  }

  recent(limit = 50) {
    const n = clamp(Number(limit) || 50, 1, 250);
    return this.records.slice(-n).reverse();
  }

  status({ ingestConfigured = false } = {}) {
    return {
      ok: true,
      service: "eagle-eyes-shell-catcher",
      mode: "LIVE_DEFENSIVE_OBSERVATION",
      operational: true,
      ingestConfigured: Boolean(ingestConfigured),
      arbitraryShellExecution: false,
      commandAuthority: false,
      domains: ["api", "shell", "air", "water", "ground", "system"],
      records: {
        total: this.total,
        flagged: this.flagged,
        retained: this.records.length,
        maxRetained: this.maxRecords
      },
      startedAt: this.startedAt,
      timestamp: new Date().toISOString()
    };
  }
}

function safeEqual(received, expected) {
  if (!received || !expected) return false;
  const left = Buffer.from(String(received));
  const right = Buffer.from(String(expected));
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function builtInCorpus() {
  return [
    {
      name: "benign-api-health",
      expectedFlagged: false,
      event: { domain: "api", source: "self-test", method: "GET", path: "/api/health", payload: { probe: "status" } }
    },
    {
      name: "shell-chain-marker",
      expectedFlagged: true,
      event: { domain: "shell", source: "self-test", eventType: "test-string", payload: "echo probe && echo second" }
    },
    {
      name: "command-substitution-marker",
      expectedFlagged: true,
      event: { domain: "shell", source: "self-test", eventType: "test-string", payload: "$(echo probe)" }
    },
    {
      name: "path-traversal-marker",
      expectedFlagged: true,
      event: { domain: "api", source: "self-test", method: "GET", path: "/safe/../../example" }
    },
    {
      name: "air-upstream-threshold",
      expectedFlagged: true,
      event: { domain: "air", source: "self-test", eventType: "air-quality", thresholdExceeded: true, severity: "warning" }
    },
    {
      name: "water-critical-upstream",
      expectedFlagged: true,
      event: { domain: "water", source: "self-test", eventType: "water-quality", severity: "critical" }
    },
    {
      name: "ground-m4-plus",
      expectedFlagged: true,
      event: { domain: "ground", source: "self-test", eventType: "earthquake", magnitude: 4.6, severity: "watch" }
    },
    {
      name: "ground-small-event",
      expectedFlagged: false,
      event: { domain: "ground", source: "self-test", eventType: "earthquake", magnitude: 2.0, severity: "info" }
    }
  ];
}

function runShellCatcherSelfTest() {
  const cases = builtInCorpus().map((item) => {
    const result = analyzeEvent(item.event);
    const pass = result.flagged === item.expectedFlagged;
    return {
      name: item.name,
      expectedFlagged: item.expectedFlagged,
      actualFlagged: result.flagged,
      risk: result.risk,
      indicators: result.indicators,
      pass
    };
  });
  const misses = cases.filter((item) => !item.pass);
  return {
    ok: misses.length === 0,
    passed: cases.length - misses.length,
    total: cases.length,
    coveragePercent: Number((((cases.length - misses.length) / cases.length) * 100).toFixed(1)),
    misses,
    cases,
    timestamp: new Date().toISOString()
  };
}

function registerShellCatcher(app, { readGuard } = {}) {
  if (!app || typeof app.get !== "function" || typeof app.post !== "function") {
    throw new Error("Express app is required");
  }

  const catcher = new ShellCatcher({ maxRecords: process.env.SHELL_CATCHER_MAX_RECORDS });
  const ingestToken = process.env.SHELL_CATCHER_INGEST_TOKEN || "";
  const guard = typeof readGuard === "function" ? readGuard : (_req, _res, next) => next();

  function requireIngest(req, res, next) {
    if (!ingestToken) {
      return res.status(503).json({
        ok: false,
        error: "Shell Catcher ingest is locked until SHELL_CATCHER_INGEST_TOKEN is configured"
      });
    }
    const authorization = req.get("authorization") || "";
    const match = authorization.match(/^Bearer\s+(.+)$/i);
    if (!match || !safeEqual(match[1], ingestToken)) {
      return res.status(401).json({ ok: false, error: "Unauthorized" });
    }
    return next();
  }

  app.get("/api/eagle-eyes/shell-catcher/health", (_req, res) => {
    res.set("cache-control", "no-store");
    res.json(catcher.status({ ingestConfigured: Boolean(ingestToken) }));
  });

  app.get("/api/eagle-eyes/shell-catcher/status", guard, (_req, res) => {
    res.set("cache-control", "no-store");
    res.json({
      ...catcher.status({ ingestConfigured: Boolean(ingestToken) }),
      selfTest: runShellCatcherSelfTest()
    });
  });

  app.get("/api/eagle-eyes/shell-catcher/events", guard, (req, res) => {
    res.set("cache-control", "no-store");
    res.json({ ok: true, events: catcher.recent(req.query.limit), timestamp: new Date().toISOString() });
  });

  app.post("/api/eagle-eyes/shell-catcher/ingest", requireIngest, (req, res) => {
    try {
      const record = catcher.ingest(req.body);
      return res.status(202).json({ ok: true, accepted: true, record, rawPayloadStored: false });
    } catch (error) {
      return res.status(400).json({
        ok: false,
        accepted: false,
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  });

  app.post("/api/eagle-eyes/shell-catcher/self-test", guard, (_req, res) => {
    res.set("cache-control", "no-store");
    res.json(runShellCatcherSelfTest());
  });

  return catcher;
}

module.exports = {
  DOMAINS,
  ShellCatcher,
  analyzeEvent,
  builtInCorpus,
  runShellCatcherSelfTest,
  registerShellCatcher
};
