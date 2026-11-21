"use strict";

const { execFile } = require("child_process");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");

const DIM = 10000;
const POLL_MS = Number(process.env.PULSAR_POLL_MS || 1500);
const MEM_HIGH_THRESHOLD = Number(process.env.PULSAR_MEM_HIGH || 0.90);
const DRIFT_LEARN_THRESHOLD = Number(process.env.PULSAR_DRIFT_LEARN || 0.15);
const WAL_LOG_URL = process.env.PULSAR_WAL_URL || "http://127.0.0.1:8182/log";
const STATE_FILE =
  process.env.PULSAR_STATE_FILE ||
  path.join(os.homedir(), ".local", "share", "astra", "pulsar_hdc_state.json");

const DEFAULT_TARGETS = [
  { name: "gateway_8090", url: "http://127.0.0.1:8090/" },
  { name: "spine_8182", url: "http://127.0.0.1:8182/health" }
];
let TARGETS = DEFAULT_TARGETS;
if (process.env.PULSAR_TARGETS_JSON) {
  try {
    const parsed = JSON.parse(process.env.PULSAR_TARGETS_JSON);
    if (Array.isArray(parsed) && parsed.length > 0) TARGETS = parsed;
  } catch (_) {}
}

// Deterministic 64-bit splitmix64 seed generator -> 10,000-bit bipolar {-1, +1} vector
function makeHypervector(seedStr) {
  let h = 2166136261n;
  for (let i = 0; i < seedStr.length; i++) {
    h ^= BigInt(seedStr.charCodeAt(i));
    h = (h * 16777619n) & 0xffffffffffffffffn;
  }
  let state = h ^ 0x9e3779b97f4a7c15n;
  const vec = new Int8Array(DIM);
  for (let i = 0; i < DIM; i++) {
    state = (state + 0x9e3779b97f4a7c15n) & 0xffffffffffffffffn;
    let z = state;
    z = ((z ^ (z >> 30n)) * 0xbf58476d1ce4e5b9n) & 0xffffffffffffffffn;
    z = ((z ^ (z >> 27n)) * 0x94d049bb133111ebn) & 0xffffffffffffffffn;
    z = z ^ (z >> 31n);
    vec[i] = (z & 1n) === 1n ? 1 : -1;
  }
  return vec;
}

// Elementwise multiplication (binding in bipolar HDC)
function bind(a, b) {
  const out = new Int8Array(DIM);
  for (let i = 0; i < DIM; i++) {
    out[i] = a[i] * b[i];
  }
  return out;
}

// Superposition (bundling) of N bipolar vectors -> {-1, +1}
function bundle(vectors) {
  const acc = new Int32Array(DIM);
  for (const v of vectors) {
    for (let i = 0; i < DIM; i++) {
      acc[i] += v[i];
    }
  }
  const out = new Int8Array(DIM);
  for (let i = 0; i < DIM; i++) {
    out[i] = acc[i] >= 0 ? 1 : -1;
  }
  return out;
}

// Normalized Hamming distance in [0, 1] for {-1, +1} vectors
function hammingDistance(a, b) {
  let diff = 0;
  for (let i = 0; i < DIM; i++) {
    if (a[i] !== b[i]) diff++;
  }
  return diff / DIM;
}

function probeUrl(url, timeoutMs = 800) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      res.resume();
      resolve({ ok: res.statusCode >= 200 && res.statusCode < 500, code: res.statusCode });
    });
    req.on("timeout", () => {
      req.destroy();
      resolve({ ok: false, code: 0 });
    });
    req.on("error", () => {
      resolve({ ok: false, code: 0 });
    });
  });
}

function runTermux(cmd, args) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: 3000 }, (err) => {
      resolve(!err);
    });
  });
}

function postWalEvent(payload) {
  try {
    const body = JSON.stringify(payload);
    const u = new URL(WAL_LOG_URL);
    const req = http.request(
      {
        hostname: u.hostname,
        port: u.port || 8182,
        path: u.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body)
        },
        timeout: 1000
      },
      (res) => res.resume()
    );
    req.on("error", () => {});
    req.write(body);
    req.end();
  } catch (_) {}
}

// Precompute channel + state codebooks
const CHANNEL_VECS = {};
const STATE_ON_VECS = {};
const STATE_OFF_VECS = {};
for (const t of TARGETS) {
  CHANNEL_VECS[t.name] = makeHypervector(`chan:${t.name}`);
  STATE_ON_VECS[t.name] = makeHypervector(`state:${t.name}:up`);
  STATE_OFF_VECS[t.name] = makeHypervector(`state:${t.name}:down`);
}
const MEM_HIGH_VEC = makeHypervector("ram:high");
const MEM_NORM_VEC = makeHypervector("ram:normal");

