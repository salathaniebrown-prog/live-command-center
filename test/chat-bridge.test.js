"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const htmlPath = path.join(root, "public", "chat", "index.html");
const jsPath = path.join(root, "public", "chat", "chat.js");

test("Eagle Eyes web chat bridge is syntax-valid and keeps secrets server-side", () => {
  assert.equal(fs.existsSync(htmlPath), true);
  assert.equal(fs.existsSync(jsPath), true);

  const html = fs.readFileSync(htmlPath, "utf8");
  const js = fs.readFileSync(jsPath, "utf8");

  execFileSync(process.execPath, ["--check", jsPath], { stdio: "pipe" });

  assert.match(html, /Direct Chat Bridge/);
  assert.match(js, /\/api\/assistant\/status/);
  assert.match(js, /\/api\/assistant\/auth-check/);
  assert.match(js, /\/api\/assistant\/stream/);
  assert.match(js, /Authorization: `Bearer \$\{token\}`/);
  assert.match(js, /turns\.slice\(-10\)/);
  assert.doesNotMatch(html + js, /OPENAI_API_KEY\s*=/);
  assert.doesNotMatch(js, /localStorage|sessionStorage/);
});
