"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.join(__dirname, "..");
const targets = {
  server: path.join(root, "server.js"),
  satellites: path.join(root, "satellites.js"),
  dashboard: path.join(root, "public", "index.html")
};

const originals = Object.fromEntries(
  Object.entries(targets).map(([key, file]) => [
    key,
    fs.readFileSync(file, "utf8")
  ])
);

const next = { ...originals };

function replaceExact(key, from, to, label) {
  if (next[key].includes(to)) return;
  if (!next[key].includes(from)) {
    throw new Error(`Full-live-data patch refused: ${label} anchor not found`);
  }
  next[key] = next[key].replace(from, to);
}

// Backend: keep a generous safety ceiling while allowing the complete current
// CelesTrak WEATHER catalog to flow through when it is below that ceiling.
replaceExact(
  "satellites",
  "const MAX_SATELLITES = 30;",
  "const MAX_SATELLITES = 512;",
  "satellite backend ceiling"
);

// GPT tools: let Eagle Eyes reason across substantially larger live datasets.
replaceExact(
  "server",
  '"Get up to 30 real weather-satellite positions propagated from current CelesTrak NORAD GP orbital elements. Never simulate missing orbital data.",',
  '"Get current real weather-satellite positions propagated from CelesTrak NORAD GP orbital elements. The backend supports the full current WEATHER catalog up to its safety ceiling. Never simulate missing orbital data.",',
  "satellite tool description"
);
replaceExact(
  "server",
  "          maximum: 30",
  "          maximum: 512",
  "satellite tool limit"
);
replaceExact(
  "server",
  "          maximum: 20",
  "          maximum: 250",
  "world-event tool limit"
);
replaceExact(
  "server",
  "    Math.min(20, Number(limit) || 10)",
  "    Math.min(250, Number(limit) || 10)",
  "world-event backend limit"
);

// Dashboard: support both the original V2 static source URLs and the Chronicle
// Lab V13 dynamic source router. Both must request the same recovered live-data
// sample size; unavailable upstream data is never simulated.
const chronicleDynamicWorldLimit =
  next.dashboard.includes(
    "const url='/api/eagle-eyes/events?source='+src+'&limit=50';"
  );

if (!chronicleDynamicWorldLimit) {
  for (const source of ["nws", "usgs", "eonet"]) {
    replaceExact(
      "dashboard",
      `/api/eagle-eyes/events?source=${source}&limit=12`,
      `/api/eagle-eyes/events?source=${source}&limit=50`,
      `${source} dashboard sample limit`
    );
  }
}

replaceExact(
  "dashboard",
  "/api/eagle-eyes/satellites?limit=30",
  "/api/eagle-eyes/satellites?limit=120",
  "satellite dashboard sample limit"
);

const changed = Object.keys(next).filter((key) => next[key] !== originals[key]);

for (const key of changed) {
  fs.writeFileSync(targets[key], next[key], "utf8");
}

function syntaxCheck(file) {
  return spawnSync(process.execPath, ["--check", file], {
    encoding: "utf8"
  });
}

const checks = [
  [targets.server, syntaxCheck(targets.server)],
  [targets.satellites, syntaxCheck(targets.satellites)]
];

const failed = checks.find(([, result]) => result.status !== 0);
const staticWorldLimits =
  next.dashboard.includes("source=nws&limit=50") &&
  next.dashboard.includes("source=usgs&limit=50") &&
  next.dashboard.includes("source=eonet&limit=50");
const dynamicWorldLimits =
  next.dashboard.includes(
    "const url='/api/eagle-eyes/events?source='+src+'&limit=50';"
  );
const dashboardOk =
  (staticWorldLimits || dynamicWorldLimits) &&
  next.dashboard.includes("satellites?limit=120");

if (failed || !dashboardOk) {
  for (const key of changed) {
    fs.writeFileSync(targets[key], originals[key], "utf8");
  }
  console.error("Full live-data validation failed; original files restored.");
  if (failed) {
    console.error(failed[1].stderr || failed[1].stdout || "Unknown syntax error");
  }
  if (!dashboardOk) {
    console.error("Dashboard live-data markers were not applied as expected.");
  }
  process.exit(1);
}

if (!changed.length) {
  console.log("Eagle Eyes full live-data limits already enabled and validated.");
  process.exit(0);
}

console.log(
  "Eagle Eyes full live-data limits enabled: AI world events up to 250, satellites up to 512, dashboard samples 50/50/50 + 120 satellites."
);
