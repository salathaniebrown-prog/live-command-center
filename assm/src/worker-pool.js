"use strict";

const { Metrics } = require("./metrics");
const { processRecord } = require("./worker");

function clampWorkerCount(value) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) return 1;
  return Math.min(parsed, 4);
}

function hashKey(value) {
  let hash = 2166136261;
  for (const char of String(value || "")) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash >>> 0;
}

function recordKey(record) {
  return record?.id || record?.eventId || record?.title || record?.source || JSON.stringify(record);
}

class WorkerPool {
  constructor({ workerCount = 1, threshold = 5 } = {}) {
    this.workerCount = clampWorkerCount(workerCount);
    this.threshold = Number.isFinite(Number(threshold)) ? Number(threshold) : 5;
    this.workers = Array.from({ length: this.workerCount }, (_, index) => ({
      id: index + 1,
      context: {
        baseline: null,
        threshold: this.threshold,
        metrics: new Metrics()
      }
    }));
    this.distribution = Array(this.workerCount).fill(0);
  }

  selectWorker(record) {
    const index = hashKey(recordKey(record)) % this.workerCount;
    return this.workers[index];
  }

  process(record) {
    const worker = this.selectWorker(record);
    const index = worker.id - 1;
    this.distribution[index] += 1;
    const result = processRecord(record, worker.context);
    return {
      ...result,
      workerId: worker.id,
      workerCount: this.workerCount,
      distribution: [...this.distribution]
    };
  }

  snapshot() {
    return {
      readOnly: true,
      persisted: false,
      workerCount: this.workerCount,
      distribution: [...this.distribution],
      workers: this.workers.map((worker) => ({
        id: worker.id,
        metrics: worker.context.metrics.snapshot(),
        baselineInitialized: Boolean(worker.context.baseline)
      }))
    };
  }
}

module.exports = {
  WorkerPool,
  clampWorkerCount,
  hashKey,
  recordKey
};
