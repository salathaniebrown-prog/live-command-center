const http = require('http');
const os = require('os');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const PORT = process.env.DASHBOARD_PORT || 8088;
const TELEMETRY_PORT = process.env.PORT || 8080;
const SECRET_KEY = process.env.TELEMETRY_SECRET || 'eagle-eyes-secure-telemetry-key';
const DB_PATH = process.env.TELEMETRY_DB || path.join(__dirname, 'telemetry_ledger.db');

function hasSqlite3Cli() {
  try {
    execFileSync('sqlite3', ['--version'], { stdio: 'ignore' });
    return true;
  } catch (_) {
    return false;
  }
}

const USE_SQLITE = hasSqlite3Cli();

function initLedger() {
  if (USE_SQLITE) {
    execFileSync('sqlite3', [
      DB_PATH,
      `CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        polled_at INTEGER NOT NULL,
        online INTEGER NOT NULL,
        signature_valid INTEGER NOT NULL,
        node_id INTEGER,
        hostname TEXT,
        uptime_sec REAL,
        mem_free INTEGER,
        mem_total INTEGER,
        mem_usage_pct TEXT,
        payload_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_snapshots_polled_at ON snapshots(polled_at DESC);`
    ]);
  } else {
    if (!fs.existsSync(DB_PATH)) {
      fs.writeFileSync(DB_PATH, '', 'utf8');
    }
  }
}

function sqlQuote(val) {
  if (val === null || val === undefined) return 'NULL';
  if (typeof val === 'number') return Number.isFinite(val) ? String(val) : 'NULL';
  return `'${String(val).replace(/'/g, "''")}'`;
}

function recordSnapshot(record) {
  if (USE_SQLITE) {
    const d = record.data || {};
    const mem = d.memory || {};
    const sql = `INSERT INTO snapshots (
      polled_at, online, signature_valid, node_id, hostname, uptime_sec, mem_free, mem_total, mem_usage_pct, payload_json
    ) VALUES (
      ${sqlQuote(record.polledAt)},
      ${sqlQuote(record.online ? 1 : 0)},
      ${sqlQuote(record.signatureValid ? 1 : 0)},
      ${sqlQuote(d.nodeId ?? null)},
      ${sqlQuote(d.hostname ?? null)},
      ${sqlQuote(d.uptime ?? null)},
      ${sqlQuote(mem.free ?? null)},
      ${sqlQuote(mem.total ?? null)},
      ${sqlQuote(mem.usagePct ?? null)},
      ${sqlQuote(JSON.stringify(record))}
    );`;
    execFileSync('sqlite3', [DB_PATH, sql]);
  } else {
    fs.appendFileSync(DB_PATH, JSON.stringify(record) + '\n', 'utf8');
  }
}

function queryHistory(limit = 50) {
  const safeLimit = Math.max(1, Math.min(250, Number(limit) || 50));
  if (USE_SQLITE) {
    const raw = execFileSync('sqlite3', [
      '-json',
      DB_PATH,
      `SELECT id, polled_at, online, signature_valid, node_id, hostname, uptime_sec, mem_free, mem_total, mem_usage_pct
       FROM snapshots ORDER BY id DESC LIMIT ${safeLimit};`
    ], { encoding: 'utf8' }).trim();
    return raw ? JSON.parse(raw) : [];
  }
  if (!fs.existsSync(DB_PATH)) return [];
  const lines = fs.readFileSync(DB_PATH, 'utf8').trim().split('\n').filter(Boolean);
  return lines.slice(-safeLimit).reverse().map((line, idx) => {
    try {
      const r = JSON.parse(line);
      const d = r.data || {};
      const mem = d.memory || {};
      return {
        id: lines.length - idx,
        polled_at: r.polledAt,
        online: r.online ? 1 : 0,
        signature_valid: r.signatureValid ? 1 : 0,
        node_id: d.nodeId ?? null,
        hostname: d.hostname ?? null,
        uptime_sec: d.uptime ?? null,
        mem_free: mem.free ?? null,
        mem_total: mem.total ?? null,
        mem_usage_pct: mem.usagePct ?? null
      };
    } catch (_) {
      return null;
    }
  }).filter(Boolean);
}

