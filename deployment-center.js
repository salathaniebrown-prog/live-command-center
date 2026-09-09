'use strict';

const express = require('express');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { performance } = require('node:perf_hooks');

const SLOT_COUNT = 32;
const WINDOW_MS = 60000;
const REPOSITORY = 'salathaniebrown-prog/live-command-center';
const WORKFLOW = 'command-center-deploy.yml';
const csvCell = value => `"${String(value ?? '').replace(/"/g, '""')}"`;

class MobileRegistry {
  constructor({ devices = {}, now = Date.now, staleMs = WINDOW_MS } = {}) {
    this.devices = devices;
    this.now = now;
    this.staleMs = staleMs;
    this.slots = new Map();
    this.nonces = new Map();
    const assigned = new Set();
    for (const [id, device] of Object.entries(devices)) {
      if (!/^[A-Za-z0-9_-]{1,80}$/.test(id) || !Number.isInteger(device.slot) ||
          device.slot < 1 || device.slot > SLOT_COUNT || assigned.has(device.slot) ||
          typeof device.secret !== 'string' || device.secret.length < 64 ||
          /placeholder|your_|secure_system/i.test(device.secret)) {
        throw new Error('MOBILE_DEVICES_JSON requires unique slots and a separate random secret of at least 64 characters per device');
      }
      assigned.add(device.slot);
    }
  }

  ingest(raw, headers) {
    const fail = (status, error) => ({ status, error });
    const timestamp = headers['x-eagle-eyes-timestamp'];
    const nonce = headers['x-eagle-eyes-nonce'];
    const signature = headers['x-eagle-eyes-signature'];
    const deviceId = headers['x-eagle-eyes-device'];
    const device = Object.hasOwn(this.devices, deviceId || '') ? this.devices[deviceId] : null;
    if (!Object.keys(this.devices).length) return fail(503, 'Mobile devices are not enrolled');
    if (!device || !/^\d{13}$/.test(timestamp || '') ||
        !/^[A-Za-z0-9_-]{16,80}$/.test(nonce || '') || !/^[a-f0-9]{64}$/.test(signature || '')) {
      return fail(401, 'Invalid authentication envelope');
    }
    const now = this.now();
    if (Math.abs(now - Number(timestamp)) > WINDOW_MS) return fail(401, 'Expired timestamp');
    const expected = crypto.createHmac('sha256', device.secret)
      .update(`${timestamp}.${nonce}.`).update(raw).digest();
    if (!crypto.timingSafeEqual(expected, Buffer.from(signature, 'hex'))) return fail(403, 'Invalid signature');
    for (const [key, expires] of this.nonces) if (expires <= now) this.nonces.delete(key);
    const key = `${deviceId}:${nonce}`;
    if (this.nonces.has(key)) return fail(409, 'Repeated heartbeat');
    if (this.nonces.size >= 4096) return fail(429, 'Heartbeat capacity reached; retry later');
    let payload;
    try { payload = JSON.parse(raw.toString('utf8')); } catch { return fail(400, 'Invalid JSON'); }
    if (!payload || Array.isArray(payload) || payload.device_id !== deviceId ||
        payload.target_cluster_slot !== device.slot || !['PASS', 'FAIL'].includes(payload.status_flag) ||
        Object.keys(payload).some(name => !['device_id', 'target_cluster_slot', 'status_flag'].includes(name))) {
      return fail(400, 'Payload does not match enrolled device and slot');
    }
    this.nonces.set(key, Number(timestamp) + WINDOW_MS + 1);
    this.slots.set(device.slot, { status: payload.status_flag, receivedAt: new Date(now).toISOString(), receivedMs: now });
    return { status: 200, node: device.slot, receiptId: crypto.randomUUID(), receivedAt: new Date(now).toISOString() };
  }

  snapshot() {
    const configured = new Set(Object.values(this.devices).map(device => device.slot));
    return Array.from({ length: SLOT_COUNT }, (_, index) => {
      const id = index + 1;
      const value = this.slots.get(id);
      return {
        nodeId: id,
        enrolled: configured.has(id),
        status: value ? (this.now() - value.receivedMs > this.staleMs ? 'STALE' : value.status) : 'WAITING',
        receivedAt: value?.receivedAt || null,
        ageMs: value ? Math.max(0, this.now() - value.receivedMs) : null,
        latencyMs: null,
        source: value ? 'signed-device-report' : null
      };
    });
  }
}

