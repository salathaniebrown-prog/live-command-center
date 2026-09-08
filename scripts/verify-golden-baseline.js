"use strict";

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const manifestPath = path.join(root, "config", "golden-baseline.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

const failures = [];

for (const capability of manifest.capabilities || []) {
  if (capability.status !== "required") continue;

  const combined = [];

  for (const relative of capability.evidence || []) {
    const absolute = path.join(root, relative);

    if (!fs.existsSync(absolute)) {
      failures.push(`${capability.id}: missing evidence file ${relative}`);
      continue;
    }

    try {
      combined.push(fs.readFileSync(absolute, "utf8"));
    } catch (error) {
      failures.push(`${capability.id}: cannot read ${relative}: ${error.message}`);
    }
  }

  const corpus = combined.join("\n");

  for (const requiredText of capability.requiredText || []) {
    if (!corpus.includes(requiredText)) {
      failures.push(`${capability.id}: required marker not found: ${requiredText}`);
    }
  }
}

if (failures.length) {
  console.error("EAGLE EYES GOLDEN BASELINE: FAIL");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("EAGLE EYES GOLDEN BASELINE: PASS");
console.log(`Protected capabilities: ${(manifest.capabilities || []).filter((x) => x.status === "required").length}`);

const targets = manifest.recoveryTargets || [];
if (targets.length) {
  console.log("Recovery targets still tracked separately from preserved capabilities:");
  for (const target of targets) {
    console.log(`- ${target.id}: ${target.status}`);
  }
}
