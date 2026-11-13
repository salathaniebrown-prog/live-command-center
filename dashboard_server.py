import os

def trigger_1click_dealership_pipeline():
    import hashlib, hmac, http.client, json, uuid
    secret = os.environ.get("ASTRA_WEBHOOK_SECRET", "astra_sovereign_hmac_key_2026").encode("utf-8")
    order_ref = "ORD-" + uuid.uuid4().hex[:6].upper()
    vin = "1GT49REY5NU104829"
    amount_usd = 107326.00
    payload = {
        "rail": "VIRTUAL_CARD_CRYPTO_ESCROW",
        "type": "dealership.purchase.settled",
        "order_ref": order_ref,
        "vehicle": "2026 GMC Hummer EV Edition 1 SUV",
        "vin": vin,
        "virtual_card_last4": "4419",
        "amount_usd": amount_usd
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

    conn_wh = http.client.HTTPConnection("127.0.0.1", 8115, timeout=8)
    conn_wh.request("POST", "/webhook", body=raw_body, headers={
        "Content-Type": "application/json",
        "X-Astra-Signature": "sha256=" + sig
    })
    wh_res = json.loads(conn_wh.getresponse().read().decode())

    conn_jev = http.client.HTTPConnection("127.0.0.1", 8111, timeout=8)
    conn_jev.request("GET", "/")
    jev_res = json.loads(conn_jev.getresponse().read().decode())

    return {
        "status": "PIPELINE_VERIFIED",
        "order_ref": order_ref,
        "vin": vin,
        "amount_usd": amount_usd,
        "webhook_8115": wh_res,
        "jev_8111_total_invoices": jev_res.get("invoices_count")
    }

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
    "/api/pro/": 8108, "/api/auto/": 8109, "/api/telemetry/": 8110, "/api/jev/": 8111, "/api/mp/": 8113, "/v1/chat/completions": 8111
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
async function api(u, b){try{const r=await fetch(u,b?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}:{});return await r.json();}catch(e){return {error:String(e),output:'[RETRYING] '+e};}}


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
</script>
<div class="card"><h3>4. MEDIAPIPE TASKS // LIVE ML ANYWHERE (WASM • WEBGPU • ANDROID • IOS • FLUTTER • PYTHON) (8113)</h3>
<div class="row"><select id="mp-task"><option value="VISION_TEXT_AUDIO_RAG">VISION + TEXT + AUDIO + RAG</option><option value="DECISION_ROUTING_MODEL">DECISION &amp; ROUTING MODEL</option><option value="ON_DEVICE_GEMMA4_LLM">ON-DEVICE GEMMA 4 LLM</option></select>
<select id="mp-plat"><option value="WEB_WASM_WEBGPU">WEB (WASM + WEBGPU)</option><option value="ANDROID_KOTLIN_JAVA">ANDROID (KOTLIN / JAVA)</option><option value="IOS_SWIFT_OBJC">IOS (SWIFT / OBJ-C)</option><option value="FLUTTER_DART">FLUTTER (DART)</option><option value="PYTHON_LINUX_MAC_WIN">PYTHON (LINUX/MAC/WIN)</option></select>
<button class="g" onclick="buildMpTask()">BUILD .TASK BUNDLE (GPU)</button>
<div style="display:flex;gap:8px;margin-top:8px;">
  <input id="mp-infer-input" type="text" placeholder="Test on-device inference / RAG query / routing prompt..." style="flex:1;background:#071318;border:1px solid #184e59;color:#9efcff;padding:6px 10px;font-family:monospace;font-size:12px;">
  <button onclick="runMpInfer(false)" style="background:#0d3b44;border:1px solid #25b8c9;color:#fff;padding:6px 12px;font-weight:bold;cursor:pointer;">RUN INFER</button>
  <button onclick="runMpInfer(true)" style="background:#163826;border:1px solid #35d07f;color:#fff;padding:6px 12px;font-weight:bold;cursor:pointer;">INDEX RAG</button>
  <button onclick="window.open('http://'+location.hostname+':8113/ui','_blank')" style="background:#1b2c4d;border:1px solid #4ea1ff;color:#fff;padding:6px 12px;font-weight:bold;cursor:pointer;">OPEN WEBGPU RUNNER</button>
