"use strict";

const { performance } = require("node:perf_hooks");
const { WorkerPool, clampWorkerCount } = require("./worker-pool");

function makeRecord(index) {
  return {
    id: `benchmark-${index}`,
    source: "assm-benchmark",
    eventType: "synthetic-throughput",
    title: `Synthetic benchmark record ${index}`,
    severity: index % 11 === 0 ? "severe" : "minor",
    magnitude: (index % 100) / 10,
    position: {
      latitude: ((index * 7) % 180) - 90,
      longitude: ((index * 13) % 360) - 180,
      depth: index % 50
    },
    retrievedAt: new Date(0).toISOString(),
    occurredAt: new Date((index % 168) * 60 * 60 * 1000).toISOString(),
    sourceMetadata: {
      urgency: index % 2 ? "expected" : "immediate",
      certainty: index % 3 ? "observed" : "likely",
      status: "actual",
      significance: index % 1000
    },
    geometry: { type: "Point" }
  };
}

function runBenchmark({ records = 10000, workerCount = 4, threshold = 5 } = {}) {
  const safeCount = Math.max(1, Math.min(Number(records) || 10000, 100000));
  const pool = new WorkerPool({
    workerCount: clampWorkerCount(workerCount),
    threshold
  });

  const started = performance.now();
  for (let index = 0; index < safeCount; index += 1) {
    pool.process(makeRecord(index));
  }
  const elapsedMs = performance.now() - started;

  return {
    readOnly: true,
    persisted: false,
    records: safeCount,
    workerCount: pool.workerCount,
    elapsedMs: Number(elapsedMs.toFixed(3)),
    recordsPerSecond: Number((safeCount / Math.max(elapsedMs / 1000, 0.000001)).toFixed(2)),
    pool: pool.snapshot()
  };
}

if (require.main === module) {
  const result = runBenchmark({
    records: process.env.ASSM_BENCHMARK_RECORDS,
    workerCount: process.env.ASSM_WORKERS,
    threshold: process.env.ASSM_HAMMING_THRESHOLD
  });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

module.exports = { makeRecord, runBenchmark };
