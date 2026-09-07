"use strict";

const readline = require("node:readline");
const { Metrics } = require("./metrics");
const { processRecord } = require("./worker");

const threshold = Number(process.env.ASSM_HAMMING_THRESHOLD || 5);
const context = {
  baseline: null,
  threshold: Number.isFinite(threshold) ? threshold : 5,
  metrics: new Metrics()
};

const rl = readline.createInterface({
  input: process.stdin,
  crlfDelay: Infinity
});

console.error("[ASSM] Phase 1 read-only router ready. Send one JSON spine record per line.");

rl.on("line", (line) => {
  if (!line.trim()) return;
  context.metrics.recordReceived();

  try {
    const record = JSON.parse(line);
    const result = processRecord(record, context);
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch (error) {
    context.metrics.recordInvalid();
    process.stdout.write(`${JSON.stringify({
      ok: false,
      readOnly: true,
      persisted: false,
      error: error.message,
      metrics: context.metrics.snapshot()
    })}\n`);
  }
});
