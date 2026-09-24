const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.env.PORT || 8080);
const HOST = '0.0.0.0';
const API_BASE = String(process.env.API_BASE || '').trim().replace(/\/+$/, '');
const CHAOS_AUDIT_URL = String(process.env.CHAOS_AUDIT_URL || '').trim();
const STATIC_DIR = path.join(__dirname, 'static');
const ALLOWED = new Set(['/api/status','/api/metrics','/api/health','/api/deployment']);
const MAX_CHAOS_EVENTS = 50;

function sendJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': body.length,
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
    'referrer-policy': 'no-referrer'
  });
  res.end(body);
}

function sendFile(res, filePath, contentType='text/html; charset=utf-8') {
  fs.readFile(filePath, (err, data) => {
    if (err) return sendJson(res, 404, { error: 'not found' });
    res.writeHead(200, {
      'content-type': contentType,
      'content-length': data.length,
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      'referrer-policy': 'no-referrer'
    });
    res.end(data);
  });
}

function envValue(name) {
  const value = String(process.env[name] || '').trim();
  return value || null;
}

function runtimeEvidence() {
  const mem = process.memoryUsage();
  return {
    verifiedAt: new Date().toISOString(),
    source: 'railway-provided-runtime-environment',
    railway: {
      project: envValue('RAILWAY_PROJECT_NAME'),
      environment: envValue('RAILWAY_ENVIRONMENT_NAME'),
      service: envValue('RAILWAY_SERVICE_NAME'),
      region: envValue('RAILWAY_REPLICA_REGION'),
      publicDomain: envValue('RAILWAY_PUBLIC_DOMAIN')
    },
    git: {
      repositoryOwner: envValue('RAILWAY_GIT_REPO_OWNER'),
      repositoryName: envValue('RAILWAY_GIT_REPO_NAME'),
      branch: envValue('RAILWAY_GIT_BRANCH'),
      commitSha: envValue('RAILWAY_GIT_COMMIT_SHA')
    },
    process: {
      nodeVersion: process.version,
      uptimeSeconds: Math.floor(process.uptime()),
      rssBytes: mem.rss,
      heapUsedBytes: mem.heapUsed
    },
    policy: {
      mode: 'read-only',
      realOnly: true,
      writeRoutesExposed: false
    }
  };
}

function observerPolicy() {
  return {
    version: 'verified-runtime-v2-chaos-observer',
    mode: 'observation-only',
    realOnly: true,
    automaticRecovery: false,
    chaosAuditConfigured: Boolean(CHAOS_AUDIT_URL),
    controls: {
      dockerSocket: false,
      privilegedContainer: false,
      hostNetworkMutation: false,
      firewallMutation: false,
      nginxReload: false,
      pciRegisterWrites: false,
      processRestart: false,
      deploymentWrites: false
    },
    recommendationMode: 'human-approval-required'
  };
}

function safeString(value, max=160) {
  if (value === null || value === undefined) return null;
  const text = String(value).replace(/[\r\n\t]+/g, ' ').trim();
  return text ? text.slice(0, max) : null;
}

function recommendationFor(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'SLA_BREACH' || s === 'CRITICAL' || s === 'FAILED') {
    return 'Inspect health, deployment, and network evidence. Require human approval before any recovery action.';
  }
  if (s === 'RESOLVED' || s === 'OK' || s === 'HEALTHY' || s === 'SUCCESS') {
    return 'No recovery action recommended. Preserve the observation for audit history.';
  }
  return 'Observe and verify the source before deciding on any action.';
}

function normalizeChaosEvent(event) {
  const durationRaw = event && (
    event.recoveryDurationSeconds ??
    event.recovery_duration_seconds ??
    event['Recovery Duration (s)']
  );
  const duration = Number(durationRaw);
  const status = safeString(event && (event.status ?? event['SLA Status']), 64);
  return {
    time: safeString(event && (event.time ?? event.timestamp ?? event.Time), 80),
    eventType: safeString(event && (event.eventType ?? event.event_type ?? event['Attack Event Type']), 120),
    targetInterface: safeString(event && (event.targetInterface ?? event.target_interface ?? event['Target Interface']), 120),
    recoveryDurationSeconds: Number.isFinite(duration) ? duration : null,
    status,
    recommendation: recommendationFor(status)
  };
}

async function fetchJson(url, timeoutMs=5000) {
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'accept': 'application/json', 'user-agent': 'Eagle-Eyes-Chaos-Observer/2.0' },
    signal: AbortSignal.timeout(timeoutMs)
  });
  const contentType = response.headers.get('content-type') || '';
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (!contentType.includes('application/json')) throw new Error('source did not return JSON');
  return response.json();
}

