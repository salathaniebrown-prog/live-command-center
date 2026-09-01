"use strict";

const express = require("express");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const {
  knowledgeSearch,
  globalWeather,
  formatKnowledge,
  formatWeather,
  worldOSStatus,
  shouldUseFreeKnowledge
} = require("./world-os");
const { execFile } = require("child_process");
const { promisify } = require("util");

const app = express();
const runFile = promisify(execFile);
const PORT = Number(process.env.PORT) || 3000;
const startedAt = new Date();
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-5.6";
const COMMAND_CENTER_ACCESS_TOKEN = process.env.COMMAND_CENTER_ACCESS_TOKEN || "";
const OPENAI_URL = "https://api.openai.com/v1/responses";

const SOURCES = {
  usgs: "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
  eonet: "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100",
  nws: "https://api.weather.gov/alerts/active"
};

const EMPTY = {
  type: "object",
  properties: {},
  required: [],
  additionalProperties: false
};

const TOOLS = [
  {
    type: "function",
    name: "get_command_center_status",
    description: "Get current Command Center status and uptime.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_command_center_metrics",
    description:
      "Get live container CPU, GPU if exposed, memory, storage and temperature if exposed.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_deployment_status",
    description:
      "Get current Railway deployment state and runtime IDs when exposed.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_system_health",
    description: "Get current API health and uptime.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_operational_snapshot",
    description:
      "Get one combined live operational snapshot across Command Center health, container metrics, Railway deployment, NOAA/NWS, USGS, and NASA EONET for situation analysis and prioritization.",
    strict: true,
    parameters: EMPTY
  },
  {
    type: "function",
    name: "get_world_events",
    description:
      "Get current public events from USGS, NASA EONET, or NOAA/NWS. Never simulate missing data.",
    strict: true,
    parameters: {
      type: "object",
      properties: {
        source: {
          type: "string",
          enum: ["usgs", "eonet", "nws"]
        },
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 20
        }
      },
      required: ["source", "limit"],
      additionalProperties: false
    }
  },
  {
    type: "function",
    name: "search_world_knowledge",
    description:
      "Search free encyclopedic world knowledge for people, places, organizations, history, science, technology, and general factual topics.",
    strict: true,
    parameters: {
      type: "object",
      properties: {
        query: {
          type: "string"
        },
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 5
        }
      },
      required: ["query", "limit"],
      additionalProperties: false
    }
  },
  {
    type: "function",
    name: "get_global_weather",
    description:
      "Get current global weather for a named city or location using live Open-Meteo data.",
    strict: true,
    parameters: {
      type: "object",
      properties: {
        location: {
          type: "string"
        }
      },
      required: ["location"],
      additionalProperties: false
    }
  },
  {
    type: "function",
    name: "get_world_os_status",
    description:
      "Get Eagle Eyes World Command Operating System capability and module status.",
    strict: true,
    parameters: EMPTY
  }
];

const INSTRUCTIONS = [
  "You are Eagle Eyes, the intelligence core of the EAGLE EYES WORLD COMMAND OPERATING SYSTEM.",
  "Use tools for current system state, metrics, deployment state, health, world-event feeds, global weather, and encyclopedic world knowledge.",
  "For general factual questions that benefit from reference knowledge, call search_world_knowledge. For current weather by place, call get_global_weather.",
  "For a mission brief, situation report, broad incident-priority request, or question about what matters now, call get_operational_snapshot before answering.",
  "When prioritizing, distinguish source facts from interpretation and use explicit NWS severity, earthquake magnitude, recency, deployment health, and container pressure as evidence.",
  "Keep mission briefs executive and mobile-friendly: group related alerts, show no more than five top incidents, shorten long area lists, separate system pressure from external incidents, explain why each priority matters, and finish with a short WATCH NEXT section.",
  "Never invent telemetry, alerts, sensor values, or deployment state.",
  "If a value is unavailable, say N/A or unavailable.",
  "All tools are read-only; never claim you changed infrastructure, files, credentials, accounts, or deployments."
].join(" ");

app.disable("x-powered-by");
app.use(express.json({ limit: "256kb" }));
app.use(express.static(path.join(__dirname, "public")));

function secretsMatch(received, expected) {
  if (!received || !expected) {
    return false;
  }

  const a = Buffer.from(received);
  const b = Buffer.from(expected);

  return (
    a.length === b.length &&
    crypto.timingSafeEqual(a, b)
  );
}

function requireAssistantAccess(req, res, next) {
  if (!COMMAND_CENTER_ACCESS_TOKEN) {
    return res.status(503).json({
      ok: false,
      error:
        "Assistant access is locked until COMMAND_CENTER_ACCESS_TOKEN is configured"
    });
  }

  const authorization =
    req.get("authorization") || "";

  const match =
    authorization.match(
      /^Bearer\s+(.+)$/i
    );

  if (
    !match ||
    !secretsMatch(
      match[1],
      COMMAND_CENTER_ACCESS_TOKEN
    )
  ) {
    return res.status(401).json({
      ok: false,
      error: "Unauthorized"
    });
  }

  return next();
}

function cpuTimes() {
  return os.cpus().reduce(
    (s, c) => {
      const t = c.times;
      s.idle += t.idle;
      s.total += t.user + t.nice + t.sys + t.idle + t.irq;
      return s;
    },
    { idle: 0, total: 0 }
  );
}

async function cpuPercent() {
  const a = cpuTimes();

  await new Promise((r) => setTimeout(r, 200));

  const b = cpuTimes();
  const total = b.total - a.total;

  return total > 0
    ? Number(((1 - (b.idle - a.idle) / total) * 100).toFixed(1))
    : null;
}

async function storagePercent() {
  try {
    const { stdout } = await runFile("df", ["-P", "/"]);

    return Number(
      stdout
        .trim()
        .split("\n")
        .at(-1)
        .trim()
        .split(/\s+/)[4]
        .replace("%", "")
    );
  } catch {
    return null;
  }
}

