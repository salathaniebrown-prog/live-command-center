const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

const demo = {
  status: {
    online: true,
    systemStatus: "OPTIMAL",
    deployment: 100,
    mode: "DEMO — connect real APIs to replace these values"
  },
  metrics: {
    cpu: 72,
    gpu: 94,
    memory: 81,
    storage: 66,
    temperatureC: 58
  },
  workloads: [
    "AI model training",
    "Physics simulation",
    "Neural rendering",
    "Data analytics",
    "Real-world testing",
    "Digital twins"
  ],
  deployment: {
    progress: 100,
    stage: "LIVE",
    success: true
  }
};

// Optional upstream API adapters.
// Set an environment variable to a real JSON endpoint:
// STATUS_URL, METRICS_URL, WORKLOADS_URL, DEPLOYMENT_URL
async function upstream(url, fallback) {
  if (!url) return fallback;
  try {
    const r = await fetch(url, { headers: { "accept": "application/json" } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    return { ...fallback, upstreamError: e.message };
  }
}

app.get("/api/status", async (_req, res) =>
  res.json(await upstream(process.env.STATUS_URL, demo.status))
);

app.get("/api/metrics", async (_req, res) =>
  res.json(await upstream(process.env.METRICS_URL, demo.metrics))
);

app.get("/api/workloads", async (_req, res) =>
  res.json(await upstream(process.env.WORKLOADS_URL, demo.workloads))
);

app.get("/api/deployment", async (_req, res) =>
  res.json(await upstream(process.env.DEPLOYMENT_URL, demo.deployment))
);

app.get("/api/health", (_req, res) =>
  res.json({ ok: true, time: new Date().toISOString() })
);

app.listen(PORT, () =>
  console.log(`Command Center live at http://localhost:${PORT}`)
);
