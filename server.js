"use strict";

const express = require("express");
const os = require("os");
const path = require("path");
const { execFile } = require("child_process");
const { promisify } = require("util");

const app = express();
const runFile = promisify(execFile);
const PORT = Number(process.env.PORT) || 3000;
const startedAt = new Date();

app.disable("x-powered-by");
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

function cpuTimes() {
  return os.cpus().reduce(
    (sum, cpu) => {
      const time = cpu.times;

      sum.idle += time.idle;
      sum.total +=
        time.user +
        time.nice +
        time.sys +
        time.idle +
        time.irq;

      return sum;
    },
    { idle: 0, total: 0 }
  );
}

async function getCpuPercent() {
  const before = cpuTimes();

  await new Promise((resolve) => setTimeout(resolve, 200));

  const after = cpuTimes();
  const totalDifference = after.total - before.total;
  const idleDifference = after.idle - before.idle;

  if (totalDifference <= 0) return null;

  return Number(
    ((1 - idleDifference / totalDifference) * 100).toFixed(1)
  );
}

async function getStoragePercent() {
  try {
    const { stdout } = await runFile("df", ["-P", "/"]);
    const lastLine = stdout.trim().split("\n").at(-1);
    const fields = lastLine.trim().split(/\s+/);

    return Number(fields[4].replace("%", ""));
  } catch {
    return null;
  }
}

async function getGpuPercent() {
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

    if (!values.length) return null;

    return Number(
      (
        values.reduce((sum, value) => sum + value, 0) /
        values.length
      ).toFixed(1)
    );
  } catch {
    return null;
  }
}

app.get("/api/status", (_req, res) => {
  res.json({
    online: true,
    systemStatus: "ONLINE",
    mode: "LIVE",
    source: "running-container",
    startedAt: startedAt.toISOString(),
    uptimeSeconds: Math.floor(process.uptime()),
    timestamp: new Date().toISOString()
  });
});

app.get("/api/metrics", async (_req, res) => {
  const totalMemory = os.totalmem();
  const usedMemory = totalMemory - os.freemem();

  const [cpu, storage, gpu] = await Promise.all([
    getCpuPercent(),
    getStoragePercent(),
    getGpuPercent()
  ]);

  res.json({
    cpu,
    gpu,
    memory: totalMemory
      ? Number(((usedMemory / totalMemory) * 100).toFixed(1))
      : null,
    storage,
    temperatureC: null,
    source: "container",
    timestamp: new Date().toISOString()
  });
});

app.get("/api/workloads", (_req, res) => {
  res.json([]);
});

app.get("/api/deployment", (_req, res) => {
  res.json({
    stage: "RUNNING",
    serviceId: process.env.RAILWAY_SERVICE_ID || null,
    deploymentId: process.env.RAILWAY_DEPLOYMENT_ID || null,
    source: "runtime-environment",
    timestamp: new Date().toISOString()
  });
});

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    uptimeSeconds: Math.floor(process.uptime()),
    time: new Date().toISOString()
  });
});
app.get("/api/dedalus/health", async (_req, res) => {
  const apiKey = process.env.DEDALUS_API_KEY;

  if (!apiKey) {
    return res.status(503).json({
      ok: false,
      service: "dedalus",
      error: "DEDALUS_API_KEY is not configured"
    });
  }

  try {
    const response = await fetch("https://api.dedaluslabs.ai/v1/models", {
      headers: {
        Authorization: `Bearer ${apiKey}`
      },
      signal: AbortSignal.timeout(10000)
    });

    if (!response.ok) {
      return res.status(502).json({
        ok: false,
        service: "dedalus",
        error: `Dedalus returned HTTP ${response.status}`
      });
    }

    return res.json({
      ok: true,
      service: "dedalus",
      connected: true,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    return res.status(502).json({
      ok: false,
      service: "dedalus",
      error: "Dedalus connection failed"
    });
  }
});
app.use((error, _req, res, _next) => {
  console.error(error);

  res.status(500).json({
    ok: false,
    error: "Internal server error"
  });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Command Center listening on port ${PORT}`);
});
