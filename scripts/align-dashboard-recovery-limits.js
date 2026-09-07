"use strict";

const fs = require("node:fs");
const path = require("node:path");

const dashboardPath = path.join(__dirname, "..", "public", "index.html");
let dashboard = fs.readFileSync(dashboardPath, "utf8");

const replacements = [
  ["/api/eagle-eyes/events?source=nws&limit=12", "/api/eagle-eyes/events?source=nws&limit=50"],
  ["/api/eagle-eyes/events?source=usgs&limit=12", "/api/eagle-eyes/events?source=usgs&limit=50"],
  ["/api/eagle-eyes/events?source=eonet&limit=12", "/api/eagle-eyes/events?source=eonet&limit=50"],
  ["/api/eagle-eyes/satellites?limit=30", "/api/eagle-eyes/satellites?limit=120"]
];

for (const [from, to] of replacements) {
  if (dashboard.includes(to)) continue;
  if (!dashboard.includes(from)) {
    throw new Error(`Dashboard recovery alignment refused: anchor not found: ${from}`);
  }
  dashboard = dashboard.replace(from, to);
}

for (const [, expected] of replacements) {
  if (!dashboard.includes(expected)) {
    throw new Error(`Dashboard recovery alignment failed: ${expected}`);
  }
}

fs.writeFileSync(dashboardPath, dashboard, "utf8");
console.log("Eagle Eyes dashboard recovery limits aligned: NWS/USGS/EONET=50, satellites=120.");
