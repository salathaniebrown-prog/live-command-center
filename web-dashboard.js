const http = require('http');
const fs = require('fs');

const PORT = 8080;

const HTML = `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Astra Enterprise Core</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #070b14; color: #00f0ff; font-family: monospace; height: 100vh; display: flex; flex-direction: column; justify-content: space-between; padding: 14px; overflow: hidden; }
  .header { border: 1px solid #00f0ff; padding: 10px; text-align: center; background: rgba(0, 240, 255, 0.05); }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; flex: 1; margin: 10px 0; }
  .card { border: 1px solid #1e3a5f; background: #0c1424; padding: 12px; display: flex; flex-direction: column; justify-content: center; }
  .label { color: #7f9cf5; font-size: 0.85rem; margin-bottom: 4px; }
  .val { font-size: 1.2rem; font-weight: bold; color: #e2e8f0; }
  .footer { border-top: 1px solid #1e3a5f; padding-top: 8px; font-size: 0.8rem; color: #64748b; text-align: center; }
</style>
</head>
<body>
  <div class="header"><strong>ASTRA ENTERPRISE CORE :: TELEMETRY SPINE</strong></div>
  <div class="grid">
    <div class="card"><div class="label">RAM USAGE</div><div class="val" id="ram">--</div></div>
    <div class="card"><div class="label">CPU LOAD</div><div class="val" id="load">--</div></div>
    <div class="card"><div class="label">BATTERY / TEMP</div><div class="val" id="batt">--</div></div>
    <div class="card"><div class="label">LOG BUFFER</div><div class="val" id="log">--</div></div>
    <div class="card"><div class="label">PYTHON WORKER</div><div class="val" id="py">--</div></div>
    <div class="card"><div class="label">JAVA 21 WORKER</div><div class="val" id="java">--</div></div>
  </div>
  <div class="footer" id="ts">Syncing live stream...</div>
<script>
  async function refresh() {
    try {
      const res = await fetch('/api/telemetry');
      const d = await res.json();
      document.getElementById('ram').textContent = d.ram;
      document.getElementById('load').textContent = d.load;
      document.getElementById('batt').textContent = d.batt;
      document.getElementById('log').textContent = d.log;
      document.getElementById('py').textContent = d.py;
      document.getElementById('java').textContent = d.java;
      document.getElementById('ts').textContent = 'UTC: ' + d.time + ' | NET: ' + d.net;
    } catch {}
  }
  setInterval(refresh, 1000);
  refresh();
</script>
</body>
</html>`;

http.createServer((req, res) => {
  if (req.url === '/api/telemetry') {
    let payload = { ram: 'N/A', load: 'N/A', batt: 'N/A', log: '0 KB', py: 'WAITING', java: 'WAITING', net: '{}', time: new Date().toISOString() };
    try {
      if (fs.existsSync('telemetry_spine.jsonl')) {
        const lines = fs.readFileSync('telemetry_spine.jsonl', 'utf8').trim().split('\n');
        const recent = lines.slice(-30).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
        const node = [...recent].reverse().find(x => x.source === 'node-spine');
        const py = [...recent].reverse().find(x => x.source === 'python-worker');
        const java = [...recent].reverse().find(x => x.source === 'java-worker');
        const kb = (fs.statSync('telemetry_spine.jsonl').size / 1024).toFixed(1);

        if (node) {
          payload.ram = `${node.memory.usedMB} / ${node.memory.totalMB} MB`;
          payload.load = node.loadAvg.map(n => n.toFixed(2)).join(' | ');
          payload.batt = `${node.battery.percentage}% (${node.battery.tempC}°C)`;
          payload.net = JSON.stringify(node.network);
        }
        payload.log = `${kb} / 5120 KB`;
        if (py) payload.py = `${py.status} (${py.data?.tasks_completed ?? 0})`;
        if (java) payload.java = `${java.status} (${java.cycle ?? 0})`;
      }
    } catch {}
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(payload));
  }
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end(HTML);
}).listen(PORT, '127.0.0.1', () => {
  console.log(`Web dashboard live at http://127.0.0.1:${PORT}`);
});
