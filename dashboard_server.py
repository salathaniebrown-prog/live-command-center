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
    "/api/pro/": 8108, "/api/auto/": 8109, "/api/telemetry/": 8110, "/api/jev/": 8111, "/v1/chat/completions": 8111
}

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASTRA + ALSTRA // JEV SYSTEM ONE COMMAND CENTER</title>
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
pre{background:#02060b;border:1px solid #00f0ff33;padding:8px;font-size:11px;color:#a8f9ff;white-space:pre-wrap;max-height:170px;overflow:auto;margin:6px 0 0}
iframe{width:100%;height:500px;border:1px solid #39ff1455;background:#03080f}
</style></head><body>
<div class="hdr"><strong style="color:#00f0ff">JEV SYSTEM ONE // ASTRA + ALSTRA UNIFIED BRAIN</strong><span id="sys-stat" style="color:#39ff14;font-size:11px">ONLINE</span></div>

<div class="card"><h3>0. JEV "SYSTEM ONE" PRIMARY INTENT ROUTER &amp; WORLD LIBRARY (PORT 8111)</h3>
<div class="row"><input id="jev-in" placeholder="Every prompt hits Jev first: Vault query, Email/Calendar tool, Invoice Agent, or Doctor/Lawyer/Inventor/Chronicles Library..."><button class="g" onclick="runJev()">ROUTE VIA JEV</button></div>
<div class="row"><input id="tf-key" type="password" placeholder="Typeface API Key (connects external route model)..."><button class="a" onclick="saveTfKey()">SAVE TYPEFACE KEY</button><button onclick="runJevPreset('World library for doctors, lawyers, inventors and historical chronicles')">WORLD LIBRARY</button><button onclick="runJevPreset('Generate client invoice and verify crypto escrow')">INVOICE AGENT</button></div>

<div class="row"><input id="jev-file" value="~/SYSTEM_MANIFEST.md" placeholder="Path to PDF, MD, JSON, or TXT guide for Jev to self-install..."><button class="g" onclick="ingestJevFile()">SELF-INSTALL FROM FILE/PDF</button><button onclick="window.location.href='/api/jev/template/medical'">MED TEMPLATE</button><button onclick="window.location.href='/api/jev/template/legal'">LEGAL TEMPLATE</button><button onclick="window.location.href='/api/jev/template/patent'">PATENT TEMPLATE</button></div>

<div class="row"><input id="feed-name" placeholder="Feed Label (e.g. Tech RSS / Crypto API)" style="max-width:190px"><input id="feed-url" placeholder="Paste any RSS, XML, JSON API, or GitHub feed URL..."><button class="g" onclick="addLiveFeed()">CONNECT FEED</button><button class="a" onclick="syncAllFeeds()">SYNC ALL FEEDS</button></div>

<div class="row"><select id="jev-feed-preset" onchange="document.getElementById('jev-feed-url').value=this.value" style="max-width:170px">
<option value="https://hnrss.org">TECH / AI LIVE FEED</option>
<option value="https://coinbase.com">COINBASE ETH SPOT</option>
<option value="https://reddit.com">GREENSBORO NC FEED</option>
</select><input id="jev-feed-url" value="https://hnrss.org" placeholder="Paste any RSS, XML, JSON API, or Web Feed URL...">
<button class="g" onclick="connectLiveFeed()">CONNECT LIVE FEED</button></div>
<pre id="jev-out">[JEV SYSTEM ONE READY] Lanes: VAULT_QUERY • TOOL_ACTION • AGENT_TASK • WORLD_LIBRARY.</pre></div>

<div class="card"><h3>1. AUTO-ASTRA COMPUTE &amp; MODEL ROUTER (8109) • STUDIO PRO (8108)</h3>
<div class="row"><input id="auto-goal" placeholder="Real-time goal or app/contract prompt..."><button class="g" onclick="runAuto()">AUTO-ASTRA</button><button onclick="buildApp()">1-PROMPT APP</button><button class="a" onclick="auditLaw()">CONTRACT LAWYER</button><button onclick="window.location.href='/api/pro/csv'">2-YR CSV</button></div>
<pre id="auto-out">[READY] Auto-selects Android Edge / PC / 8-GPU Supercomputer.</pre></div>

<div class="card"><h3>2. WYLER &amp; DEALERSLINK CRYPTO DEALERSHIP (SAME-ORIGIN HTTPS)</h3>
<iframe src="/dealership/"></iframe></div>

<div class="card"><h3>3. GREENSBORO TRIAD GEO • OSINT • SOC 2 / GDPR • BACKUPS</h3>
<div class="row"><input id="ops-in" placeholder="Greensboro address or OSINT topic..."><button class="g" onclick="triadGo()">TRIAD ROUTE</button><button onclick="osintGo()">OSINT HARVEST</button><button class="a" onclick="window.open('/api/ent/audit-report','_blank')">SOC 2 REPORT</button><button onclick="backupGo()">BACKUP DBS</button></div>
<pre id="ops-out">[ALL NODES LINKED]</pre></div>

<script>
async function api(u, b){const r=await fetch(u,b?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}:{});return await r.json();}


async function addLiveFeed(){
  const name = document.getElementById('feed-name').value.trim() || 'External Live Feed';
  const url = document.getElementById('feed-url').value.trim();
  if (!url) return;
  document.getElementById('jev-out').innerText = '> Connecting & harvesting live external feed...';
  const d = await api('/api/jev/add-feed', {name, url});
  document.getElementById('jev-out').innerText = '[' + d.feed_id + '] ' + d.name + ' -> ' + (d.snapshot || d.error);
}
async function syncAllFeeds(){
  document.getElementById('jev-out').innerText = '> Syncing all external feeds into Jev & 45M Brain...';
  const d = await api('/api/jev/feeds');
  document.getElementById('jev-out').innerText = (d.feeds || []).map(f => '[' + f.feed_id + '] ' + f.name + ': ' + (f.snapshot || f.error)).join('\n');
}

async function connectLiveFeed(){
  const url = document.getElementById('jev-feed-url').value.trim();
  document.getElementById('jev-out').innerText = '> Connecting Jev Reflex Layer to live external feed...';
  const d = await api('/api/jev/connect-feed', {url, label: 'LIVE_STREAM'});
  document.getElementById('jev-out').innerText = '[' + d.status + '] ' + d.url + '\\n' + (d.items||[]).map((x,i)=>(i+1)+'. '+x).join('\\n');
}
async function ingestJevFile(){
  const file_path = document.getElementById('jev-file').value.trim();
  const d = await api('/api/jev/ingest-file', {file_path});
  document.getElementById('jev-out').innerText = d.error || ('[' + d.status + '] ' + d.file + ' -> Learned Keywords: ' + (d.installed_keywords||[]).join(', '));
}
async function runJev(){const prompt=document.getElementById('jev-in').value.trim()||'Search world professional library';const d=await api('/api/jev/route',{prompt});document.getElementById('jev-out').innerText=d.output;}
async function runJevPreset(p){document.getElementById('jev-in').value=p;runJev();}
async function saveTfKey(){const api_key=document.getElementById('tf-key').value.trim();const d=await api('/api/jev/set-key',{api_key});document.getElementById('jev-out').innerText='['+d.status+'] Jev connected to Typeface route model.';}
async function runAuto(){const goal=document.getElementById('auto-goal').value.trim()||'Evening Wyler vehicle & Triad route';const d=await api('/api/auto/run',{goal});document.getElementById('auto-out').innerText=d.summary;}
async function buildApp(){const prompt=document.getElementById('auto-goal').value.trim()||'Sovereign Command App';const d=await api('/api/pro/app',{prompt,effort:'HIGH'});document.getElementById('auto-out').innerText=d.summary;if(d.app_url)window.open(d.app_url,'_blank');}
async function auditLaw(){const text=document.getElementById('auto-goal').value.trim()||'Contractor agreement with indemnification, Net 60, IP assignment';const d=await api('/api/pro/contract',{text,effort:'HIGH'});document.getElementById('auto-out').innerText=d.report;}
async function triadGo(){const d=await api('/api/geo/route',{});document.getElementById('ops-out').innerText='TRIAD: '+d.total_miles+' mi (~'+d.est_drive_minutes+' min) | Gas $'+d.fuel_cost_usd+' / EV $'+d.ev_cost_usd;}
async function osintGo(){const query=document.getElementById('ops-in').value.trim()||'Greensboro North Carolina';const d=await api('/api/osint/harvest',{query});document.getElementById('ops-out').innerText=d.summary;}
async function backupGo(){const d=await api('/api/wf/backup',{});document.getElementById('ops-out').innerText='['+d.status+'] '+d.snapshot+' ('+d.dbs_backed_up+' DBs)';}
api('/api/ent/visibility').then(d=>{if(d.online_count)document.getElementById('sys-stat').innerText='LIVE NODES: '+d.online_count+'/'+d.total_agents+' ONLINE';}).catch(()=>{});
</script></body></html>"""

class UnifiedHandler(BaseHTTPRequestHandler):
    def _proxy(self):
        H = ".".join(["127","0","0","1"])
        port = next((p for k, p in ROUTES.items() if self.path.startswith(k)), None)
        if not port: return False
        sub = self.path.replace("/dealership", "", 1) or "/"
        ln = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(ln) if (self.command == "POST" and ln > 0) else (b"{}" if self.command == "POST" else None)
        rq = urllib.request.Request(f"http://{H}:{port}{sub}", data=body, method=self.command)
        if body is not None: rq.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(rq, timeout=8) as r:
                data = r.read()
                self.send_response(r.status); self.send_header("Content-Type", r.headers.get("Content-Type", "application/json")); self.end_headers()
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
            self.send_error(404); return
        if self._proxy(): return
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

HTTPServer(("0.0.0.0", 8088), UnifiedHandler).serve_forever()
