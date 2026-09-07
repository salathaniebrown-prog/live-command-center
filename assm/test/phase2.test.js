"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { WorkerPool, clampWorkerCount } = require("../src/worker-pool");
const { makeRecord, runBenchmark } = require("../src/benchmark");

test("worker count is constrained to the Phase 2 safety boundary", () => {
  assert.equal(clampWorkerCount(undefined), 1);
  assert.equal(clampWorkerCount(0), 1);
  assert.equal(clampWorkerCount(1), 1);
  assert.equal(clampWorkerCount(4), 4);
  assert.equal(clampWorkerCount(32), 4);
});

test("the same record routes deterministically to the same worker", () => {
  const pool = new WorkerPool({ workerCount: 4 });
  const record = makeRecord(42);
  const first = pool.selectWorker(record).id;
  const second = pool.selectWorker(record).id;
  assert.equal(first, second);
});

test("four-worker routing remains read-only and tracks distribution", () => {
  const pool = new WorkerPool({ workerCount: 4 });
  for (let index = 0; index < 100; index += 1) {
    const result = pool.process(makeRecord(index));
    assert.equal(result.readOnly, true);
    assert.equal(result.persisted, false);
    assert.ok(result.workerId >= 1 && result.workerId <= 4);
  }

  const snapshot = pool.snapshot();
  assert.equal(snapshot.workerCount, 4);
  assert.equal(snapshot.distribution.reduce((sum, value) => sum + value, 0), 100);
  assert.equal(snapshot.readOnly, true);
  assert.equal(snapshot.persisted, false);
});

test("benchmark processes the requested record count without persistence", () => {
  const result = runBenchmark({ records: 250, workerCount: 4 });
  assert.equal(result.records, 250);
  assert.equal(result.workerCount, 4);
  assert.equal(result.readOnly, true);
  assert.equal(result.persisted, false);
  assert.ok(result.elapsedMs >= 0);
  assert.ok(result.recordsPerSecond > 0);
  assert.equal(result.pool.distribution.reduce((sum, value) => sum + value, 0), 250);
});
