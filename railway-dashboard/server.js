const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.env.PORT || 8080);
const HOST = '0.0.0.0';
const API_BASE = String(process.env.API_BASE || '').trim().replace(/\/+$/, '');
const STATIC_DIR = path.join(__dirname, 'static');
const ALLOWED = new Set(['/api/status','/api/metrics','/api/health','/api/deployment']);

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

async function proxyGet(req, res, pathname) {
  if (!ALLOWED.has(pathname)) return sendJson(res, 403, { error: 'endpoint not allowed', path: pathname });
  if (!API_BASE) return sendJson(res, 503, { error: 'API_BASE is not configured', path: pathname });
  try {
    const upstream = await fetch(API_BASE + pathname, {
      method: 'GET',
      headers: { 'accept': 'application/json', 'user-agent': 'Salathaniel-Command-Dashboard/1.0' },
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

  if (pathname === '/dashboard-health') {
    return sendJson(res, 200, {
      ok: true,
      service: 'railway-visual-dashboard',
      mode: 'read-only',
      realOnly: true,
      upstreamConfigured: Boolean(API_BASE)
    });
  }

  if (pathname === '/dashboard-meta') {
    return sendJson(res, 200, {
      name: 'Salathaniel Command Center',
      mode: 'read-only',
      realOnly: true,
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
});
