"use strict";

class Metrics {
  constructor() {
    this.startedAt = Date.now();
    this.received = 0;
    this.processed = 0;
    this.invalid = 0;
    this.anomalies = 0;
  }

  recordReceived() {
    this.received += 1;
  }

  recordProcessed({ anomalous = false } = {}) {
    this.processed += 1;
    if (anomalous) this.anomalies += 1;
  }

  recordInvalid() {
    this.invalid += 1;
  }

  snapshot() {
    const elapsedMs = Math.max(1, Date.now() - this.startedAt);
    return {
      received: this.received,
      processed: this.processed,
      invalid: this.invalid,
      anomalies: this.anomalies,
      elapsedMs,
      averagePps: Number(((this.processed * 1000) / elapsedMs).toFixed(2))
    };
  }
}

module.exports = { Metrics };
