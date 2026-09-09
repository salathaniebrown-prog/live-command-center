"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const triHtmlPath = path.join(root, "public", "tri-chat.html");
const triJsPath = path.join(root, "public", "tri-chat.js");
const blueprintPath = path.join(root, "render.yaml");

test("global Render edge keeps API server-side and Triple Consensus bounded", () => {
  const output = execFileSync(process.execPath, [path.join(root, "scripts", "verify-global-static.js")], {
    cwd: root,
    encoding: "utf8"
  });
  const report = JSON.parse(output);
  assert.equal(report.ok, true);
  assert.equal(report.globalFrontend, "render-static-cdn");
  assert.equal(report.browserSecretPersistence, false);

  const html = fs.readFileSync(triHtmlPath, "utf8");
  const js = fs.readFileSync(triJsPath, "utf8");
  const blueprint = fs.readFileSync(blueprintPath, "utf8");

  assert.match(html, /Triple Consensus/);
  assert.match(js, /turns\.slice\(-6\)/);
  assert.match(js, /clip\(analyst\.text, 3000\)/);
  assert.match(js, /clip\(challenger\.text, 2200\)/);
  assert.match(js, /Authorization: `Bearer \$\{token\}`/);
  assert.doesNotMatch(html + js, /OPENAI_API_KEY\s*=/);
  assert.doesNotMatch(js, /localStorage|sessionStorage/);
  assert.match(blueprint, /source: \/api\/\*/);
  assert.match(blueprint, /destination: https:\/\/live-command-center-deployment\.onrender\.com\/api\/\*/);
});
