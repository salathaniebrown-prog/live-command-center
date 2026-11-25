const http = require('http');

const PROXY_PORT = process.env.PROXY_PORT || 8090;
const DASH_PORT = process.env.DASHBOARD_PORT || 8088;
const TELE_PORT = process.env.PORT || 8080;

function forward(req, res, targetPort, stripPrefix = '') {
  const forwardPath = stripPrefix && req.url.startsWith(stripPrefix)
    ? (req.url.slice(stripPrefix.length) || '/')
    : req.url;

  const proxyReq = http.request({
    hostname: '127.0.0.1',
    port: targetPort,
    path: forwardPath,
    method: req.method,
    headers: {
      ...req.headers,
      host: `127.0.0.1:${targetPort}`
    }
  }, (proxyRes) => {
    res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Upstream unavailable', detail: err.message }));
  });

  req.pipe(proxyReq);
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith('/telemetry-api')) {
    return forward(req, res, TELE_PORT, '/telemetry-api');
  }
  return forward(req, res, DASH_PORT, '/dashboard');
});

server.listen(PROXY_PORT, '0.0.0.0', () => {
  console.log(`[PROXY] Routing http://127.0.0.1:${PROXY_PORT}/dashboard -> :${DASH_PORT} and /telemetry-api -> :${TELE_PORT}`);
});
