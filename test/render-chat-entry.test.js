"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("Render chat entry points exist and keep secrets server-side", () => {
  const rootEntry = read("public/chat.html");
  const nestedEntry = read("public/chat/index.html");
  const client = read("public/chat/chat.js");

  assert.match(rootEntry, /EAGLE EYES · OPENAI/);
  assert.match(rootEntry, /<script src="\/chat\/chat\.js" defer><\/script>/);
  assert.match(nestedEntry, /Direct Chat Bridge/);
  assert.match(client, /\/api\/assistant\/stream/);

  for (const text of [rootEntry, nestedEntry, client]) {
    assert.doesNotMatch(text, /sk-[A-Za-z0-9_-]{16,}/);
    assert.doesNotMatch(text, /OPENAI_API_KEY\s*=/);
    assert.doesNotMatch(text, /localStorage|sessionStorage/);
  }
});
