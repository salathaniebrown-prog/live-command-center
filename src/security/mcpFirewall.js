"use strict";

class McpToolFirewall {
  constructor({
    cooldownMs = 5000,
    minThrottleMs = 0,
    maxThrottleMs = 250
  } = {}) {
    this.lastExecutionTime = 0;
    this.COOLDOWN_MS = cooldownMs;
    this.MIN_THROTTLE_MS = minThrottleMs;
    this.MAX_THROTTLE_MS = maxThrottleMs;
  }

  validateTuneRequest(args = {}) {
    const now = Date.now();

    if (!args || typeof args !== "object" || Array.isArray(args)) {
      throw new Error("[FIREWALL BLOCK]: Tool arguments must be an object.");
    }

    const unexpected = Object.keys(args).filter((key) => key !== "throttleFactor");
    if (unexpected.length) {
      throw new Error(
        `[FIREWALL BLOCK]: Unsupported tuning field(s): ${unexpected.join(", ")}.`
      );
    }

    const throttle = args.throttleFactor;
    if (
      typeof throttle !== "number" ||
      !Number.isFinite(throttle) ||
      throttle < this.MIN_THROTTLE_MS ||
      throttle > this.MAX_THROTTLE_MS
    ) {
      throw new Error(
        `[FIREWALL BLOCK]: throttleFactor must be a finite number between ${this.MIN_THROTTLE_MS}ms and ${this.MAX_THROTTLE_MS}ms.`
      );
    }

    const elapsed = now - this.lastExecutionTime;
    if (this.lastExecutionTime && elapsed < this.COOLDOWN_MS) {
      throw new Error(
        `[FIREWALL BLOCK]: Execution throttled. Retry after ${this.COOLDOWN_MS - elapsed}ms.`
      );
    }

    this.lastExecutionTime = now;

    return {
      approved: true,
      throttleFactor: throttle,
      approvedAt: new Date(now).toISOString()
    };
  }
}

module.exports = { McpToolFirewall };