async function gpuPercent() {
  try {
    const { stdout } = await runFile("nvidia-smi", [
      "--query-gpu=utilization.gpu",
      "--format=csv,noheader,nounits"
    ]);

    const v = stdout
      .trim()
      .split("\n")
      .map(Number)
      .filter(Number.isFinite);

    return v.length
      ? Number(
          (v.reduce((a, b) => a + b, 0) / v.length).toFixed(1)
        )
      : null;
  } catch {
    return null;
  }
}

function status() {
  return {
    online: true,
    systemStatus: "ONLINE",
    mode: "LIVE",
    source: "running-container",
    startedAt: startedAt.toISOString(),
    uptimeSeconds: Math.floor(process.uptime()),
    timestamp: new Date().toISOString()
  };
}

async function metrics() {
  const total = os.totalmem();
  const used = total - os.freemem();

  const [cpu, storage, gpu] = await Promise.all([
    cpuPercent(),
    storagePercent(),
    gpuPercent()
  ]);

  return {
    cpu,
    gpu,
    memory: total
      ? Number(((used / total) * 100).toFixed(1))
      : null,
    storage,
    temperatureC: null,
    source: "container",
    timestamp: new Date().toISOString()
  };
}

function deployment() {
  return {
    stage: "RUNNING",
    serviceId: process.env.RAILWAY_SERVICE_ID || null,
    deploymentId: process.env.RAILWAY_DEPLOYMENT_ID || null,
    environment: process.env.RAILWAY_ENVIRONMENT_NAME || null,
    source: "runtime-environment",
    timestamp: new Date().toISOString()
  };
}

function health() {
  return {
    ok: true,
    uptimeSeconds: Math.floor(process.uptime()),
    time: new Date().toISOString()
  };
}

async function jsonFetch(url, headers = {}) {
  const r = await fetch(url, {
    headers,
    signal: AbortSignal.timeout(10000)
  });

  if (!r.ok) {
    throw new Error(`Upstream returned HTTP ${r.status}`);
  }

  return r.json();
}

async function world(source, limit = 10) {
  if (!SOURCES[source]) {
    throw new Error("Unsupported world-event source");
  }

  const n = Math.max(
    1,
    Math.min(20, Number(limit) || 10)
  );

  const headers =
    source === "nws"
      ? {
          accept: "application/geo+json",
          "user-agent":
            "Eagle-Eyes-Live-Command-Center/1.0"
        }
      : {
          accept: "application/json"
        };

  const data = await jsonFetch(
    SOURCES[source],
    headers
  );

  let events;

  if (source === "usgs") {
    events = (data.features || [])
      .slice(0, n)
      .map((f) => ({
        id: f.id || null,
        title: f.properties?.title || null,
        magnitude: Number.isFinite(
          f.properties?.mag
        )
          ? f.properties.mag
          : null,
        place: f.properties?.place || null,
        time: Number.isFinite(
          f.properties?.time
        )
          ? new Date(
              f.properties.time
            ).toISOString()
          : null,
        url: f.properties?.url || null
      }));
  } else if (source === "eonet") {
    events = (data.events || [])
      .slice(0, n)
      .map((e) => ({
        id: e.id || null,
        title: e.title || null,
        categories: (e.categories || [])
          .map((x) => x.title)
          .filter(Boolean),
        time:
          e.geometry?.at(-1)?.date || null,
        link: e.link || null
      }));
  } else {
    events = (data.features || [])
      .slice(0, n)
      .map((f) => ({
        id: f.id || null,
        event:
          f.properties?.event || null,
        headline:
          f.properties?.headline || null,
        severity:
          f.properties?.severity || null,
        area:
          f.properties?.areaDesc || null,
        effective:
          f.properties?.effective || null,
        expires:
          f.properties?.expires || null,
        url:
          f.properties?.web ||
          f.properties?.uri ||
          null
      }));
  }

  return {
    ok: true,
    source,
    sourceUrl: SOURCES[source],
    simulated: false,
    count: events.length,
    events,
    timestamp: new Date().toISOString()
  };
}


function severityScore(severity) {
  const scores = {
    Extreme: 100,
    Severe: 85,
    Moderate: 65,
    Minor: 35,
    Unknown: 20
  };

  return scores[severity] || 20;
}

function metricPriority(name, value) {
  if (!Number.isFinite(value)) {
    return null;
  }

  if (value >= 90) {
    return {
      score: 95,
      level: "critical",
      source: "container",
      title: `${name}: ${value}%`
    };
  }

  if (value >= 80) {
    return {
      score: 75,
      level: "elevated",
      source: "container",
      title: `${name}: ${value}%`
    };
  }

  if (value >= 70) {
    return {
      score: 55,
      level: "watch",
      source: "container",
      title: `${name}: ${value}%`
    };
  }

  return null;
}

function areaParts(area) {
  return String(area || "")
    .split(";")
    .map((x) => x.trim())
    .filter(Boolean);
}

function summarizeAreas(areas, limit = 3) {
  const unique = [
    ...new Set(
      (areas || [])
        .flatMap((area) => areaParts(area))
    )
  ];

  if (!unique.length) {
    return "Area unavailable";
  }

  if (unique.length <= limit) {
    return unique.join("; ");
  }

  return (
    unique.slice(0, limit).join("; ") +
    ` +${unique.length - limit} more`
  );
}

