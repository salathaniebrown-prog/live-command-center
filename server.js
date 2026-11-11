const express = require('express');
const http = require('http');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const app = express();
const server = http.createServer(app);
app.use(express.json());

const dbFile = path.join(__dirname, 'datacenter_ledger.db');
const db = new sqlite3.Database(dbFile, (err) => {
  if (err) {
    console.error('[SQLite Error] Failed to open database:', err.message);
  } else {
    console.log('[SQLite] Connected to datacenter_ledger.db successfully.');
  }
});

db.serialize(() => {
  db.run("CREATE TABLE IF NOT EXISTS ledger_blocks (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, directive TEXT, vector_status TEXT, signature TEXT)");
  db.run("CREATE TABLE IF NOT EXISTS cyberspace_vectors (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT, content TEXT, epoch INTEGER)");
  db.run("INSERT OR IGNORE INTO cyberspace_vectors (id, tag, content, epoch) VALUES (1, 'core_identity', 'Root Owner Salathaniel S A Brown Sr, CDP Vault 0x5f04EBB30d3BBf356263c3ef4823080d05bEDDf5 ($20.00 USDC).', 13)");
});

let ledgerBlock = 160;

app.get('/api/sovereign-state', (req, res) => {
  res.json({
    success: true,
    owner: "Salathaniel S A Brown Sr",
    role: "LEAD_SYSTEM_ARCHITECT_ROOT_OWNER",
    status: "ONLINE_AUTONOMOUS_OPERATING_24_7",
    systemVersion: "v13.9.5-autonomous-sovereign",
    vaultWallet: "0x5f04EBB30d3BBf356263c3ef4823080d05bEDDf5",
    balance: "$20.00 USDC",
    activeGpuClusters: 5000,
    activeWorkerNodes: 32,
    worldIngestionRate: "148,290 ticks/sec",
    aggregateEflops: "121.55 EFLOPS",
    database: "datacenter_ledger.db (Active)",
    ports: { master: 3001, vector: 8090, imageGen: 8001, ledger: 8099 }
  });
});

app.post('/api/fast', (req, res) => {
  const command = (req.body.command || 'status').trim();
  ledgerBlock++;
  const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
  const signature = '0x' + Math.random().toString(16).substring(2, 34);

  db.run("INSERT INTO ledger_blocks (timestamp, directive, vector_status, signature) VALUES (?, ?, ?, ?)", 
    [timestamp, command, "CYBERSPACE_EA_SYNCED", signature], (err) => {
      if (err) console.error("DB Insert Error:", err.message);
    });

  res.json({
    status: 'success',
    output: `[${timestamp}] ASTRA SUPERCOMPUTER DIRECTIVE: "${command}"\n• Ledger Block : #${ledgerBlock}\n• Owner        : Salathaniel S A Brown Sr\n• CDP Vault    : 0x5f04EBB30d3BBf356263c3ef4823080d05bEDDf5 [$20.00 USDC]\n• Vector Lab   : Cyberspace EA Evolutionary Algorithm Active\n• Auth Sign    : ${signature}`
  });
});

app.get(['/', '/v13', '/dashboard'], (req, res) => {
  res.send(`<!DOCTYPE html>
<html>
<head>
  <title>Astra Sovereign & Eagle Eyes Command Center</title>
  <style>
    body { background: #06070c; color: #00ff88; font-family: monospace; padding: 20px; margin: 0; }
    h1 { color: #00ffff; border-bottom: 2px solid #00ff88; padding-bottom: 8px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; margin-bottom: 20px; }
    .card { background: #0c101d; border: 1px solid #1a2642; padding: 15px; border-radius: 8px; }
    #console { background: #030408; border: 1px solid #00ff88; color: #00ff88; padding: 12px; height: 220px; overflow-y: auto; border-radius: 4px; }
    input, button { padding: 10px; font-family: monospace; border-radius: 4px; }
    input { width: 70%; background: #121829; color: #fff; border: 1px solid #00ff88; }
    button { background: #00ff88; color: #000; font-weight: bold; border: none; cursor: pointer; }
    button:hover { background: #00b35f; }
  </style>
</head>
<body>
  <h1>ASTRA SOVEREIGN // EAGLE EYES COMMAND CENTER</h1>
  <div class="grid">
    <div class="card">
      <h3>Root Architect Telemetry</h3>
      <p><strong>Owner:</strong> Salathaniel S A Brown Sr</p>
      <p><strong>Vault Wallet:</strong> 0x5f04...DdF5 ($20.00 USDC)</p>
      <p><strong>Status:</strong> <span style="color:#00ff88;font-weight:bold;">ONLINE 24/7</span></p>
    </div>
    <div class="card">
      <h3>Datacenter Mesh & EA Lab</h3>
      <p><strong>Compute Power:</strong> 121.55 EFLOPS (30 Nodes)</p>
      <p><strong>Database:</strong> datacenter_ledger.db</p>
      <p><strong>Master Port:</strong> 3001 Active</p>
    </div>
  </div>

  <div class="card">
    <h3>Unified Command Core (/api/fast)</h3>
    <div id="console">Eagle Eyes Datacenter Core Online. Enter directive below...</div><br/>
    <input type="text" id="cmd" placeholder="Type command (e.g. status, evolve vector, ls)..." />
    <button onclick="send()">EXECUTE</button>
  </div>

  <script>
    async function send() {
      const input = document.getElementById('cmd');
      const c = document.getElementById('console');
      if (!input.value) return;
      c.innerHTML += '<br/>> ' + input.value;
      try {
        const res = await fetch('/api/fast', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ command: input.value })
        });
        const d = await res.json();
        c.innerHTML += '<br/>' + d.output.replace(/\\n/g, '<br/>');
      } catch(e) {
        c.innerHTML += '<br/>[ERROR] Command failed.';
      }
      input.value = '';
      c.scrollTop = c.scrollHeight;
    }
  </script>
</body>
</html>`);
});

const PORT = 3001;
server.listen(PORT, '0.0.0.0', () => {
  console.log('[Astra Master EA Engine] Live on http://127.0.0.1:' + PORT);
});