// One-shot memory bank of observed anomaly vectors
const oneShotBank = [];
let baselineGlobal = null;
let lastSignature = "";
let lastHapticAt = 0;

function getMemRatio() {
  const total = os.totalmem() || 1;
  const free = os.freemem() || 0;
  return (total - free) / total;
}

async function emitProprioception(dist, knownAnomaly, signature) {
  const now = Date.now();
  // Rate-limit haptic motor to avoid Android vibrator queue saturation
  if (now - lastHapticAt < 650) return;
  lastHapticAt = now;

  if (knownAnomaly) {
    // Double-tap sharp alert for a previously seen error signature
    await runTermux("termux-vibrate", ["-d", "95", "-f"]);
    setTimeout(() => runTermux("termux-vibrate", ["-d", "95", "-f"]), 180);
    await runTermux("termux-tts-speak", [`Known state shift: ${signature}`]);
  } else if (dist > 0.18) {
    // Novel / high-distance anomaly ("unknown unknown" turbulence)
    await runTermux("termux-vibrate", ["-d", "140", "-f"]);
    await runTermux("termux-tts-speak", [`Anomaly distance ${dist.toFixed(2)}`]);
  } else {
    // Subtle heartbeat micro-pulse
    await runTermux("termux-vibrate", ["-d", "28", "-f"]);
  }
}

async function tick() {
  const results = await Promise.all(
    TARGETS.map(async (t) => ({ ...t, ...(await probeUrl(t.url)) }))
  );
  const memRatio = getMemRatio();
  const memHigh = memRatio >= MEM_HIGH_THRESHOLD;

  const boundParts = results.map((r) =>
    bind(CHANNEL_VECS[r.name], r.ok ? STATE_ON_VECS[r.name] : STATE_OFF_VECS[r.name])
  );
  boundParts.push(bind(makeHypervector("chan:ram"), memHigh ? MEM_HIGH_VEC : MEM_NORM_VEC));

  const globalVec = bundle(boundParts);
  if (!baselineGlobal) {
    baselineGlobal = globalVec;
  }

  const dist = hammingDistance(globalVec, baselineGlobal);
  const signature = results.map((r) => `${r.name}:${r.ok ? "UP" : "DN"}`).join("|") + `|ram:${(memRatio * 100).toFixed(0)}%`;

  // Check one-shot memory (similarity >= 0.85 -> distance <= 0.15 to a stored anomaly)
  let matchedIdx = -1;
  for (let i = 0; i < oneShotBank.length; i++) {
    if (hammingDistance(globalVec, oneShotBank[i].vec) <= 0.15) {
      matchedIdx = i;
      break;
    }
  }

  const isShift = signature !== lastSignature || dist > 0.18;
  let knownAnomaly = false;

  if (isShift) {
    if (matchedIdx >= 0) {
      knownAnomaly = true;
      oneShotBank[matchedIdx].hits += 1;
    } else if (dist > DRIFT_LEARN_THRESHOLD) {
      // One-shot learn this state vector
      oneShotBank.push({
        sig: signature,
        dist: Number(dist.toFixed(4)),
        hits: 1,
        vec: Array.from(globalVec)
      });
      if (oneShotBank.length > 64) oneShotBank.shift();
    }

    lastSignature = signature;
    postWalEvent({
      pulsar: "hdc_10k",
      dist: Number(dist.toFixed(4)),
      known_anomaly: knownAnomaly,
      one_shot_count: oneShotBank.length,
      signature
    });

    try {
      fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
      fs.writeFileSync(
        STATE_FILE,
        JSON.stringify(
          {
            updated_at: Date.now(),
            dist: Number(dist.toFixed(4)),
            signature,
            one_shot_entries: oneShotBank.map(({ sig, dist: d, hits }) => ({ sig, dist: d, hits }))
          },
          null,
          2
        )
      );
    } catch (_) {}

    await emitProprioception(dist, knownAnomaly, signature);
  }

  const upCount = results.filter((r) => r.ok).length;
  process.stdout.write(
    `\r[PULSAR-10K] up=${upCount}/${results.length} dist=${dist.toFixed(4)} mem=${(memRatio * 100).toFixed(1)}% oneshot=${oneShotBank.length} | ${signature}   `
  );
}

async function main() {
  console.log(`Starting Project PULSAR (${DIM}-bit HDC) poll=${POLL_MS}ms -> ${WAL_LOG_URL}`);
  await tick();
  setInterval(tick, POLL_MS);
}

main();
