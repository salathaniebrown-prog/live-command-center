"use strict";

const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");

const runFile = promisify(execFile);
const DEFAULT_STATE_PATH = path.join(
  process.cwd(),
  "data",
  "v1",
  "udp-backplane-state.json"
);

function cpuTimes() {
  return os.cpus().reduce(
    (sum, cpu) => {
      sum.idle += cpu.times.idle;
      sum.total += Object.values(cpu.times).reduce((a, b) => a + b, 0);
      return sum;
    },
    { idle: 0, total: 0 }
  );
}

async function cpuPercent(sampleMs = 200) {
  const before = cpuTimes();
  await new Promise((resolve) => setTimeout(resolve, sampleMs));
  const after = cpuTimes();
  const total = after.total - before.total;

  if (total <= 0) {
    return null;
  }

  return Number(
    ((1 - (after.idle - before.idle) / total) * 100).toFixed(1)
  );
}

async function storagePercent() {
  try {
    const { stdout } = await runFile("df", ["-P", "/"]);
    const value = Number(
      stdout.trim().split("\n").at(-1).trim().split(/\s+/)[4].replace("%", "")
    );
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

async function gpuPercent() {
  try {
    const { stdout } = await runFile("nvidia-smi", [
      "--query-gpu=utilization.gpu",
      "--format=csv,noheader,nounits"
    ]);
    const values = stdout
      .trim()
      .split("\n")
      .map(Number)
      .filter(Number.isFinite);

    if (!values.length) {
      return null;
    }

    return Number(
      (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)
    );
  } catch {
    return null;
  }
}

async function readBackplaneState(
  statePath = process.env.UDP_STATE_PATH || DEFAULT_STATE_PATH
) {
  try {
    const parsed = JSON.parse(await fs.readFile(statePath, "utf8"));
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function configuredNodeCount() {
  const value = Number(process.env.EAGLE_EYES_CLUSTER_NODES || 50);
  return Number.isInteger(value) && value > 0 ? value : 50;
}

async function compileSystemPerformanceMetrics() {
  const totalMemory = os.totalmem();
  const usedMemory = totalMemory - os.freemem();

  const [cpu, storage, gpu, backplane] = await Promise.all([
    cpuPercent(),
    storagePercent(),
    gpuPercent(),
    readBackplaneState()
  ]);

  return {
    ok: true,
    source: backplane ? "runtime+udp-backplane" : "runtime",
    runtime: {
      cpu,
      gpu,
      memory: totalMemory
        ? Number(((usedMemory / totalMemory) * 100).toFixed(1))
        : null,
      storage,
      temperatureC: null,
      loadAverage: os.loadavg().map((value) => Number(value.toFixed(2))),
      uptimeSeconds: Math.floor(process.uptime())
    },
    cluster: {
      configuredNodes: configuredNodeCount(),
      liveObservedNodes: backplane?.liveObservedNodes ?? null,
      simulationObservedNodes: backplane?.simulationObservedNodes ?? null,
      livePackets: backplane?.livePackets ?? null,
      simulatedPackets: backplane?.simulatedPackets ?? null,
      rejectedPackets: backplane?.rejectedPackets ?? null,
      bytesReceived: backplane?.bytesReceived ?? null,
      pendingPackets: backplane?.pendingPackets ?? null,
      throttleFactorMs: backplane?.throttleFactorMs ?? null,
      averageLatencyMs: backplane?.averageLatencyMs ?? null,
      maxLatencyMs: backplane?.maxLatencyMs ?? null,
      latencySpikeCount: backplane?.latencySpikeCount ?? null,
      lastPacketAt: backplane?.lastPacketAt ?? null,
      backplaneState: backplane ? "OBSERVED" : "UNAVAILABLE"
    },
    database: {
      configured: Boolean(process.env.DATABASE_URL),
      queried: false,
      note: "Database connectivity is not inferred from DATABASE_URL alone."
    },
    timestamp: new Date().toISOString()
  };
}

module.exports = {
  compileSystemPerformanceMetrics,
  readBackplaneState
};
