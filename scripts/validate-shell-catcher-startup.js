"use strict";

const { runShellCatcherSelfTest } = require("../shell-catcher");

const result = runShellCatcherSelfTest();
const summary = {
  service: "eagle-eyes-shell-catcher",
  check: "startup-self-test",
  ok: result.ok,
  passed: result.passed,
  total: result.total,
  coveragePercent: result.coveragePercent,
  ingestConfigured: Boolean(process.env.SHELL_CATCHER_INGEST_TOKEN),
  arbitraryShellExecution: false,
  commandAuthority: false,
  domains: ["api", "shell", "air", "water", "ground", "system"]
};

console.log(`[Shell Catcher] ${JSON.stringify(summary)}`);

if (!result.ok) {
  const missNames = result.misses.map((item) => item.name);
  console.error(`[Shell Catcher] startup detector misses: ${JSON.stringify(missNames)}`);
  process.exit(1);
}
