"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

test("full live-data runtime transform raises satellite and dashboard limits", () => {
  const root = path.join(__dirname, "..");
  const satellites = require(path.join(root, "satellites.js"));
  const dashboard = fs.readFileSync(
    path.join(root, "public", "index.html"),
    "utf8"
  );

  assert.equal(satellites.MAX_SATELLITES, 512);
  assert.match(dashboard, /\/api\/eagle-eyes\/satellites\?limit=120/);
  assert.match(dashboard, /source=nws&limit=50/);
  assert.match(dashboard, /source=usgs&limit=50/);
  assert.match(dashboard, /source=eonet&limit=50/);
});