function fetchTelemetry() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${TELEMETRY_PORT}/`, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        try {
          resolve({
            online: res.statusCode === 200,
            signature: res.headers['x-telemetry-signature'] || null,
            data: JSON.parse(body)
          });
        } catch (err) {
          resolve({ online: false, error: err.message, data: null });
        }
      });
    });
    req.on('error', (err) => {
      resolve({ online: false, error: err.message, data: null });
    });
    req.setTimeout(2000, () => {
      req.destroy();
      resolve({ online: false, error: 'timeout', data: null });
    });
  });
}

async function pollAndPersist() {
  const snap = await fetchTelemetry();
  let signatureValid = false;
  if (snap.online && snap.data && snap.signature) {
    const expected = crypto
      .createHmac('sha256', SECRET_KEY)
      .update(JSON.stringify(snap.data))
      .digest('hex');
    try {
      signatureValid = crypto.timingSafeEqual(
        Buffer.from(snap.signature, 'utf8'),
        Buffer.from(expected, 'utf8')
      );
    } catch (_) {
      signatureValid = false;
    }
  }
  const record = {
    ...snap,
    signatureValid,
    dashboardHost: os.hostname(),
    polledAt: Date.now()
  };
  try {
    recordSnapshot(record);
  } catch (err) {
    console.error('[LEDGER] Write error:', err.message);
  }
  return record;
}

function renderHtml() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Eagle Eyes Command Center</title>
<style>
  :root {
    --bg: #0b0f14;
    --panel: #131a24;
    --border: #233042;
    --text: #e6edf3;
    --muted: #8b9bb0;
    --accent: #38bdf8;
    --ok: #22c55e;
    --warn: #f59e0b;
    --bad: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    padding: 20px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 14px;
    margin-bottom: 20px;
  }
  h1 { font-size: 1.2rem; letter-spacing: 0.06em; color: var(--accent); }
  .meta-strip { font-size: 0.78rem; color: var(--muted); }
  .badge {
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 700;
    border: 1px solid var(--border);
  }
  .online { color: var(--ok); border-color: rgba(34,197,94,0.4); background: rgba(34,197,94,0.08); }
  .offline { color: var(--bad); border-color: rgba(239,68,68,0.4); background: rgba(239,68,68,0.08); }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px;
    margin-bottom: 18px;
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }
  .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; margin-bottom: 6px; }
  .val { font-size: 1.35rem; font-weight: 700; }
  .sub { font-size: 0.8rem; color: var(--muted); margin-top: 6px; word-break: break-all; }
  .bar-wrap {
    height: 10px;
    background: #0b0f14;
    border-radius: 999px;
    overflow: hidden;
    margin-top: 10px;
    border: 1px solid var(--border);
  }
  .bar { height: 100%; background: var(--accent); width: 0%; transition: width 0.3s ease; }
  .section-title {
    font-size: 0.85rem;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 18px 0 8px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    font-size: 0.78rem;
  }
  th, td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    white-space: nowrap;
  }
  th { color: var(--muted); background: #0f151e; }
  .tbl-wrap { overflow-x: auto; }
  pre {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    overflow-x: auto;
    font-size: 0.8rem;
    line-height: 1.45;
  }
</style>
</head>
<body>
  <header>
    <div>
      <h1>EAGLE EYES // LIVE COMMAND CENTER</h1>
      <div class="meta-strip">Ledger: ${path.basename(DB_PATH)} (${USE_SQLITE ? 'SQLite' : 'JSONL fallback'}) | Route: /api/telemetry, /api/history</div>
    </div>
    <div id="statusBadge" class="badge offline">CONNECTING...</div>
  </header>

  <div class="grid">
    <div class="card">
      <div class="label">Telemetry Node</div>
      <div id="nodeVal" class="val">--</div>
      <div id="nodeSub" class="sub">Port ${TELEMETRY_PORT}</div>
    </div>
    <div class="card">
      <div class="label">System Memory Usage</div>
      <div id="memVal" class="val">--</div>
      <div class="bar-wrap"><div id="memBar" class="bar"></div></div>
      <div id="memSub" class="sub">--</div>
    </div>
    <div class="card">
      <div class="label">Uptime & Load</div>
      <div id="upVal" class="val">--</div>
      <div id="loadSub" class="sub">Load: --</div>
    </div>
    <div class="card">
      <div class="label">HMAC Signature</div>
      <div id="sigState" class="val">--</div>
      <div id="sigSub" class="sub">--</div>
    </div>
  </div>

  <div class="section-title">Persisted Telemetry Snapshots</div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Time</th>
          <th>State</th>
          <th>PID</th>
          <th>Mem %</th>
          <th>Uptime</th>
          <th>HMAC</th>
        </tr>
      </thead>
      <tbody id="historyRows">
        <tr><td colspan="7">Loading snapshots...</td></tr>
      </tbody>
    </table>
  </div>

  <div class="section-title">Latest Payload</div>
  <pre id="rawJson">Loading live telemetry stream...</pre>

<script>
async function refresh() {
  try {
    const [tRes, hRes] = await Promise.all([
      fetch('/api/telemetry', { cache: 'no-store' }),
      fetch('/api/history?limit=25', { cache: 'no-store' })
    ]);
    const payload = await tRes.json();
    const history = await hRes.json();

    const badge = document.getElementById('statusBadge');
    const raw = document.getElementById('rawJson');

    if (payload.online && payload.data) {
      badge.textContent = 'STREAM ONLINE';
      badge.className = 'badge online';

      document.getElementById('nodeVal').textContent = 'PID ' + payload.data.nodeId;
      document.getElementById('nodeSub').textContent = 'Host: ' + payload.data.hostname;

      const pct = parseFloat(payload.data.memory.usagePct) || 0;
      document.getElementById('memVal').textContent = payload.data.memory.usagePct;
      document.getElementById('memBar').style.width = Math.min(100, Math.max(0, pct)) + '%';
      const freeMb = (payload.data.memory.free / 1048576).toFixed(0);
      const totalMb = (payload.data.memory.total / 1048576).toFixed(0);
      document.getElementById('memSub').textContent = freeMb + ' MB free / ' + totalMb + ' MB total';

      const upSec = Math.floor(payload.data.uptime || 0);
      const mins = Math.floor(upSec / 60);
      const secs = upSec % 60;
      document.getElementById('upVal').textContent = mins + 'm ' + secs + 's';
      document.getElementById('loadSub').textContent = 'Load: ' + (payload.data.loadAverage || []).map(n => n.toFixed(2)).join(' | ');

      document.getElementById('sigState').textContent = payload.signatureValid ? 'VERIFIED' : 'UNVERIFIED';
      document.getElementById('sigState').style.color = payload.signatureValid ? '#22c55e' : '#f59e0b';
      document.getElementById('sigSub').textContent = payload.signature ? payload.signature.slice(0, 32) + '...' : 'No header';
    } else {
      badge.textContent = 'NODE OFFLINE';
      badge.className = 'badge offline';
      document.getElementById('nodeVal').textContent = 'OFFLINE';
      document.getElementById('nodeSub').textContent = payload.error || 'Unreachable';
    }

    const tbody = document.getElementById('historyRows');
    if (Array.isArray(history.rows) && history.rows.length > 0) {
      tbody.innerHTML = history.rows.map(r => {
        const ts = new Date(r.polled_at).toLocaleTimeString();
        const up = r.uptime_sec != null ? Math.floor(r.uptime_sec) + 's' : '--';
        return '<tr>' +
          '<td>' + r.id + '</td>' +
          '<td>' + ts + '</td>' +
          '<td>' + (r.online ? 'ONLINE' : 'OFFLINE') + '</td>' +
          '<td>' + (r.node_id ?? '--') + '</td>' +
          '<td>' + (r.mem_usage_pct ?? '--') + '</td>' +
          '<td>' + up + '</td>' +
          '<td>' + (r.signature_valid ? 'OK' : 'NO') + '</td>' +
        '</tr>';
      }).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="7">No snapshots recorded yet.</td></tr>';
    }

    raw.textContent = JSON.stringify(payload, null, 2);
  } catch (err) {
    const badge = document.getElementById('statusBadge');
    badge.textContent = 'DASHBOARD ERR';
    badge.className = 'badge offline';
  }
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>`;
}

initLedger();

const server = http.createServer(async (req, res) => {
  const urlObj = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (urlObj.pathname === '/api/telemetry') {
    const record = await pollAndPersist();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(record, null, 2));
    return;
  }

  if (urlObj.pathname === '/api/history') {
    const limit = urlObj.searchParams.get('limit') || '50';
    const rows = queryHistory(limit);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      engine: USE_SQLITE ? 'sqlite3' : 'jsonl',
      dbPath: DB_PATH,
      count: rows.length,
      rows
    }, null, 2));
    return;
  }

  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(renderHtml());
});

server.on('error', (err) => {
  console.error('[DASHBOARD] Listen error:', err.code || err.message);
  process.exit(1);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[DASHBOARD] Eagle Eyes UI active on http://127.0.0.1:${PORT} (${USE_SQLITE ? 'SQLite' : 'JSONL'} -> ${DB_PATH})`);
});