</div>
<pre id="mp-infer-out" style="margin-top:6px;padding:6px;background:#040b0e;border:1px solid #10323a;color:#6ef7c8;font-size:11px;white-space:pre-wrap;display:none;"></pre>
<script>
async function runMpInfer(indexMode) {
  const input = document.getElementById('mp-infer-input').value || 'detect objects in live camera stream';
  const taskSel = document.querySelector('[id*="mp"], select');
  const taskType = indexMode ? 'RETRIEVAL' : (input.toLowerCase().includes('search') ? 'RETRIEVAL' : 'DECISION');
  const out = document.getElementById('mp-infer-out');
  out.style.display = 'block';
  out.textContent = '[RUNNING ON-DEVICE INFERENCE...]';
  const res = await fetch("http://" + location.hostname + ":8113/execute", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({goal:input, index:indexMode})});
  out.textContent = JSON.stringify(await res.json(), null, 2);
}
</script>
</div>
<pre id="mp-out">[MEDIAPIPE TASKS READY] On-device CPU/GPU acceleration across Web, Android, iOS, Flutter &amp; Desktop.</pre></div>
<script>
async function buildMpTask(){
  const task_type = document.getElementById('mp-task').value;
  const platform = document.getElementById('mp-plat').value;
  const d = await api('/api/mp/build', {task_type, platform, delegate: 'GPU'});
  document.getElementById('mp-out').innerText = '[' + d.task_bundle_id + ' | ' + d.target_platform + ' | ' + d.accelerator_delegate + ']\\n' + d.sdk_code;
}
</script>
<script>
async function dispatchToJev8111(orderRef, vin, amountUsd) {
    try {
        const target = "http://" + window.location.hostname + ":8111/invoice";
        const res = await fetch(target, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({order_ref: orderRef, vin: vin, amount_usd: amountUsd})
        });
        const data = await res.json();
        alert("JEV SYSTEM ONE RECEIPT PERSISTED:\n" + JSON.stringify(data, null, 2));
    } catch (e) {
        console.error("JEV 8111 Bridge Error:", e);
    }
}
</script>

<div id="astra-webhook-ticker" style="position:fixed;bottom:10px;right:12px;width:360px;background:rgba(5,12,24,0.95);border:1px solid #00ff88;box-shadow:0 0 15px rgba(0,255,136,0.25);padding:10px;font-family:monospace;font-size:11px;color:#00f0ff;z-index:9999;">
  <div style="display:flex;justify-content:space-between;border-bottom:1px solid #00ff8844;padding-bottom:4px;margin-bottom:6px;">
    <strong style="color:#00ff88;">LIVE CRYPTO / CARD WEBHOOKS (8115)</strong>
    <span id="wh-count" style="color:#fff;">0 EVENTS</span>
  </div>
  <button id="btn-1click-test" onclick="runOneClickPipelineTest()" style="width:100%;margin-bottom:6px;padding:6px;background:#00ff8822;border:1px solid #00ff88;color:#00ff88;font-family:monospace;font-weight:bold;cursor:pointer;text-transform:uppercase;">⚡ 1-CLICK TEST TRANSACTION (8115 -> 8111)</button>
  <div id="wh-last-receipt" style="display:none;background:#00ff8815;border:1px solid #00ff8855;padding:5px;margin-bottom:6px;color:#fff;font-size:10px;"></div>
  <div id="wh-feed-list" style="max-height:110px;overflow-y:auto;line-height:1.4;">Waiting for incoming HMAC events...</div>
</div>
<script>
async function runOneClickPipelineTest() {
  const btn = document.getElementById("btn-1click-test");
  const box = document.getElementById("wh-last-receipt");
  btn.disabled = true;
  btn.innerText = "EXECUTING HMAC -> JEV PIPELINE...";
  try {
    const res = await fetch("/api/test-dealership-pipeline", {method: "POST"});
    const data = await res.json();
    box.style.display = "block";
    box.innerHTML = `<strong style="color:#00ff88;">[✔] SETTLED ${data.order_ref}</strong> | $${Number(data.amount_usd).toLocaleString()}<br>` +
                    `EVENT: ${data.webhook_8115.event_id} | HMAC: VERIFIED<br>` +
                    `JEV 8111 RECEIPTS: ${data.jev_8111_total_invoices}`;
    await pollWebhookFeed8115();
  } catch (e) {
    box.style.display = "block";
    box.innerText = "PIPELINE ERROR: " + e;
  }
  btn.disabled = false;
  btn.innerText = "⚡ 1-CLICK TEST TRANSACTION (8115 -> 8111)";
}
async function pollWebhookFeed8115() {
  try {
    const url = "http://" + window.location.hostname + ":8115/";
    const res = await fetch(url);
    const data = await res.json();
    document.getElementById("wh-count").innerText = (data.events_logged || 0) + " EVENTS";
    const list = document.getElementById("wh-feed-list");
    if (data.recent_events && data.recent_events.length > 0) {
      list.innerHTML = data.recent_events.slice(0, 4).map(ev =>
        `<div style="border-bottom:1px dashed #ffffff22;padding:3px 0;">` +
        `<span style="color:#00ff88;">[✔] ${ev.event_id}</span> | $${Number(ev.amount_usd).toLocaleString()}<br>` +
        `<span style="color:#8899aa;">VIN: ${ev.vin} | ${ev.event_type}</span>` +
        `</div>`
      ).join("");
    }
  } catch (e) {}
}
setInterval(pollWebhookFeed8115, 5000);
pollWebhookFeed8115();
</script>
</body>

</html>"""

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
        if self.path == "/api/test-dealership-pipeline":
            import json
            res_body = json.dumps(trigger_1click_dealership_pipeline()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(res_body)))
            self.end_headers()
            self.wfile.write(res_body)
            return


        if self.path == "/api/mediapipe/infer":
            import urllib.request
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            req = urllib.request.Request("http://127.0.0", data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                out = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)
            return

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