function systemPressure(snapshot) {
  const metricsList = [
    ["CPU", snapshot.metrics?.cpu],
    ["Memory", snapshot.metrics?.memory],
    ["Storage", snapshot.metrics?.storage]
  ].filter(([, value]) => Number.isFinite(value));

  const highest = metricsList
    .slice()
    .sort((a, b) => b[1] - a[1])[0] || [null, null];

  let level = "nominal";
  let why =
    "Health and Railway are normal; measured CPU, memory, and storage are below the 70% watch threshold.";

  if (!snapshot.health?.ok) {
    level = "critical";
    why = "Command Center health check is not OK.";
  } else if (
    snapshot.deployment?.stage &&
    snapshot.deployment.stage !== "RUNNING"
  ) {
    level = "critical";
    why =
      `Railway deployment stage is ${snapshot.deployment.stage}, not RUNNING.`;
  } else if (Number.isFinite(highest[1]) && highest[1] >= 90) {
    level = "critical";
    why =
      `${highest[0]} is ${highest[1]}%, at or above the 90% critical threshold.`;
  } else if (Number.isFinite(highest[1]) && highest[1] >= 80) {
    level = "elevated";
    why =
      `${highest[0]} is ${highest[1]}%, at or above the 80% elevated threshold.`;
  } else if (Number.isFinite(highest[1]) && highest[1] >= 70) {
    level = "watch";
    why =
      `${highest[0]} is ${highest[1]}%, above the 70% watch threshold and below the 80% elevated threshold.`;
  }

  return {
    level,
    why,
    highestMetric:
      highest[0]
        ? {
            name: highest[0],
            value: highest[1]
          }
        : null,
    thresholds: {
      watch: 70,
      elevated: 80,
      critical: 90
    }
  };
}

function groupedNwsPriorities(events) {
  const groups = new Map();

  for (const event of events || []) {
    const baseScore =
      severityScore(event.severity);

    if (baseScore < 65) {
      continue;
    }

    const eventName =
      event.event || "Weather alert";

    const severity =
      event.severity || "Unknown";

    const key =
      `${eventName}|${severity}`;

    if (!groups.has(key)) {
      groups.set(key, {
        eventName,
        severity,
        baseScore,
        count: 0,
        areas: []
      });
    }

    const group =
      groups.get(key);

    group.count += 1;

    if (event.area) {
      group.areas.push(event.area);
    }
  }

  return [...groups.values()]
    .map((group) => {
      const score = Math.min(
        100,
        group.baseScore +
          Math.min(
            10,
            Math.max(0, group.count - 1) * 2
          )
      );

      return {
        score,
        level:
          score >= 95
            ? "critical"
            : score >= 85
              ? "high"
              : "elevated",
        source: "nws",
        title:
          group.count > 1
            ? `${group.eventName} (${group.count} related alerts)`
            : group.eventName,
        detail:
          `${group.severity} • ${summarizeAreas(group.areas)}`,
        why:
          group.count > 1
            ? `NWS severity is ${group.severity}; ${group.count} related active alerts are grouped here.`
            : `NWS severity is ${group.severity}.`
      };
    });
}

function snapshotPriorities(snapshot) {
  const items = [];

  items.push(
    ...groupedNwsPriorities(
      snapshot.feeds?.nws?.events || []
    )
  );

  for (const event of snapshot.feeds?.usgs?.events || []) {
    const magnitude = event.magnitude;

    if (!Number.isFinite(magnitude) || magnitude < 4) {
      continue;
    }

    const score =
      magnitude >= 6
        ? 95
        : magnitude >= 5
          ? 80
          : 65;

    items.push({
      score,
      level:
        score >= 95
          ? "critical"
          : score >= 80
            ? "high"
            : "elevated",
      source: "usgs",
      title:
        `Earthquake M${magnitude} • ${event.place || event.title || "location unavailable"}`,
      detail:
        event.time
          ? `Reported ${event.time}`
          : "Report time unavailable",
      why:
        `Magnitude ${magnitude} meets the M4+ operational monitoring threshold.`
    });
  }

  for (
    const event of
      (snapshot.feeds?.eonet?.events || []).slice(0, 5)
  ) {
    items.push({
      score: 40,
      level: "monitor",
      source: "eonet",
      title:
        event.title || "NASA EONET event",
      detail:
        Array.isArray(event.categories) &&
        event.categories.length
          ? event.categories.join(", ")
          : "Active natural event",
      why:
        "NASA EONET lists this as an active event; monitor for status or location changes."
    });
  }

  return items
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
}

function buildWatchNext(snapshot) {
  const watch = [];
  const priorities =
    snapshot.priorities || [];

  const topNws =
    priorities.find(
      (item) => item.source === "nws"
    );

  if (topNws) {
    watch.push(
      `NWS: watch ${topNws.title} for severity, area, and expiration changes.`
    );
  }

  const usgsEvents =
    snapshot.feeds?.usgs?.events || [];

  const strongestQuake =
    usgsEvents
      .filter((event) =>
        Number.isFinite(event.magnitude)
      )
      .sort(
        (a, b) =>
          b.magnitude - a.magnitude
      )[0];

  if (
    strongestQuake &&
    strongestQuake.magnitude >= 4
  ) {
    watch.push(
      `USGS: watch for magnitude/location updates or additional M4+ events; current strongest is M${strongestQuake.magnitude}.`
    );
  }

  const pressure =
    snapshot.systemPressure;

  if (
    pressure?.level &&
    pressure.level !== "nominal"
  ) {
    const highest =
      pressure.highestMetric;

    watch.push(
      highest
        ? `SYSTEM: ${highest.name} is ${highest.value}%; watch the 80% elevated and 90% critical thresholds.`
        : "SYSTEM: watch Command Center health and Railway deployment state."
    );
  } else {
    watch.push(
      "SYSTEM: no immediate infrastructure action; watch for Railway stage, health, or resource-threshold changes."
    );
  }

  if (
    watch.length < 3 &&
    (snapshot.feeds?.eonet?.count || 0) > 0
  ) {
    watch.push(
      "NASA EONET: monitor active events for new status or location changes."
    );
  }

  return watch.slice(0, 3);
}

function failedFeed(source, reason) {
  return {
    ok: false,
    source,
    simulated: false,
    count: 0,
    events: [],
    error:
      reason instanceof Error
        ? reason.message
        : String(reason || "unavailable"),
    timestamp: new Date().toISOString()
  };
}

