"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const required = [
  "public/index.html",
  "public/chat.html",
  "public/tri-chat.html",
  "public/tri-chat.js",
  "render.yaml"
];

for (const relative of required) {
  const absolute = path.join(root, relative);
  if (!fs.existsSync(absolute)) {
    throw new Error(`Global static artifact missing: ${relative}`);
  }
}

const triHtml = fs.readFileSync(path.join(root, "public/tri-chat.html"), "utf8");
const triJs = fs.readFileSync(path.join(root, "public/tri-chat.js"), "utf8");
const blueprint = fs.readFileSync(path.join(root, "render.yaml"), "utf8");

execFileSync(process.execPath, ["--check", path.join(root, "public/tri-chat.js")], { stdio: "pipe" });

if (/OPENAI_API_KEY\s*=/.test(triHtml + triJs)) {
  throw new Error("Client bundle must not contain an OpenAI API key assignment");
}

if (/localStorage|sessionStorage/.test(triJs)) {
  throw new Error("Global chat must not persist the Command Center token in browser storage");
}

for (const marker of ["PASS 1 OF 3", "PASS 2 OF 3", "PASS 3 OF 3"]) {
  if (!triJs.includes(marker)) throw new Error(`Triple Consensus marker missing: ${marker}`);
}

if (!blueprint.includes("runtime: static") || !blueprint.includes("staticPublishPath: public")) {
  throw new Error("Render blueprint is not configured as a global static site");
}

if (!blueprint.includes("source: /api/*") || !blueprint.includes("live-command-center-deployment.onrender.com/api/*")) {
  throw new Error("Render blueprint is missing the protected API rewrite");
}

console.log(JSON.stringify({
  ok: true,
  globalFrontend: "render-static-cdn",
  protectedApi: "live-command-center-deployment.onrender.com",
  aiMode: "triple-consensus-3-pass",
  browserSecretPersistence: false
}, null, 2));
