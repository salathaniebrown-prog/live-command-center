'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const express = require('express');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { MobileRegistry, createDeploymentCenter } = require('../deployment-center');
const secret = 'b'.repeat(64);
const clock = 1788970000000;
const devices = { field12: { slot: 12, secret } };
function signed(body = '{"device_id":"field12", "target_cluster_slot":12,"status_flag":"PASS"}', timestamp = clock, nonce = 'a'.repeat(32)) {
  const raw = Buffer.from(body);
  return { raw, headers: {
    'x-eagle-eyes-device': 'field12', 'x-eagle-eyes-timestamp': String(timestamp), 'x-eagle-eyes-nonce': nonce,
    'x-eagle-eyes-signature': crypto.createHmac('sha256', secret).update(`${timestamp}.${nonce}.`).update(raw).digest('hex')
  } };
}
test('unobserved slots stay waiting; signed PASS becomes stale after timeout', () => {
  let now = clock;
  const store = new MobileRegistry({ devices, now: () => now });
  assert.equal(store.snapshot().filter(node => node.status === 'WAITING').length, 32);
  const input = signed(); assert.equal(store.ingest(input.raw, input.headers).status, 200);
  assert.equal(store.snapshot()[11].status, 'PASS');
  assert.equal(store.snapshot()[11].latencyMs, null);
  now += 60001; assert.equal(store.snapshot()[11].status, 'STALE');
});
test('mobile verification preserves exact JSON bytes and rejects replay, tampering, clock skew, and unauthorized slots', () => {
  const store = new MobileRegistry({ devices, now: () => clock });
  const valid = signed();
  assert.equal(store.ingest(Buffer.from(valid.raw.toString().replace(' ', '')), valid.headers).status, 403);
  assert.equal(store.ingest(valid.raw, valid.headers).status, 200);
  assert.equal(store.ingest(valid.raw, valid.headers).status, 409);
  const expired = signed(undefined, clock - 60001); assert.equal(store.ingest(expired.raw, expired.headers).status, 401);
  const wrongSlot = signed('{"device_id":"field12","target_cluster_slot":13,"status_flag":"PASS"}', clock, 'c'.repeat(32));
  assert.equal(store.ingest(wrongSlot.raw, wrongSlot.headers).status, 400);
  assert.equal(store.ingest(valid.raw, { ...valid.headers, 'x-eagle-eyes-device': '__proto__' }).status, 401);
});
test('duplicate assignments, placeholder secrets and unenrolled devices fail closed', () => {
  assert.throws(() => new MobileRegistry({ devices: { ...devices, another: { slot: 12, secret } } }));
  assert.throws(() => new MobileRegistry({ devices: { field12: { slot: 12, secret: 'PLACEHOLDER'.repeat(9) } } }));
  const valid = signed(); assert.equal(new MobileRegistry().ingest(valid.raw, valid.headers).status, 503);
});
const guard = (req, res, next) => req.get('authorization') === 'Bearer test-access' ? next() : res.status(401).json({ error: 'Unauthorized' });
const input = overrides => ({
  guard, now: () => clock, env: {}, deployment: () => ({ commitSha: 'a'.repeat(40), branch: 'main' }),
  world: async source => ({ ok: true, events: [{ source }] }), metrics: async () => ({ cpu: 2.5, gpu: null }),
  fetchImpl: async url => ({ ok: true, json: async () => ({ data: { currency: 'USD', amount: url.includes('BTC') ? '50000' : '0.9998' } }) }),
  ...overrides
});
test('concurrent consumers share actual measurements and never fabricate node passes or fallback prices', async () => {
  let calls = 0;
  const center = createDeploymentCenter(input({
    world: async name => { calls++; if (name === 'nws') throw new Error('timeout'); return { ok: true, events: [] }; },
    fetchImpl: async () => ({ ok: true, json: async () => ({ data: { amount: 'not-a-price' } }) })
  }));
  const snapshots = await Promise.all(Array.from({ length: 10 }, () => center.snapshot()));
  assert.equal(calls, 3);
  assert.equal(snapshots[0].systemState, 'DEGRADED');
  assert.equal(snapshots[0].markets[0].value, null);
  assert.equal(snapshots[0].activeNodes, 0);
  assert.equal(snapshots[0].feeds.find(feed => feed.name === 'nws').status, 'UNAVAILABLE');
});
async function running(t, center) {
  const app = express(); app.use(center.router); app.use(express.json());
  const server = app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.on('listening', resolve));
  t.after(() => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); }));
  return `http://127.0.0.1:${server.address().port}`;
}
test('HTTP ingest writes measured CSV; protected export and deploy cannot be called anonymously', async t => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'eagle-center-test-'));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  const center = createDeploymentCenter(input({ env: { MOBILE_DEVICES_JSON: JSON.stringify(devices), DEPLOYMENT_LOG_DIR: directory } }));
  const url = await running(t, center);
  assert.equal((await fetch(url + '/api/deployment-center/deploy', { method: 'POST' })).status, 401);
  assert.equal((await fetch(url + '/api/deployment-center/network.csv')).status, 401);
  const packet = signed();
  const response = await fetch(url + '/api/mobile/telemetry', { method: 'POST', headers: { ...packet.headers, 'Content-Type': 'application/json' }, body: packet.raw });
  assert.equal(response.status, 200); const data = await response.json();
  assert.equal(data.logged, true); assert.ok(data.processingLatencyMs >= 0);
  const csv = await fetch(url + '/api/deployment-center/network.csv', { headers: { Authorization: 'Bearer test-access' } });
  assert.equal(csv.status, 200); assert.match(await csv.text(), /Processing_Latency_MS\n.*"12","PASS"/);
  const replay = await fetch(url + '/api/mobile/telemetry', { method: 'POST', headers: { ...packet.headers, 'Content-Type': 'application/json' }, body: packet.raw });
  assert.equal(replay.status, 409);
});
test('dispatch only requests the fixed workflow for the current main SHA and reports accepted, not deployed', async t => {
  const calls = [];
  const center = createDeploymentCenter(input({ env: { DEPLOYMENT_GITHUB_TOKEN: 'test-token' }, fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return options.method === 'POST' ? { status: 204 } : { ok: true, json: async () => ({ object: { sha: 'a'.repeat(40) } }) };
  } }));
  const url = await running(t, center);
  const request = commit => fetch(url + '/api/deployment-center/deploy', { method: 'POST', headers: { Authorization: 'Bearer test-access', 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedCommit: commit, targetRepo: 'untrusted/other' }) });
  assert.equal((await request('b'.repeat(40))).status, 409);
  const accepted = await request('a'.repeat(40)); assert.equal(accepted.status, 202);
  assert.equal((await accepted.json()).status, 'REQUESTED');
  assert.match(calls.at(-1).url, /salathaniebrown-prog\/live-command-center\/actions\/workflows\/command-center-deploy.yml\/dispatches$/);
  assert.equal(JSON.parse(calls.at(-1).options.body).inputs.expected_sha, 'a'.repeat(40));
  assert.equal((await request('a'.repeat(40))).status, 429);
});
test('SSE sends the same measured snapshot and starts with zero reporting devices', async t => {
  const center = createDeploymentCenter(input()); const url = await running(t, center);
  const controller = new AbortController();
  const response = await fetch(url + '/api/deployment-center/stream', { signal: controller.signal });
  const reader = response.body.getReader(); const { value } = await reader.read();
  const text = new TextDecoder().decode(value);
  assert.match(text, /event: snapshot/); assert.match(text, /"activeNodes":0/);
  await reader.cancel(); controller.abort();
});