async function operationalSnapshot(limit = 20) {
  const [
    metricResult,
    usgsResult,
    nwsResult,
    eonetResult
  ] = await Promise.allSettled([
    metrics(),
    world("usgs", limit),
    world("nws", limit),
    world("eonet", limit)
  ]);

  const snapshot = {
    ok: true,
    status: status(),
    health: health(),
    metrics:
      metricResult.status === "fulfilled"
        ? metricResult.value
        : {
            cpu: null,
            gpu: null,
            memory: null,
            storage: null,
            temperatureC: null,
            source: "container",
            error:
              metricResult.reason?.message ||
              "Metrics unavailable",
            timestamp: new Date().toISOString()
          },
    deployment: deployment(),
    feeds: {
      usgs:
        usgsResult.status === "fulfilled"
          ? usgsResult.value
          : failedFeed("usgs", usgsResult.reason),
      nws:
        nwsResult.status === "fulfilled"
          ? nwsResult.value
          : failedFeed("nws", nwsResult.reason),
      eonet:
        eonetResult.status === "fulfilled"
          ? eonetResult.value
          : failedFeed("eonet", eonetResult.reason)
    },
    simulated: false,
    timestamp: new Date().toISOString()
  };

  snapshot.systemPressure =
    systemPressure(snapshot);

  snapshot.priorities =
    snapshotPriorities(snapshot);

  snapshot.watchNext =
    buildWatchNext(snapshot);

  return snapshot;
}

function formatMissionBrief(snapshot) {
  const m = snapshot.metrics || {};
  const priorities =
    snapshot.priorities || [];
  const pressure =
    snapshot.systemPressure ||
    systemPressure(snapshot);
  const watchNext =
    snapshot.watchNext ||
    buildWatchNext(snapshot);

  const lines = [
    "EAGLE EYES EXECUTIVE MISSION BRIEF",
    "",
    `SYSTEM PRESSURE: [${String(pressure.level || "unknown").toUpperCase()}]`,
    `Command Center: ${snapshot.status?.systemStatus || "N/A"} • ${snapshot.status?.mode || "N/A"}`,
    `Railway: ${snapshot.deployment?.stage || "N/A"} • ${snapshot.deployment?.environment || "N/A"}`,
    `CPU ${pct(m.cpu)} • Memory ${pct(m.memory)} • Storage ${pct(m.storage)}`,
    `Why: ${pressure.why || "No pressure assessment available."}`,
    "",
    "TOP INCIDENTS:"
  ];

  if (priorities.length) {
    priorities.forEach((item, index) => {
      lines.push(
        `${index + 1}. [${String(item.level || "monitor").toUpperCase()}] ${item.source.toUpperCase()} • ${item.title}`
      );

      if (item.detail) {
        lines.push(
          `   ${item.detail}`
        );
      }

      if (item.why) {
        lines.push(
          `   Why: ${item.why}`
        );
      }
    });
  } else {
    lines.push(
      "No elevated external incident was detected in the current snapshot."
    );
  }

  lines.push(
    "",
    "WATCH NEXT:"
  );

  if (watchNext.length) {
    watchNext.forEach(
      (item, index) => {
        lines.push(
          `${index + 1}. ${item}`
        );
      }
    );
  } else {
    lines.push(
      "No specific watch item generated."
    );
  }

  const feedWarnings = Object.entries(
    snapshot.feeds || {}
  )
    .filter(([, feed]) => feed?.ok === false)
    .map(
      ([name, feed]) =>
        `${name.toUpperCase()}: ${feed.error || "unavailable"}`
    );

  lines.push(
    "",
    `COVERAGE: NWS ${snapshot.feeds?.nws?.count ?? 0} • USGS ${snapshot.feeds?.usgs?.count ?? 0} • NASA EONET ${snapshot.feeds?.eonet?.count ?? 0}`,
    "Simulation: OFF"
  );

  if (feedWarnings.length) {
    lines.push(
      `Feed warning: ${feedWarnings.join(" • ")}`
    );
  }

  lines.push(
    `Checked: ${snapshot.timestamp}`
  );

  return lines.join("\n");
}

function pct(value) {
  return Number.isFinite(value)
    ? `${value}%`
    : "N/A";
}

function compactEvent(event, source) {
  if (source === "usgs") {
    return [
      event.title || event.place || "Earthquake",
      Number.isFinite(event.magnitude)
        ? `M${event.magnitude}`
        : null,
      event.time || null
    ].filter(Boolean).join(" • ");
  }

  if (source === "nws") {
    return [
      event.event || "Weather alert",
      event.severity || null,
      event.area || null
    ].filter(Boolean).join(" • ");
  }

  return [
    event.title || "NASA EONET event",
    Array.isArray(event.categories) && event.categories.length
      ? event.categories.join(", ")
      : null,
    event.time || null
  ].filter(Boolean).join(" • ");
}

