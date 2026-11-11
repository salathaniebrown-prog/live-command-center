const http = require('http');
const fs = require('fs');

const PORT = 8080;

const HTML = fs.readFileSync("dashboard.html", "utf8");

http.createServer((req, res) => {

  if (req.method === "POST" && req.url === "/api/control") {
    let body = "";
    req.on("data", chunk => body += chunk);
    req.on("end", () => {
      try {
        const cmd = JSON.parse(body);
        const { exec } = require("child_process");
        if (cmd.action === "rotate_logs") exec("gzip -f *.log 2>/dev/null || true");
        if (cmd.action === "pulse_workers") exec("pkill -USR1 -f python_worker.py 2>/dev/null || true");
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, executed: cmd.action, model: cmd.model || null }));
      } catch (e) {
        res.writeHead(400); res.end(JSON.stringify({ ok: false }));
      }
    });
    return;
  }

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
  res.end(HTML);
}).listen(PORT, '127.0.0.1', () => {
  console.log(`Web dashboard live at http://127.0.0.1:${PORT}`);
});
