"use strict";

const readline = require("node:readline");
const { WorkerPool, clampWorkerCount } = require("./worker-pool");

const threshold = Number(process.env.ASSM_HAMMING_THRESHOLD || 5);
const workerCount = clampWorkerCount(process.env.ASSM_WORKERS || 1);
const pool = new WorkerPool({
  workerCount,
  threshold: Number.isFinite(threshold) ? threshold : 5
});

const rl = readline.createInterface({
  input: process.stdin,
  crlfDelay: Infinity
});

console.error(
  `[ASSM] Phase 2 read-only router ready with ${pool.workerCount} worker(s). ` +
  "Send one JSON spine record per line."
);

rl.on("line", (line) => {
  if (!line.trim()) return;

  try {
    const record = JSON.parse(line);
    const result = pool.process(record);
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({
      ok: false,
      readOnly: true,
      persisted: false,
      error: error.message,
      pool: pool.snapshot()
    })}\n`);
  }
});

process.on("SIGINT", () => {
  process.stderr.write(`[ASSM] Final pool snapshot: ${JSON.stringify(pool.snapshot())}\n`);
  process.exit(0);
});