async function freeCommand(message) {
  const q = String(message || "")
    .trim()
    .toLowerCase();

  if (!q) {
    return null;
  }

  if (
    /\b(help|commands|what can you do|free mode)\b/.test(q)
  ) {
    return {
      handled: true,
      tool: "free_help",
      text: [
        "FREE COMMAND MODE IS ONLINE.",
        "",
        "Available without OpenAI credits:",
        "• health / system status",
        "• live metrics / CPU / memory / storage / GPU",
        "• Railway deployment status",
        "• Executive Mission Brief / grouped cross-feed priority snapshot",
        "• NWS weather alerts",
        "• USGS earthquakes",
        "• NASA EONET events",
        "• world data sources",
        "• world knowledge lookup (people, places, history, science, technology)",
        "• global current weather by city or place",
        "• World OS capability status",
        "",
        "These commands use live read-only data. GPT-5.6 commands will automatically become available when API billing is active."
      ].join("\n")
    };
  }

  if (
    /\b(mission brief|situation report|sitrep|operational snapshot|priority brief|prioritize incidents|what matters now)\b/.test(q)
  ) {
    const snapshot =
      await operationalSnapshot(20);

    return {
      handled: true,
      tool: "get_operational_snapshot",
      text:
        formatMissionBrief(snapshot)
    };
  }

  if (
    /\b(world os|world command|world command operating system|operating system|os status|capability|capabilities|modules)\b/.test(q)
  ) {
    const info =
      worldOSStatus();

    return {
      handled: true,
      tool: "get_world_os_status",
      text: [
        info.name,
        `Version: ${info.version}`,
        `Mode: ${info.mode}`,
        "",
        "ACTIVE MODULES:",
        ...info.modules.map(
          (item, index) =>
            `${index + 1}. ${item}`
        ),
        "",
        "FREE CAPABILITIES:",
        ...info.freeCapabilities.map(
          (item) =>
            `• ${item}`
        ),
        "",
        `Checked: ${info.timestamp}`
      ].join("\n")
    };
  }

  const weatherMatch =
    String(message || "").match(
      /\b(?:weather|temperature|forecast)\s+(?:in|for|at)\s+(.+?)\s*$/i
    );

  if (weatherMatch?.[1]) {
    try {
      const data =
        await globalWeather(
          weatherMatch[1]
        );

      return {
        handled: true,
        tool: "get_global_weather",
        text:
          formatWeather(data)
      };
    } catch (error) {
      return {
        handled: true,
        tool: "get_global_weather",
        text: [
          "GLOBAL WEATHER TEMPORARILY UNAVAILABLE",
          `Reason: ${error.message}`,
          "No simulated data was substituted."
        ].join("\n")
      };
    }
  }

  if (/\b(deployment|deploy|railway)\b/.test(q)) {
    const d = deployment();

    return {
      handled: true,
      tool: "get_deployment_status",
      text: [
        "RAILWAY DEPLOYMENT",
        `Stage: ${d.stage || "N/A"}`,
        `Environment: ${d.environment || "N/A"}`,
        `Service ID: ${d.serviceId || "N/A"}`,
        `Deployment ID: ${d.deploymentId || "N/A"}`,
        `Source: ${d.source}`,
        `Checked: ${d.timestamp}`
      ].join("\n")
    };
  }

  if (
    /\b(metric|metrics|cpu|memory|storage|gpu|temperature|container)\b/.test(q)
  ) {
    const m = await metrics();

    return {
      handled: true,
      tool: "get_command_center_metrics",
      text: [
        "LIVE CONTAINER METRICS",
        `CPU: ${pct(m.cpu)}`,
        `Memory: ${pct(m.memory)}`,
        `Storage: ${pct(m.storage)}`,
        `GPU: ${pct(m.gpu)}`,
        `Temperature: ${Number.isFinite(m.temperatureC) ? `${m.temperatureC}°C` : "N/A"}`,
        `Source: ${m.source}`,
        `Checked: ${m.timestamp}`
      ].join("\n")
    };
  }

  if (
    /\b(source|sources|world data|feeds)\b/.test(q)
  ) {
    return {
      handled: true,
      tool: "get_world_sources",
      text: [
        "LIVE WORLD DATA SOURCES",
        `USGS: ${SOURCES.usgs}`,
        `NASA EONET: ${SOURCES.eonet}`,
        `NOAA / NWS: ${SOURCES.nws}`,
        "Simulation: OFF"
      ].join("\n")
    };
  }

  const worldSource =
    /\b(usgs|earthquake|earthquakes|quake|quakes)\b/.test(q)
      ? "usgs"
      : /\b(nws|noaa|weather|alert|alerts|storm|storms)\b/.test(q)
        ? "nws"
        : /\b(nasa|eonet|wildfire|wildfires|natural event|natural events)\b/.test(q)
          ? "eonet"
          : null;

  if (worldSource) {
    try {
      const data = await world(worldSource, 5);
      const labels = {
        usgs: "USGS EARTHQUAKES",
        nws: "NOAA / NWS ALERTS",
        eonet: "NASA EONET EVENTS"
      };

      const lines = (data.events || []).map(
        (event, index) =>
          `${index + 1}. ${compactEvent(event, worldSource)}`
      );

      return {
        handled: true,
        tool: `get_world_events:${worldSource}`,
        text: [
          labels[worldSource],
          `Live results: ${data.count}`,
          ...(lines.length ? lines : ["No active events returned."]),
          `Checked: ${data.timestamp}`
        ].join("\n")
      };
    } catch (error) {
      return {
        handled: true,
        tool: `get_world_events:${worldSource}`,
        text: [
          "LIVE SOURCE TEMPORARILY UNAVAILABLE",
          `Source: ${worldSource.toUpperCase()}`,
          `Reason: ${error.message}`,
          "No simulated data was substituted."
        ].join("\n")
      };
    }
  }

  if (
    /\b(health|healthy|status|online|uptime|system)\b/.test(q)
  ) {
    const s = status();
    const h = health();

    return {
      handled: true,
      tool: "get_system_health",
      text: [
        "COMMAND CENTER HEALTH",
        `System: ${s.systemStatus}`,
        `Online: ${s.online ? "YES" : "NO"}`,
        `Mode: ${s.mode}`,
        `Uptime: ${h.uptimeSeconds} seconds`,
        `Source: ${s.source}`,
        `Checked: ${h.time}`
      ].join("\n")
    };
  }

  if (
    shouldUseFreeKnowledge(
      message,
      Boolean(OPENAI_API_KEY)
    )
  ) {
    const knowledgeQuery =
      String(message || "")
        .replace(
          /^\s*(?:world knowledge|wikipedia|encyclopedia)\s*[:-]?\s*/i,
          ""
        )
        .trim() ||
      message;

    try {
      const data =
        await knowledgeSearch(
          knowledgeQuery,
          3
        );

      return {
        handled: true,
        tool: "search_world_knowledge",
        text:
          formatKnowledge(data)
      };
    } catch (error) {
      return {
        handled: true,
        tool: "search_world_knowledge",
        text: [
          "EAGLE EYES FREE KNOWLEDGE MODE",
          "I could not resolve that request from the current free knowledge source.",
          `Reason: ${error.message}`,
          "Try a more specific person, place, organization, event, science, history, or technology question."
        ].join("\n")
      };
    }
  }

  return null;
}

