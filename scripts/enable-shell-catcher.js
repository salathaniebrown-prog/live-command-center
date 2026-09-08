"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.join(__dirname, "..");
const serverPath = path.join(root, "server.js");
const modulePath = path.join(root, "shell-catcher.js");
const original = fs.readFileSync(serverPath, "utf8");
let next = original;

const importMarker = 'const { registerShellCatcher } = require("./shell-catcher");';
if (!next.includes(importMarker)) {
  const anchor = 'const { registerLeadIntake } = require("./lead-intake-preload");';
  if (!next.includes(anchor)) {
    throw new Error("Shell Catcher patch refused: lead-intake import anchor not found");
  }
  next = next.replace(anchor, `${anchor}\n${importMarker}`);
}

const registrationMarker = "registerShellCatcher(app, { readGuard: requireAssistantAccess });";
if (!next.includes(registrationMarker)) {
  const anchor = "registerLeadIntake(app);";
  if (!next.includes(anchor)) {
    throw new Error("Shell Catcher patch refused: lead-intake registration anchor not found");
  }
  next = next.replace(anchor, `${anchor}\n${registrationMarker}`);
}

fs.writeFileSync(serverPath, next, "utf8");

const checks = [
  [serverPath, spawnSync(process.execPath, ["--check", serverPath], { encoding: "utf8" })],
  [modulePath, spawnSync(process.execPath, ["--check", modulePath], { encoding: "utf8" })]
];
const failed = checks.find(([, result]) => result.status !== 0);

if (failed) {
  fs.writeFileSync(serverPath, original, "utf8");
  console.error("Shell Catcher integration failed; original server.js restored.");
  console.error(failed[1].stderr || failed[1].stdout || "Unknown syntax error");
  process.exit(1);
}

if (next === original) {
  console.log("Eagle Eyes Shell Catcher already enabled.");
} else {
  console.log("Eagle Eyes Shell Catcher enabled and syntax validated.");
}