class CsvLog {
  constructor(file) { this.file = file; this.queue = Promise.resolve(); }
  append(row) {
    const operation = this.queue.then(async () => {
      await fs.mkdir(path.dirname(this.file), { recursive: true, mode: 0o700 });
      const size = await fs.stat(this.file).then(stat => stat.size).catch(error => {
        if (error.code === 'ENOENT') return 0;
        throw error;
      });
      if (size >= 50 * 1024 * 1024) await fs.rename(this.file, this.file + '.1');
      if (!size || size >= 50 * 1024 * 1024) {
        await fs.writeFile(this.file, 'Timestamp,Node,Status,Processing_Latency_MS\n', { mode: 0o600 });
      }
      await fs.appendFile(this.file, row.map(csvCell).join(',') + '\n', { mode: 0o600 });
    });
    this.queue = operation.catch(() => {});
    return operation;
  }
}

function createDeploymentCenter({ world, metrics, deployment, guard, env = process.env, fetchImpl = fetch, now = Date.now }) {
  const router = express.Router();
  const registry = new MobileRegistry({ devices: JSON.parse(env.MOBILE_DEVICES_JSON || '{}'), now });
  const logger = new CsvLog(path.join(env.DEPLOYMENT_LOG_DIR || path.join(os.tmpdir(), 'eagle-eyes'), 'network_stats.csv'));
  const subscribers = new Set();
  let cached = null;
  let inFlight = null;
  let lastAttempt = 0;
  let nextDispatch = 0;
  let dispatching = false;
  const workflowUrl = `https://github.com/${REPOSITORY}/actions/workflows/${WORKFLOW}`;

  async function measured(name, operation) {
    const started = performance.now();
    try {
      const value = await operation();
      return { name, status: 'ONLINE', value, latencyMs: Number((performance.now() - started).toFixed(2)), checkedAt: new Date(now()).toISOString() };
    } catch {
      return { name, status: 'UNAVAILABLE', value: null, latencyMs: Number((performance.now() - started).toFixed(2)), checkedAt: new Date(now()).toISOString() };
    }
  }

  async function price(pair) {
    const url = `https://api.coinbase.com/v2/prices/${pair}/spot`;
    const result = await measured(pair, async () => {
      const response = await fetchImpl(url, { signal: AbortSignal.timeout(5000), redirect: 'error' });
      if (!response.ok) throw new Error('Market unavailable');
      const data = (await response.json()).data;
      if (data?.currency !== 'USD' || !/^\d+(\.\d+)?$/.test(data?.amount || '') || !Number.isFinite(Number(data.amount)) || Number(data.amount) <= 0) {
        throw new Error('Invalid market data');
      }
      return data.amount;
    });
    return { ...result, sourceUrl: url, unit: 'USD', kind: 'spot-price' };
  }

  async function collect() {
    if (cached && now() - lastAttempt < 30000) return cached;
    if (inFlight) return inFlight;
    lastAttempt = now();
    inFlight = (async () => {
      const [host, feeds, markets] = await Promise.all([
        measured('host', metrics),
        Promise.all(['usgs', 'nws', 'eonet'].map(name => measured(name, async () => {
          const value = await world(name, 50);
          if (value.ok !== true || !Array.isArray(value.events)) throw new Error('Invalid feed');
          return { count: value.events.length, sourceUrl: value.sourceUrl || null, latest: value.events.slice(0, 3) };
        }))),
        Promise.all(['USDC-USD', 'BTC-USD'].map(price))
      ]);
      cached = { checkedAt: new Date(now()).toISOString(), host, feeds, markets };
      return cached;
    })().finally(() => { inFlight = null; });
    return inFlight;
  }

  async function snapshot() {
    const state = await collect();
    const nodes = registry.snapshot();
    const ageMs = Math.max(0, now() - Date.parse(state.checkedAt));
    return {
      schemaVersion: 1, simulated: false, ...state, collectionAgeMs: ageMs,
      systemState: ageMs > 60000 ? 'STALE' : [state.host, ...state.feeds, ...state.markets].every(x => x.status === 'ONLINE') ? 'LIVE' : 'DEGRADED',
      deployment: deployment(), nodes,
      activeNodes: nodes.filter(node => node.status === 'PASS').length,
      enrolledNodes: nodes.filter(node => node.enrolled).length,
      capabilities: { deployConfigured: Boolean(env.DEPLOYMENT_GITHUB_TOKEN), workflowUrl, mobileConfigured: Object.keys(registry.devices).length > 0, transport: 'SSE', heartbeatStaleAfterMs: WINDOW_MS }
    };
  }

  function send(res, event, data) {
    if (res.destroyed || res.writableEnded) return;
    if (res.writableLength > 256 * 1024) { res.end(); return; }
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  }
  function broadcastNodes() {
    const nodes = registry.snapshot();
    for (const res of subscribers) send(res, 'nodes', { nodes });
  }

  router.get(['/api/telemetry', '/api/deployment-center/status'], async (_req, res, next) => {
    try { res.set('Cache-Control', 'no-store').json(await snapshot()); } catch (error) { next(error); }
  });
  router.get('/api/deployment-center/stream', async (req, res) => {
    if (subscribers.size >= 32) return res.status(429).json({ error: 'Stream capacity reached' });
    subscribers.add(res);
    res.set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no' });
    res.flushHeaders();
    let running = false;
    const tick = async () => {
      if (running || res.destroyed) return;
      running = true;
      try { send(res, 'snapshot', await snapshot()); }
      catch { send(res, 'unavailable', { message: 'Telemetry collection unavailable' }); }
      finally { running = false; }
    };
    const timer = setInterval(tick, 5000);
    timer.unref();
    res.on('close', () => { clearInterval(timer); subscribers.delete(res); });
    await tick();
  });

  router.post('/api/mobile/telemetry', express.raw({ type: 'application/json', limit: '16kb', inflate: false }), async (req, res) => {
    const started = performance.now();
    if (!Buffer.isBuffer(req.body)) return res.status(415).json({ error: 'application/json required' });
    const receipt = registry.ingest(req.body, req.headers);
    if (receipt.status !== 200) return res.status(receipt.status).json({ error: receipt.error });
    const processingLatencyMs = Number((performance.now() - started).toFixed(3));
    let logged = true;
    try { await logger.append([receipt.receivedAt, receipt.node, registry.slots.get(receipt.node).status, processingLatencyMs]); }
    catch { logged = false; console.error('Deployment Center heartbeat log unavailable'); }
    broadcastNodes();
    res.json({ accepted: true, receiptId: receipt.receiptId, receivedAt: receipt.receivedAt, nodeId: receipt.node, processingLatencyMs, logged });
  });
  router.get('/api/deployment-center/network.csv', guard, async (_req, res, next) => {
    try {
      await logger.queue;
      res.set({ 'Cache-Control': 'no-store', 'Content-Disposition': 'attachment; filename="network_stats.csv"' });
      res.type('text/csv').send(await fs.readFile(logger.file, 'utf8'));
    } catch (error) {
      if (error.code === 'ENOENT') return res.status(404).json({ error: 'No device heartbeats have been logged' });
      next(error);
    }
  });

  router.post('/api/deployment-center/deploy', guard, express.json({ limit: '2kb' }), async (req, res) => {
    if (!env.DEPLOYMENT_GITHUB_TOKEN) return res.status(503).json({ error: 'GitHub deployment credential is not configured', workflowUrl });
    if (dispatching || now() < nextDispatch) return res.status(429).json({ error: 'A deployment was recently requested; inspect GitHub Actions before retrying' });
    const expected = req.body?.expectedCommit;
    if (!/^[a-f0-9]{40}$/.test(expected || '')) return res.status(400).json({ error: 'A full verified commit is required' });
    dispatching = true;
    try {
      const headers = { Authorization: `Bearer ${env.DEPLOYMENT_GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28' };
      const headResponse = await fetchImpl(`https://api.github.com/repos/${REPOSITORY}/git/ref/heads/main`, { headers, signal: AbortSignal.timeout(5000), redirect: 'error' });
      if (!headResponse.ok) throw new Error('GitHub unavailable');
      if ((await headResponse.json()).object?.sha !== expected) return res.status(409).json({ error: 'Main has changed; verify its new revision before deploying' });
      // Set the cooldown before dispatch: a timeout can mean GitHub accepted the request.
      nextDispatch = now() + 60000;
      const response = await fetchImpl(`https://api.github.com/repos/${REPOSITORY}/actions/workflows/${WORKFLOW}/dispatches`, {
        method: 'POST', headers, body: JSON.stringify({ ref: 'main', inputs: { expected_sha: expected } }),
        signal: AbortSignal.timeout(10000), redirect: 'error'
      });
      if (response.status !== 204) throw new Error('Dispatch rejected');
      res.status(202).json({ status: 'REQUESTED', expectedCommit: expected, workflowUrl, message: 'GitHub accepted the workflow request. Deployment success requires its verification job to pass.' });
    } catch { res.status(502).json({ error: 'Deployment request could not be confirmed. Check GitHub Actions before retrying.', workflowUrl }); }
    finally { dispatching = false; }
  });
  router.use((error, _req, res, _next) => {
    res.status(error.status >= 400 && error.status < 500 ? error.status : 500).json({ error: error.status === 413 ? 'Payload too large' : 'Request could not be processed' });
  });
  return { router, registry, snapshot, logger };
}

module.exports = { MobileRegistry, CsvLog, createDeploymentCenter };