async function runTool(call) {
  const args = call.arguments
    ? JSON.parse(call.arguments)
    : {};

  switch (call.name) {
    case "get_command_center_status":
      return status();

    case "get_command_center_metrics":
      return metrics();

    case "get_deployment_status":
      return deployment();

    case "get_system_health":
      return health();

    case "get_operational_snapshot":
      return operationalSnapshot(20);

    case "get_world_events":
      return world(
        args.source,
        args.limit
      );

    case "search_world_knowledge":
      return knowledgeSearch(
        args.query,
        args.limit
      );

    case "get_global_weather":
      return globalWeather(
        args.location
      );

    case "get_world_os_status":
      return worldOSStatus();

    default:
      throw new Error(
        `Unknown tool: ${call.name}`
      );
  }
}

const callsFrom = (r) =>
  (r?.output || []).filter(
    (x) =>
      x?.type === "function_call"
  );

function textFrom(r) {
  const out = [];

  for (const item of r?.output || []) {
    const parts =
      item?.type === "message" &&
      Array.isArray(item.content)
        ? item.content
        : [];

    for (const p of parts) {
      if (
        p?.type === "output_text" &&
        typeof p.text === "string"
      ) {
        out.push(p.text);
      }
    }
  }

  return out.join("");
}

async function openAI(
  body,
  signal,
  stream = false
) {
  if (!OPENAI_API_KEY) {
    const e = new Error(
      "OPENAI_API_KEY is not configured"
    );

    e.statusCode = 503;

    throw e;
  }

  const r = await fetch(OPENAI_URL, {
    method: "POST",

    headers: {
      authorization:
        `Bearer ${OPENAI_API_KEY}`,

      "content-type":
        "application/json",

      ...(stream
        ? {
            accept:
              "text/event-stream"
          }
        : {})
    },

    body: JSON.stringify({
      ...body,
      ...(stream
        ? {
            stream: true
          }
        : {})
    }),

    signal
  });

  if (!r.ok) {
    const raw = await r.text();

    let msg = raw;

    try {
      msg =
        JSON.parse(raw)?.error?.message ||
        raw;
    } catch {}

    const e = new Error(
      msg ||
        `OpenAI returned HTTP ${r.status}`
    );

    e.statusCode = 502;

    throw e;
  }

  return r;
}

async function assistant(
  message,
  signal
) {
  let input = [
    {
      role: "user",

      content: [
        {
          type: "input_text",
          text: message
        }
      ]
    }
  ];

  for (
    let step = 0;
    step < 6;
    step++
  ) {
    const r = await openAI(
      {
        model: OPENAI_MODEL,
        instructions: INSTRUCTIONS,
        input,
        tools: TOOLS,
        tool_choice: "auto",
        store: false
      },
      signal
    );

    const response = await r.json();

    const calls =
      callsFrom(response);

    if (!calls.length) {
      return {
        responseId:
          response.id || null,

        model:
          response.model ||
          OPENAI_MODEL,

        text:
          textFrom(response)
      };
    }

    input.push(
      ...response.output
    );

    for (const call of calls) {
      try {
        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output: JSON.stringify({
            ok: true,

            result:
              await runTool(call)
          })
        });
      } catch (e) {
        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output: JSON.stringify({
            ok: false,
            error: e.message
          })
        });
      }
    }
  }

  throw new Error(
    "Eagle Eyes exceeded the tool-call step limit"
  );
}

function sendSSE(
  res,
  event,
  data
) {
  res.write(
    `event: ${event}\n` +
      `data: ${JSON.stringify(data)}\n\n`
  );
}

async function streamedResponse(
  body,
  signal,
  onEvent
) {
  const r = await openAI(
    body,
    signal,
    true
  );

  if (!r.body) {
    throw new Error(
      "OpenAI stream returned no body"
    );
  }

  const reader =
    r.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer = "";
  let completed = null;

  while (true) {
    const {
      value,
      done
    } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(
      value,
      {
        stream: true
      }
    );

    buffer =
      buffer.replace(
        /\r\n/g,
        "\n"
      );

    let i;

    while (
      (i =
        buffer.indexOf(
          "\n\n"
        )) !== -1
    ) {
      const block =
        buffer.slice(
          0,
          i
        );

      buffer =
        buffer.slice(
          i + 2
        );

      const payload =
        block
          .split("\n")
          .filter(
            (x) =>
              x.startsWith(
                "data:"
              )
          )
          .map((x) =>
            x
              .slice(5)
              .trimStart()
          )
          .join("\n");

      if (
        !payload ||
        payload === "[DONE]"
      ) {
        continue;
      }

      let event;

      try {
        event =
          JSON.parse(
            payload
          );
      } catch {
        continue;
      }

      if (
  event.type ===
  "response.failed"
) {
  throw new Error(
    event.response?.error?.message ||
      event.response?.error?.code ||
      "OpenAI response failed"
  );
}

if (
  event.type ===
  "response.incomplete"
) {
  const reason =
    event.response?.incomplete_details?.reason ||
    "unknown reason";

  throw new Error(
    `OpenAI response incomplete: ${reason}`
  );
}

if (
  event.type ===
  "error"
) {
  throw new Error(
    event.message ||
      event.error?.message ||
      event.error?.code ||
      "OpenAI streaming error"
  );
}

if (
  event.type ===
  "response.completed"
) {
  completed =
    event.response;
}

await onEvent(event);
    }
  }

  if (!completed) {
    throw new Error(
      "OpenAI stream ended before response.completed"
    );
  }

  return completed;
}

