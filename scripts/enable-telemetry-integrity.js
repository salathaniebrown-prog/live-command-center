"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.join(__dirname, "..");
const serverPath = path.join(root, "server.js");
const dashboardPath = path.join(root, "public", "index.html");
const uiScriptPath = path.join(root, "public", "secure-telemetry-status.js");

const originalServer = fs.readFileSync(serverPath, "utf8");
const originalDashboard = fs.readFileSync(dashboardPath, "utf8");
let server = originalServer;
let dashboard = originalDashboard;

const px4Require = [
  "const {",
  "  Px4TelemetryStore,",
  "  formatPx4Telemetry",
  '} = require("./px4-telemetry");'
].join("\n");

const integrityRequire =
  'const { getTelemetryIntegrity } = require("./telemetry-integrity");';

if (!server.includes(integrityRequire)) {
  if (!server.includes(px4Require)) {
    throw new Error("Telemetry integrity patch refused: PX4 require anchor not found");
  }
  server = server.replace(
    px4Require,
    `${px4Require}\n${integrityRequire}`
  );
}

const routeMarker = '"/api/eagle-eyes/telemetry-integrity"';
if (!server.includes(routeMarker)) {
  const px4Route = 'app.get(\n  "/api/eagle-eyes/px4",';
  if (!server.includes(px4Route)) {
    throw new Error("Telemetry integrity patch refused: PX4 route anchor not found");
  }

  const route = [
    "app.get(",
    '  "/api/eagle-eyes/telemetry-integrity",',
    "  async (_req, res) => {",
    '    res.set("cache-control", "no-store");',
    "    res.json(await getTelemetryIntegrity());",
    "  }",
    ");",
    "",
  ].join("\n");

  server = server.replace(px4Route, route + px4Route);
}

const scriptTag = '<script src="/secure-telemetry-status.js"></script>';
if (!dashboard.includes(scriptTag)) {
  if (!dashboard.includes("CHRONICLE LAB")) {
    throw new Error("Telemetry integrity UI patch refused: Chronicle Lab baseline missing");
  }
  if (!dashboard.includes("</body>")) {
    throw new Error("Telemetry integrity UI patch refused: body closing tag missing");
  }
  dashboard = dashboard.replace("</body>", `${scriptTag}\n</body>`);
}

fs.writeFileSync(serverPath, server, "utf8");
fs.writeFileSync(dashboardPath, dashboard, "utf8");

const checks = [
  [serverPath, spawnSync(process.execPath, ["--check", serverPath], { encoding: "utf8" })],
  [uiScriptPath, spawnSync(process.execPath, ["--check", uiScriptPath], { encoding: "utf8" })]
];
const failed = checks.find(([, result]) => result.status !== 0);

const markersOk =
  server.includes(integrityRequire) &&
  server.includes(routeMarker) &&
  dashboard.includes(scriptTag) &&
  dashboard.includes("CHRONICLE LAB");

if (failed || !markersOk) {
  fs.writeFileSync(serverPath, originalServer, "utf8");
  fs.writeFileSync(dashboardPath, originalDashboard, "utf8");
  console.error("Telemetry integrity integration failed; original files restored.");
  if (failed) {
    console.error(failed[1].stderr || failed[1].stdout || "Unknown syntax error");
  }
  process.exit(1);
}

if (server === originalServer && dashboard === originalDashboard) {
  console.log("Chronicle secure telemetry integrity integration already enabled.");
} else {
  console.log("Chronicle secure telemetry integrity route + UI enabled and validated.");
}
