import os, json, socketserver, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

socketserver.TCPServer.allow_reuse_address = True
HOME = os.path.expanduser("~")
APPS_DIR = os.path.join(HOME, "astra-ownable-apps")

ROUTES = {
    "/api/legal/": 8095, "/api/brain/": 8096, "/api/ooda/": 8097, "/api/bi/": 8098,
    "/dealership": 8099, "/api/state": 8099, "/api/acquire": 8099, "/api/advance": 8099,
    "/api/reset": 8099, "/api/add_vehicle": 8099, "/api/set_webhook": 8099, "/api/receipt/": 8099,
    "/api/nexus/": 8100, "/api/os/": 8101, "/api/wf/": 8102, "/api/geo/": 8103,
    "/api/osint/": 8104, "/api/re/": 8105, "/api/ent/": 8106, "/api/seo/": 8107,
    "/api/pro/": 8108, "/api/auto/": 8109
}

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASTRA SOVEREIGN OS // UNIFIED COMMAND CENTER</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:10px;background:#03070d;color:#e6f9ff;font-family:monospace}
.hdr{display:flex;justify-content:space-between;align-items:center;border:1px solid #00f0ff66;background:#061320;padding:10px;margin-bottom:10px}
.card{border:1px solid #00f0ff55;background:#050f1a;padding:10px;margin-bottom:10px}
.card h3{margin:0 0 8px;font-size:13px;color:#39ff14;border-bottom:1px solid #00f0ff33;padding-bottom:4px}
.row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
input,select{flex:1;min-width:140px;background:#02060b;border:1px solid #00f0ff66;color:#fff;padding:7px;font-family:monospace;font-size:12px}
button{background:#00f0ff22;border:1px solid #00f0ff;color:#00f0ff;padding:7px 10px;font-family:monospace;font-weight:bold;font-size:11px;cursor:pointer}
button.g{background:#39ff1422;border-color:#39ff14;color:#39ff14}
button.a{background:#ffaa0022;border-color:#ffaa00;color:#ffaa00}
pre{background:#02060b;border:1px solid #00f0ff33;padding:8px;font-size:11px;color:#a8f9ff;white-space:pre-wrap;max-height:160px;overflow:auto;margin:6px 0 0}
iframe{width:100%;height:520px;border:1px solid #39ff1455;background:#03080f}
</style></head><body>
<div class="hdr"><strong style="color:#00f0ff">ASTRA SOVEREIGN OS // HTTPS &amp; LOCAL UNIFIED COMMAND</strong><span id="sys-stat" style="color:#39ff14;font-size:11px">CHECKING 15 NODES...</span></div>

<div class="card"><h3>1. AUTO-ASTRA AUTONOMOUS GOAL, MODEL &amp; SUPERCOMPUTER / PC ROUTER (PORT 8109)</h3>
<div class="row"><input id="auto-goal" placeholder="Enter real goal (e.g. Buy evening Wyler car, audit contract, build app, optimize Greensboro route)..."><button class="g" onclick="runAutoAstra()">AUTO-SELECT &amp; EXECUTE</button></div>

<div class="row"><select id="cl-tier" style="max-width:160px"><option value="PC">PC WORKSTATION</option><option value="SUPERCOMPUTER">8-GPU CLUSTER</option></select>
<input id="cl-url" placeholder="External PC / 8-GPU URL (e.g. http://192.168.1)...">
<button onclick="saveCluster()">SAVE COMPUTE NODE</button><button class="a" onclick="api('/api/reset',{}).then(()=>alert('Wyler Fleet Reset to AVAILABLE'))">RESET FLEET</button></div>
<pre id="auto-out">[AUTO-ASTRA READY] Picks Compute (Android Edge / PC / 8-GPU Supercomputer), Model &amp; Agent automatically.</pre></div>

<div class="card"><h3>2. ONE-PROMPT MULTI-MODEL STUDIO • CONTRACTOR LAWYER • 2-YR SPREADSHEET • REAL BENCHMARK (8108)</h3>
<div class="row"><select id="effort" style="max-width:130px"><option value="LOW">THINK: LOW</option><option value="MEDIUM">THINK: MEDIUM</option><option value="HIGH" selected>THINK: HIGH</option></select>
<input id="pro-in" placeholder="App prompt OR contract text to audit..."><button class="g" onclick="buildApp()">BUILD WORKING APP</button><button onclick="if(lastApp)window.open(lastApp,'_blank')">OPEN APP</button></div>
<div class="row"><button class="a" onclick="auditContract()">CONTRACTOR LAWYER</button><button onclick="window.location.href='/api/pro/csv'">DOWNLOAD 2-YR NUMBERS (.CSV)</button><button onclick="realBench()">REAL BENCHMARK</button><button class="g" onclick="window.open('/api/geo/manifest','_blank')">TRIAD ROUTE MANIFEST</button></div>
<pre id="pro-out">[STUDIO PRO READY] All routes relative &amp; HTTPS-tunnel safe.</pre></div>

<div class="card"><h3>3. WYLER &amp; DEALERSLINK CRYPTO DEALERSHIP (SAME-ORIGIN HTTPS PROXY)</h3>
<iframe src="/dealership/"></iframe></div>

<div class="card"><h3>4. GREENSBORO LOCATION INTEL • OSINT • ENTERPRISE SOC 2 / GDPR • BACKUPS</h3>
<div class="row"><input id="geo-addr" placeholder="Greensboro / Triad Address or OSINT Topic..."><button class="g" onclick="triadRoute()">OPTIMIZE TRIAD ROUTE</button><button onclick="osintGo()">HARVEST OSINT</button><button class="a" onclick="window.open('/api/ent/audit-report','_blank')">SOC 2 / GDPR REPORT</button><button onclick="backupNow()">BACKUP ALL DBS</button></div>
<pre id="ops-out">[ALL 15 NODES LINKED] Ready for live execution.</pre></div>

<script>
let lastApp = "";
async function api(url, body){
  const r = await fetch(url, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
  return await r.json();
}

async function saveCluster(){
  const tier = document.getElementById('cl-tier').value;
  const endpoint = document.getElementById('cl-url').value.trim();
  const d = await api('/api/auto/set-cluster', {tier, endpoint});
  document.getElementById('auto-out').innerText = '[COMPUTE CONFIGURED] ' + d.tier + ' -> ' + (endpoint || 'LOCAL_MESH');
}
async function runAutoAstra(){
  const goal = document.getElementById('auto-goal').value.trim() || 'Execute evening Wyler vehicle check & Greensboro route';
  document.getElementById('auto-out').innerText = '> Auto-Astra evaluating hardware, model & agent...';
  const d = await api('/api/auto/run', {goal});
  document.getElementById('auto-out').innerText = d.summary;
}
async function buildApp(){
  const prompt = document.getElementById('pro-in').value.trim() || 'Sovereign Fleet & Crypto App';
  const effort = document.getElementById('effort').value;
  const d = await api('/api/pro/app', {prompt, effort});
  lastApp = d.app_url || '';
  document.getElementById('pro-out').innerText = d.summary + ' -> Tap OPEN APP';
}
async function auditContract(){
  const text = document.getElementById('pro-in').value.trim() || 'Contractor agreement with indemnification, Net 60 payment, IP assignment, and termination clauses';
  const d = await api('/api/pro/contract', {text, effort: document.getElementById('effort').value});
  document.getElementById('pro-out').innerText = d.report;
}
async function realBench(){
  const d = await api('/api/pro/benchmark');
  document.getElementById('pro-out').innerText = '[' + d.verdict + ']\\n' + d.reality_check.join('\\n');
}
async function triadRoute(){
  const d = await api('/api/geo/route', {});
  document.getElementById('ops-out').innerText = 'TRIAD ROUTE: ' + d.total_miles + ' mi (~' + d.est_drive_minutes + ' min) | Gas $' + d.fuel_cost_usd + ' / EV $' + d.ev_cost_usd;
}
async function osintGo(){
  const query = document.getElementById('geo-addr').value.trim() || 'Greensboro North Carolina';
  const d = await api('/api/osint/harvest', {query});
  document.getElementById('ops-out').innerText = '[' + d.id + '] ' + d.summary;
}
async function backupNow(){
  const d = await api('/api/wf/backup', {});
  document.getElementById('ops-out').innerText = '[' + d.status + '] ' + d.snapshot + ' (' + d.dbs_backed_up + ' DBs backed up)';
}
api('/api/ent/visibility').then(d => { document.getElementById('sys-stat').innerText = 'LIVE NODES: ' + d.online_count + '/' + d.total_agents + ' ONLINE'; }).catch(()=>{});
</script></body></html>"""

class UnifiedHandler(BaseHTTPRequestHandler):
    def _proxy(self):
        H = ".".join(["127","0","0","1"])
        port = next((p for k, p in ROUTES.items() if self.path.startswith(k)), None)
        if not port: return False
        sub = self.path.replace("/dealership", "", 1) or "/"
        url = f"http://{H}:{port}{sub}"
        ln = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(ln) if (self.command == "POST" and ln > 0) else (b"{}" if self.command == "POST" else None)
        rq = urllib.request.Request(url, data=body, method=self.command)
        if body is not None: rq.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(rq, timeout=10) as r:
                data = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_response(502); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        return True

    def do_POST(self):
        if not self._proxy(): self.send_error(404)

    def do_GET(self):
        if self.path.startswith("/apps/"):
            rel = self.path[6:].split("?").strip("/")
            fp = os.path.join(APPS_DIR, rel)
            if os.path.isdir(fp): fp = os.path.join(fp, "index.html")
            if os.path.isfile(fp):
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
                self.wfile.write(open(fp, "rb").read()); return
            self.send_error(404, "App not found"); return
        if self._proxy(): return
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

HTTPServer(("0.0.0.0", 8088), UnifiedHandler).serve_forever()