async function assistantStream(
  message,
  res,
  signal
) {
  let input = [
    {
      role: "user",

      content: [
        {
          type: "input_text",
          text: message
        }
      ]
    }
  ];

  for (
    let step = 0;
    step < 6;
    step++
  ) {
    const completed =
      await streamedResponse(
        {
          model:
            OPENAI_MODEL,

          instructions:
            INSTRUCTIONS,

          input,

          tools:
            TOOLS,

          tool_choice:
            "auto",

          store:
            false
        },

        signal,

        async (event) => {
          if (
            event.type ===
              "response.output_text.delta" &&
            typeof event.delta ===
              "string"
          ) {
            sendSSE(
              res,
              "delta",
              {
                text:
                  event.delta
              }
            );
          }

          if (
            event.type ===
            "response.function_call_arguments.done"
          ) {
            sendSSE(
              res,
              "tool_call",
              {
                name:
                  event.name
              }
            );
          }
        }
      );

    const calls =
      callsFrom(completed);

    if (!calls.length) {
      sendSSE(
        res,
        "done",
        {
          responseId:
            completed.id ||
            null,

          model:
            completed.model ||
            OPENAI_MODEL
        }
      );

      return;
    }

    input.push(
      ...completed.output
    );

    for (const call of calls) {
      try {
        const result =
          await runTool(
            call
          );

        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output:
            JSON.stringify({
              ok: true,
              result
            })
        });

        sendSSE(
          res,
          "tool_result",
          {
            name:
              call.name,

            ok: true
          }
        );
      } catch (e) {
        input.push({
          type:
            "function_call_output",

          call_id:
            call.call_id,

          output:
            JSON.stringify({
              ok: false,
              error:
                e.message
            })
        });

        sendSSE(
          res,
          "tool_result",
          {
            name:
              call.name,

            ok: false
          }
        );
      }
    }
  }

  throw new Error(
    "Eagle Eyes exceeded the tool-call step limit"
  );
}

app.get(
  "/api/status",
  (_req, res) =>
    res.json(status())
);

app.get(
  "/api/metrics",
  async (_req, res, next) => {
    try {
      res.json(
        await metrics()
      );
    } catch (e) {
      next(e);
    }
  }
);

app.get(
  "/api/workloads",
  (_req, res) =>
    res.json([])
);

app.get(
  "/api/deployment",
  (_req, res) =>
    res.json(
      deployment()
    )
);

app.get(
  "/api/health",
  (_req, res) =>
    res.json(
      health()
    )
);

app.get(
  "/api/eagle-eyes/sources",
  (_req, res) =>
    res.json({
      ok: true,
      simulated: false,
      sources:
        Object.keys(
          SOURCES
        ),
      urls:
        SOURCES,
      timestamp:
        new Date().toISOString()
    })
);

app.get(
  "/api/eagle-eyes/events",
  async (req, res) => {
    try {
      res.json(
        await world(
          String(
            req.query.source ||
              ""
          ).toLowerCase(),

          Number(
            req.query.limit ||
              10
          )
        )
      );
    } catch (e) {
      res.status(502).json({
        ok: false,
        error:
          e.message,
        timestamp:
          new Date().toISOString()
      });
    }
  }
);

app.get(
  "/api/eagle-eyes/snapshot",
  requireAssistantAccess,
  async (_req, res) => {
    try {
      res.json(
        await operationalSnapshot(20)
      );
    } catch (e) {
      res.status(502).json({
        ok: false,
        error: e.message,
        timestamp:
          new Date().toISOString()
      });
    }
  }
);

app.get(
  "/api/eagle-eyes/world-os",
  requireAssistantAccess,
  (_req, res) =>
    res.json(
      worldOSStatus()
    )
);

app.get(
  "/api/eagle-eyes/knowledge",
  requireAssistantAccess,
  async (req, res) => {
    try {
      const query =
        String(
          req.query.q || ""
        ).trim();

      if (!query) {
        return res
          .status(400)
          .json({
            ok: false,
            error: "q is required"
          });
      }

      return res.json(
        await knowledgeSearch(
          query,
          Number(
            req.query.limit || 3
          )
        )
      );
    } catch (e) {
      return res
        .status(502)
        .json({
          ok: false,
          error: e.message,
          simulated: false,
          timestamp:
            new Date().toISOString()
        });
    }
  }
);

app.get(
  "/api/eagle-eyes/weather",
  requireAssistantAccess,
  async (req, res) => {
    try {
      const location =
        String(
          req.query.location || ""
        ).trim();

      if (!location) {
        return res
          .status(400)
          .json({
            ok: false,
            error:
              "location is required"
          });
      }

      return res.json(
        await globalWeather(
          location
        )
      );
    } catch (e) {
      return res
        .status(502)
        .json({
          ok: false,
          error: e.message,
          simulated: false,
          timestamp:
            new Date().toISOString()
        });
    }
  }
);

app.get(
  "/api/assistant/status",
  (_req, res) =>
    res.json({
      ok: true,

      configured:
        Boolean(
          OPENAI_API_KEY
        ),

      freeMode:
        true,

      worldOS:
        true,

      freeKnowledge:
        "Wikipedia",

      globalWeather:
        "Open-Meteo",

      commandMode:
        OPENAI_API_KEY
          ? "AI+FREE"
          : "FREE",

      accessProtected:
        true,

      accessConfigured:
        Boolean(
          COMMAND_CENTER_ACCESS_TOKEN
        ),

      model:
        OPENAI_MODEL,

      transport:
        "responses-api-sse",

      readOnlyTools:
        TOOLS.map(
          (t) =>
            t.name
        ),

      timestamp:
        new Date().toISOString()
    })
);

app.get(
  "/api/assistant/auth-check",
  requireAssistantAccess,
  (_req, res) =>
    res.json({
      ok: true,
      authorized: true,
      timestamp:
        new Date().toISOString()
    })
);

