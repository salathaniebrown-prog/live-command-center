const handleControl = require("./control-api.js");
const http = require('http');
const fs = require('fs');

const PORT = 8080;

const HTML = fs.readFileSync("dashboard.html", "utf8");

http.createServer((req, res) => {

  if (req.method === "POST" && req.url === "/api/control") return handleControl(req, res);

  if (req.url === "/api/export") { res.writeHead(200, {"Content-Type":"application/jsonl","Content-Disposition":"attachment; filename=astra_telemetry.jsonl"}); return res.end(fs.existsSync("telemetry_spine.jsonl") ? fs.readFileSync("telemetry_spine.jsonl") : ""); }
  if (req.url === "/api/health") { res.writeHead(200, {"Content-Type":"application/json"}); return res.end(JSON.stringify({ok:true, status:"healthy"})); }
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
  res.end(fs.readFileSync("dashboard.html","utf8"));
}).listen(PORT, '127.0.0.1', () => {
  console.log(`Web dashboard live at http://127.0.0.1:${PORT}`);
});