async function chaosEvents() {
  if (!CHAOS_AUDIT_URL) {
    return {
      configured: false,
      source: null,
      events: [],
      note: 'CHAOS_AUDIT_URL is not configured; no chaos events are inferred or fabricated.'
    };
  }

  const parsed = new URL(CHAOS_AUDIT_URL);
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('CHAOS_AUDIT_URL must use http or https');
  }

  const payload = await fetchJson(parsed.toString());
  const rows = Array.isArray(payload) ? payload : (Array.isArray(payload.events) ? payload.events : []);
  return {
    configured: true,
    source: parsed.origin,
    events: rows.slice(0, MAX_CHAOS_EVENTS).map(normalizeChaosEvent)
  };
}

async function upstreamObservation(pathname) {
  if (!API_BASE) return { configured: false, ok: false, httpStatus: null };
  try {
    const response = await fetch(API_BASE + pathname, {
      method: 'GET',
      headers: { 'accept': 'application/json', 'user-agent': 'Eagle-Eyes-Chaos-Observer/2.0' },
      signal: AbortSignal.timeout(5000)
    });
    return { configured: true, ok: response.ok, httpStatus: response.status };
  } catch {
    return { configured: true, ok: false, httpStatus: null };
  }
}

async function observerSnapshot() {
  const [health, status, deployment] = await Promise.all([
    upstreamObservation('/api/health'),
    upstreamObservation('/api/status'),
    upstreamObservation('/api/deployment')
  ]);

  const observations = { health, status, deployment };
  const failing = Object.entries(observations).filter(([, value]) => value.configured && !value.ok).map(([key]) => key);

  return {
    observedAt: new Date().toISOString(),
    source: 'read-only-upstream-http-observation',
    observations,
    recommendation: failing.length
      ? `Review ${failing.join(', ')} evidence and logs before any manual recovery action.`
      : 'No recovery action recommended from the current HTTP observations.'
  };
}

async function proxyGet(req, res, pathname) {
  if (!ALLOWED.has(pathname)) return sendJson(res, 403, { error: 'endpoint not allowed', path: pathname });
  if (!API_BASE) return sendJson(res, 503, { error: 'API_BASE is not configured', path: pathname });
  try {
    const upstream = await fetch(API_BASE + pathname, {
      method: 'GET',
      headers: { 'accept': 'application/json', 'user-agent': 'Salathaniel-Command-Dashboard/2.0' },
      signal: AbortSignal.timeout(8000)
    });
    const body = Buffer.from(await upstream.arrayBuffer());
    res.writeHead(upstream.status, {
      'content-type': upstream.headers.get('content-type') || 'application/json',
      'content-length': body.length,
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff'
    });
    res.end(body);
  } catch (err) {
    sendJson(res, 502, { error: 'upstream unavailable', detail: String(err && err.message || err), path: pathname });
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = url.pathname;

  if (req.method !== 'GET') return sendJson(res, 405, { error: 'read-only dashboard' });

  if (pathname === '/dashboard-health' || pathname === '/dashboard_health') {
    return sendJson(res, 200, {
      ok: true,
      service: 'railway-visual-dashboard',
      version: 'verified-runtime-v2-chaos-observer',
      mode: 'read-only',
      realOnly: true,
      upstreamConfigured: Boolean(API_BASE),
      chaosAuditConfigured: Boolean(CHAOS_AUDIT_URL)
    });
  }

  if (pathname === '/runtime-evidence') {
    return sendJson(res, 200, runtimeEvidence());
  }

  if (pathname === '/observer-policy') {
    return sendJson(res, 200, observerPolicy());
  }

  if (pathname === '/observer-snapshot') {
    return sendJson(res, 200, await observerSnapshot());
  }

  if (pathname === '/chaos-events') {
    try {
      return sendJson(res, 200, await chaosEvents());
    } catch (err) {
      return sendJson(res, 502, {
        configured: Boolean(CHAOS_AUDIT_URL),
        events: [],
        error: 'chaos audit source unavailable',
        detail: String(err && err.message || err)
      });
    }
  }

  if (pathname === '/dashboard-meta') {
    return sendJson(res, 200, {
      name: 'Eagle Eyes Command Center',
      version: 'Verified Runtime V2 — Chaos Observer',
      mode: 'read-only',
      realOnly: true,
      evidencePath: '/runtime-evidence',
      observerPolicyPath: '/observer-policy',
      observerSnapshotPath: '/observer-snapshot',
      chaosEventsPath: '/chaos-events',
      allowedApiPaths: [...ALLOWED]
    });
  }

  if (pathname.startsWith('/api/')) return proxyGet(req, res, pathname);

  if (pathname === '/' || pathname === '/index.html') {
    return sendFile(res, path.join(STATIC_DIR, 'index.html'));
  }

  return sendJson(res, 404, { error: 'not found' });
});

server.listen(PORT, HOST, () => {
  console.log(`dashboard listening on ${HOST}:${PORT}`);
  console.log(`upstream configured: ${Boolean(API_BASE)}`);
  console.log(`chaos audit configured: ${Boolean(CHAOS_AUDIT_URL)}`);
  console.log('runtime evidence source: railway-provided-runtime-environment');
  console.log('chaos observer mode: observation-only');
});