app.post(
  "/api/assistant",
  requireAssistantAccess,
  async (req, res) => {
    const message =
      typeof req.body?.message ===
      "string"
        ? req.body.message.trim()
        : "";

    if (!message) {
      return res
        .status(400)
        .json({
          ok: false,
          error:
            "message is required"
        });
    }

    if (
      message.length >
      12000
    ) {
      return res
        .status(413)
        .json({
          ok: false,
          error:
            "message is too large"
        });
    }

    try {
      const local =
        await freeCommand(
          message
        );

      if (local) {
        return res.json({
          ok: true,
          mode:
            "free",
          model:
            "free-command-mode",
          tool:
            local.tool,
          text:
            local.text
        });
      }

      if (
        !OPENAI_API_KEY
      ) {
        return res
          .status(503)
          .json({
            ok: false,
            mode:
              "free",
            error:
              "GPT-5.6 is temporarily unavailable. Free commands remain available: mission brief, health, live metrics, deployment, NWS alerts, USGS earthquakes, NASA EONET, global weather, world knowledge, World OS status, or help."
          });
      }

      return res.json({
        ok: true,

        ...(await assistant(
          message
        ))
      });
    } catch (e) {
      return res
        .status(
          e.statusCode ||
            502
        )
        .json({
          ok: false,
          error:
            e.message
        });
    }
  }
);

app.post(
  "/api/assistant/stream",
  requireAssistantAccess,
  async (req, res) => {
    const message =
      typeof req.body?.message ===
      "string"
        ? req.body.message.trim()
        : "";

    if (!message) {
      return res
        .status(400)
        .json({
          ok: false,
          error:
            "message is required"
        });
    }

    if (
      message.length >
      12000
    ) {
      return res
        .status(413)
        .json({
          ok: false,
          error:
            "message is too large"
        });
    }

    const local =
      await freeCommand(
        message
      );

    if (local) {
      res
        .status(200)
        .set({
          "content-type":
            "text/event-stream; charset=utf-8",

          "cache-control":
            "no-cache, no-transform",

          connection:
            "keep-alive",

          "x-accel-buffering":
            "no"
        });

      res.flushHeaders();

      sendSSE(
        res,
        "ready",
        {
          model:
            "free-command-mode",
          mode:
            "free"
        }
      );

      sendSSE(
        res,
        "tool_call",
        {
          name:
            local.tool
        }
      );

      sendSSE(
        res,
        "delta",
        {
          text:
            local.text
        }
      );

      sendSSE(
        res,
        "tool_result",
        {
          name:
            local.tool,
          ok:
            true
        }
      );

      sendSSE(
        res,
        "done",
        {
          model:
            "free-command-mode",
          mode:
            "free"
        }
      );

      return res.end();
    }

    if (
      !OPENAI_API_KEY
    ) {
      res
        .status(200)
        .set({
          "content-type":
            "text/event-stream; charset=utf-8",

          "cache-control":
            "no-cache, no-transform",

          connection:
            "keep-alive",

          "x-accel-buffering":
            "no"
        });

      res.flushHeaders();

      sendSSE(
        res,
        "ready",
        {
          model:
            "free-command-mode",
          mode:
            "free"
        }
      );

      sendSSE(
        res,
        "delta",
        {
          text: [
            "GPT-5.6 is temporarily unavailable because API billing is not active.",
            "",
            "FREE COMMAND MODE is still online. Try: mission brief, health, live metrics, deployment, NWS alerts, USGS earthquakes, NASA EONET, weather in a city, a factual world-knowledge question, World OS status, or help."
          ].join("\n")
        }
      );

      sendSSE(
        res,
        "done",
        {
          model:
            "free-command-mode",
          mode:
            "free"
        }
      );

      return res.end();
    }

    res
      .status(200)
      .set({
        "content-type":
          "text/event-stream; charset=utf-8",

        "cache-control":
          "no-cache, no-transform",

        connection:
          "keep-alive",

        "x-accel-buffering":
          "no"
      });

    res.flushHeaders();

    const controller =
      new AbortController();

    res.on(
      "close",
      () =>
        controller.abort()
    );

    sendSSE(
      res,
      "ready",
      {
        model:
          OPENAI_MODEL
      }
    );

    try {
      await assistantStream(
        message,
        res,
        controller.signal
      );
    } catch (e) {
      if (
        !controller
          .signal
          .aborted
      ) {
        sendSSE(
          res,
          "error",
          {
            message:
              e.message
          }
        );
      }
    } finally {
      if (
        !res.writableEnded
      ) {
        res.end();
      }
    }
  }
);

app.get(
  "/api/dedalus/health",
  async (_req, res) => {
    const key =
      process.env
        .DEDALUS_API_KEY;

    if (!key) {
      return res
        .status(503)
        .json({
          ok: false,
          service:
            "dedalus",
          error:
            "DEDALUS_API_KEY is not configured"
        });
    }

    try {
      const r =
        await fetch(
          "https://api.dedaluslabs.ai/v1/models",
          {
            headers: {
              Authorization:
                `Bearer ${key}`
            },

            signal:
              AbortSignal.timeout(
                10000
              )
          }
        );

      if (!r.ok) {
        return res
          .status(502)
          .json({
            ok: false,
            service:
              "dedalus",
            error:
              `Dedalus returned HTTP ${r.status}`
          });
      }

      return res.json({
        ok: true,
        service:
          "dedalus",
        connected:
          true,
        timestamp:
          new Date().toISOString()
      });
    } catch {
      return res
        .status(502)
        .json({
          ok: false,
          service:
            "dedalus",
          error:
            "Dedalus connection failed"
        });
    }
  }
);

app.use(
  (
    err,
    _req,
    res,
    _next
  ) => {
    console.error(err);

    res
      .status(500)
      .json({
        ok: false,
        error:
          "Internal server error"
      });
  }
);

app.listen(
  PORT,
  "0.0.0.0",
  () =>
    console.log(
      `Command Center listening on port ${PORT}`
    )
);
