import base64, hashlib, http.server, json, os, pathlib, socket, socketserver, subprocess, time, urllib.parse, urllib.request

PORT = 8089
HOME = pathlib.Path.home()

def probe_port(port, timeout=0.3):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False

def get_device_metrics():
    hw = {}
    if probe_port(8101, 0.25):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8101/api/hw", timeout=0.6) as r:
                hw = json.loads(r.read().decode()).get("hw", {})
        except Exception:
            pass
    orb = {}
    if probe_port(8102, 0.25):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8102/api/latest", timeout=0.5) as r:
                b = json.loads(r.read().decode()).get("block", {})
                f = b.get("feeds", {})
                orb = {
                    "h": b.get("height"),
                    "lat": f.get("iss", {}).get("lat"),
                    "lon": f.get("iss", {}).get("lon"),
                    "btc": f.get("spot", {}).get("btc_usd"),
                    "eth": f.get("spot", {}).get("eth_usd"),
                }
        except Exception:
            pass
    st = os.statvfs(str(HOME))
    disk_pct = round(((st.f_blocks - st.f_bavail) / max(st.f_blocks, 1)) * 100.0, 1)
    return {
        "ts": int(time.time()),
        "ram_pct": hw.get("ram_pct", 0.0),
        "ram_avail_mb": hw.get("ram_avail_mb", 0),
        "disk_pct": disk_pct,
        "load1": hw.get("load1", 0.0),
        "cores": hw.get("cores", os.cpu_count() or 1),
        "soc_temp_c": hw.get("soc_temp_c"),
        "batt_pct": hw.get("batt_pct"),
        "gpu_pct": hw.get("gpu_pct"),
        "npu_ready": hw.get("npu_ready", False),
        "net_rx_kb": hw.get("net_rx_kb", 0),
        "net_tx_kb": hw.get("net_tx_kb", 0),
        "orbital": orb,
        "nodes": {
            "agent_8099": probe_port(8099),
            "compute_8101": probe_port(8101),
            "gateway_8090": probe_port(8090),
            "sentinel_8165": probe_port(8165),
            "orbital_8102": probe_port(8102),
        }
    }

def list_workspace(rel_path=""):
    target = (HOME / rel_path).resolve()
    if not str(target).startswith(str(HOME.resolve())):
        target = HOME.resolve()
    if target.is_file():
        try:
            content = target.read_text(encoding="utf-8", errors="replace")[:8000]
        except Exception as e:
            content = f"[Read error: {e}]"
        return {"type": "file", "path": str(target.relative_to(HOME)), "content": content}
    items = []
    try:
        for p in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if p.name.startswith(".") and p.name not in (".pm2", ".github"):
                continue
            items.append({"name": p.name, "is_dir": p.is_dir(), "rel": str(p.relative_to(HOME)), "size": p.stat().st_size if p.is_file() else 0})
    except OSError:
        pass
    parent = "" if target == HOME.resolve() else str(target.parent.relative_to(HOME))
    return {"type": "dir", "path": str(target.relative_to(HOME)) if target != HOME.resolve() else "", "parent": parent, "items": items[:120]}

def write_workspace_file(rel_path, content):
    target = (HOME / rel_path).resolve()
    if not str(target).startswith(str(HOME.resolve())):
        return {"ok": False, "error": "Path outside HOME"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target.relative_to(HOME)), "bytes": len(content.encode("utf-8"))}

def proxy_provision(target, name="node"):
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8143/api/provision",
            data=json.dumps({"target": target, "name": name}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def proxy_teleport(action, slot="default", state=None):
    try:
        if action == "push":
            req = urllib.request.Request(
                "http://127.0.0.1:8101/teleport/push",
                data=json.dumps({"slot": slot, "state": state or {}, "device": "astra-deck-8088"}).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=2) as r:
                return json.loads(r.read().decode())
        with urllib.request.urlopen(f"http://127.0.0.1:8101/teleport/pull?slot={urllib.parse.quote(slot)}", timeout=2) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run_trigger(kind, code=""):
    if kind == "status":
        return {"ok": True, "target": "HW + NODES", "output": json.dumps(get_device_metrics(), indent=2)}
    if kind == "python":
        src = code.strip() or 'import platform, os; print("PY OK:", platform.python_version(), "| CORES:", os.cpu_count())'
        if probe_port(8101):
            try:
                req = urllib.request.Request("http://127.0.0.1:8101/run", data=json.dumps({"code": src}).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=4) as r:
                    d = json.loads(r.read().decode())
                    return {"ok": d.get("ok", False), "target": "COMPUTE :8101", "output": d.get("output", "")}
            except Exception:
                pass
        p = subprocess.run(["python3", "-c", src], capture_output=True, text=True, timeout=5)
        return {"ok": p.returncode == 0, "target": "LOCAL PYTHON3", "output": (p.stdout + p.stderr).strip()}
    if kind == "cpp":
        src = code.strip() or '#include <iostream>\nint main(){ std::cout << "ASTRA C++ COMPUTE READY" << std::endl; return 0; }'
        tmp_cpp, tmp_bin = "/data/data/com.termux/files/usr/tmp/astra_quick.cpp", "/data/data/com.termux/files/usr/tmp/astra_quick.out"
        pathlib.Path(tmp_cpp).write_text(src, encoding="utf-8")
        c = subprocess.run(["clang++", "-O2", tmp_cpp, "-o", tmp_bin], capture_output=True, text=True, timeout=10)
        if c.returncode != 0:
            return {"ok": False, "target": "CLANG++", "output": (c.stdout + c.stderr).strip()}
        r = subprocess.run([tmp_bin], capture_output=True, text=True, timeout=5)
        return {"ok": r.returncode == 0, "target": "C++ BINARY", "output": (r.stdout + r.stderr).strip()}
    if kind == "agent":
        if not probe_port(8099):
            return {"ok": False, "target": "AGENT :8099", "output": "Port 8099 Agent is currently OFFLINE."}
        try:
            req = urllib.request.Request("http://127.0.0.1:8099/api/chat", data=json.dumps({"prompt": code.strip() or "status"}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as r:
                return {"ok": True, "target": "AGENT :8099", "output": r.read().decode(errors="replace")}
        except Exception as e:
            return {"ok": False, "target": "AGENT :8099", "output": str(e)}
    return {"ok": False, "target": "UNKNOWN", "output": "Invalid trigger"}

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>ASTRA // ZERO-SCROLL COMMAND DECK (:8088)</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:100vw;height:100vh;overflow:hidden;background:#030812;color:#e2f1ff;font-family:monospace;font-size:11px}
  body{
    background-image:
      radial-gradient(circle at 50% 50%, rgba(56,189,248,0.12) 0%, rgba(3,8,18,0.96) 68%),
      repeating-radial-gradient(circle at 50% 50%, transparent 0, transparent 42px, rgba(56,189,248,0.06) 43px, transparent 44px);
    display:grid;grid-template-rows:42px 1fr;gap:6px;padding:6px;
  }
  header{display:flex;align-items:center;justify-content:space-between;background:rgba(6,15,30,0.88);border:1px solid #38bdf844;border-radius:8px;padding:0 10px}
  .brand{color:#38bdf8;font-weight:bold;letter-spacing:1.2px;font-size:11px}
  .pills{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .pill{padding:2px 7px;border-radius:999px;font-size:10px;border:1px solid #334155;background:#091426}
  .ok{color:#00ff9d;border-color:#00ff9d66}.off{color:#f43f5e;border-color:#f43f5e66}
  main{display:grid;grid-template-columns:1fr 1.25fr 1fr;gap:6px;min-height:0;height:100%}
  .pane{display:flex;flex-direction:column;min-height:0;overflow:hidden;background:rgba(6,15,30,0.84);border:1px solid #38bdf844;border-radius:8px;padding:8px}
  .ptitle{color:#38bdf8;font-size:10px;font-weight:bold;letter-spacing:1px;border-bottom:1px solid #38bdf833;padding-bottom:5px;margin-bottom:6px;display:flex;justify-content:space-between}
  .btns{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:6px}
  .tbtns{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:6px}
  button{background:#0b1f3a;color:#38bdf8;border:1px solid #38bdf866;border-radius:6px;padding:6px 5px;font-family:monospace;font-size:10px;cursor:pointer;font-weight:bold}
  button:active{background:#38bdf8;color:#030812}
  button.tp{border-color:#00ff9d66;color:#00ff9d}
  textarea{width:100%;height:64px;resize:none;background:#02060d;color:#00ff9d;border:1px solid #1e3a5f;border-radius:6px;padding:6px;font-family:monospace;font-size:11px;margin-bottom:6px}
  .scroll{flex:1;min-height:0;overflow-y:auto;background:#02060d;border:1px solid #1e3a5f;border-radius:6px;padding:6px;white-space:pre-wrap;word-break:break-word;font-size:10px;line-height:1.35}
  canvas#scope{width:100%;height:110px;background:#02060d;border:1px solid #1e3a5f;border-radius:6px;margin-bottom:6px;display:block}
  .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:6px}
  .mbox{background:#02060d;border:1px solid #1e3a5f;border-radius:6px;padding:5px 6px}
  .mk{color:#94a3b8;font-size:9px}.mv{color:#00ff9d;font-size:11px;font-weight:bold;margin-top:1px}
  .fitem{display:flex;justify-content:space-between;padding:4px 5px;border-bottom:1px solid #0f213b;cursor:pointer}
  .fitem:hover{background:#0b1f3a}
  .dir{color:#38bdf8;font-weight:bold}.file{color:#cbd5e1}
  @media (max-width: 820px){ main{grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr} .pane:nth-child(3){grid-column:1 / span 2} }
</style>
</head>
<body>
<header>
  <div class="brand">ASTRA // COMMAND DECK (:8088) + TELEPORT (:8101)</div>
  <div class="pills">
    <span id="p8099" class="pill off">AGENT :8099</span>
    <span id="p8101" class="pill off">COMPUTE :8101</span>
    <span id="p8090" class="pill off">GW :8090</span>
    <span id="p8165" class="pill off">SENTINEL :8165</span>
    <span id="p8102" class="pill off">ORBITAL :8102</span>
    <span id="wsPill" class="pill off">WS: INIT</span>
  </div>
</header>

<main>
  <!-- PANE 1: TRIGGERS, AGENT & 1-CLICK TELEPORT VAULT -->
  <section class="pane">
    <div class="ptitle"><span>01 // TRIGGERS & TELEPORT VAULT</span><span id="trigTarget">READY</span></div>
    <div class="btns">
      <button onclick="fire('status')">STATUS</button>
      <button onclick="fire('python')">PYTHON</button>
      <button onclick="fire('cpp')">C++</button>
    </div>
    <textarea id="cmdBox" placeholder="Python, C++, Agent :8099 prompt, or State Payload..."></textarea>
    <div class="tbtns">
      <button class="tp" onclick="teleport('push')">⬆ PUSH STATE (:8101)</button>
      <button class="tp" onclick="teleport('pull')">⬇ PULL STATE (:8101)</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin-bottom:6px">
      <button onclick="prov('gpu_datacenter')">GPU DC</button>
      <button onclick="prov('supercomputer')">HPC</button>
      <button onclick="prov('solar_edge')">SOLAR</button>
      <button onclick="prov('pc_node')">PC</button>
      <button onclick="prov('ai_agent')">AGENT</button>
    </div>
    <div id="agentLog" class="scroll">Standing by for trigger or State Teleport...</div>
  </section>

  <!-- PANE 2: 60FPS OSCILLOSCOPE CANVAS & LIVE STREAM -->
  <section class="pane">
    <div class="ptitle"><span>02 // 60FPS OSCILLOSCOPE & STREAM</span><span id="clock">--:--:--</span></div>
    <canvas id="scope"></canvas>
    <div id="orbTicker" style="font-size:10px;color:#38bdf8;background:#02060d;border:1px solid #1e3a5f;border-radius:6px;padding:4px 6px;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">ORBITAL :8102 // SYNCING...</div>
    <div id="streamLog" class="scroll">Connecting to WebSocket telemetry stream...</div>
  </section>

  <!-- PANE 3: WORKSPACE BROWSER & DEEP SOC/HW METRICS -->
  <section class="pane">
    <div class="ptitle"><span>03 // WORKSPACE & SOC/HW SENSORS</span><span id="cwdLabel">~/</span></div>
    <div class="metrics">
      <div class="mbox"><div class="mk">RAM</div><div class="mv" id="mRam">--%</div></div>
      <div class="mbox"><div class="mk">DISK</div><div class="mv" id="mDisk">--%</div></div>
      <div class="mbox"><div class="mk">LOAD</div><div class="mv" id="mLoad">--</div></div>
      <div class="mbox"><div class="mk">SOC TEMP</div><div class="mv" id="mTemp">--°C</div></div>
      <div class="mbox"><div class="mk">BATTERY</div><div class="mv" id="mBatt">--%</div></div>
      <div class="mbox"><div class="mk">GPU / NPU</div><div class="mv" id="mGpu">--</div></div>
    </div>
    <div id="fileList" class="scroll">Loading workspace...</div>
  </section>
</main>

<script>
const $ = id => document.getElementById(id);
let currentCwd = '';
function setPill(id, on, label) {
  const el = $(id); el.className = 'pill ' + (on ? 'ok' : 'off');
  if (label) el.textContent = label;
}
function logStream(msg) {
  const el = $('streamLog');
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + el.textContent.slice(0, 5000);
}

// 60FPS HTML5 Canvas Cybernetic Oscilloscope
const canvas = $('scope'), ctx = canvas.getContext('2d');
const ramHist = new Array(80).fill(50), loadHist = new Array(80).fill(10);
let phase = 0;
function drawScope() {
  const w = canvas.width = canvas.clientWidth;
  const h = canvas.height = canvas.clientHeight;
  ctx.fillStyle = '#02060d'; ctx.fillRect(0, 0, w, h);
  // Grid
  ctx.strokeStyle = 'rgba(56,189,248,0.12)'; ctx.lineWidth = 1;
  for (let x = 0; x < w; x += 28) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
  for (let y = 0; y < h; y += 22) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
  // RAM waveform (cyan)
  ctx.strokeStyle = '#38bdf8'; ctx.lineWidth = 1.8; ctx.beginPath();
  ramHist.forEach((v, i) => {
    const x = (i / (ramHist.length - 1)) * w;
    const y = h - (v / 100) * (h - 14) - 7 + Math.sin(phase + i * 0.25) * 2.2;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
  // Load waveform (neon green)
  ctx.strokeStyle = '#00ff9d'; ctx.lineWidth = 1.6; ctx.beginPath();
  loadHist.forEach((v, i) => {
    const x = (i / (loadHist.length - 1)) * w;
    const y = h - Math.min(v / 8, 1) * (h - 14) - 7 + Math.cos(phase * 1.4 + i * 0.3) * 2.0;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
  phase += 0.08;
  requestAnimationFrame(drawScope);
}
requestAnimationFrame(drawScope);

async function fire(kind) {
  $('trigTarget').textContent = 'RUNNING...';
  const r = await fetch('/api/trigger', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ kind, code: $('cmdBox').value }) });
  const d = await r.json();
  $('trigTarget').textContent = d.target;
  $('agentLog').textContent = d.output || '(no output)';
  logStream(`[${d.target}] ${kind.toUpperCase()} -> ${d.ok ? 'OK' : 'ERR'}`);
}

async function teleport(action) {
  $('trigTarget').textContent = 'TELEPORT...';
  const payload = { action, slot: 'default', state: { cmd: $('cmdBox').value, cwd: currentCwd, ts: Date.now() } };
  const r = await fetch('/api/teleport', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
  const d = await r.json();
  $('trigTarget').textContent = d.ok ? 'VAULT OK' : 'VAULT ERR';
  if (action === 'pull' && d.ok && d.state) {
    if (d.state.cmd !== undefined) $('cmdBox').value = d.state.cmd;
    if (d.state.cwd !== undefined) loadDir(d.state.cwd);
  }
  $('agentLog').textContent = JSON.stringify(d, null, 2);
  logStream(`[TELEPORT :8101] ${action.toUpperCase()} -> ${d.ok ? 'SYNCED' : d.error}`);
}

async function saveFile(path) {
  const content = document.getElementById('fileEditor').value;
  const r = await fetch('/api/fs/save', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ path, content }) });
  const d = await r.json();
  logStream(`[WRITE] ${d.ok ? 'SAVED ' + d.path + ' (' + d.bytes + 'B)' : 'ERR: ' + d.error}`);
}
async function prov(target) {
  $('trigTarget').textContent = 'PROVISIONING...';
  const r = await fetch('/api/provision', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ target, name: 'build' }) });
  const d = await r.json();
  $('trigTarget').textContent = d.ok ? 'BUILT' : 'ERR';
  $('agentLog').textContent = JSON.stringify(d, null, 2);
  logStream(`[PROVISION :8143] ${target} -> ${d.ok ? d.bundle_dir : d.error}`);
  if (d.ok) loadDir('astra_blueprints');
}
async function loadDir(rel = '') {
  currentCwd = rel;
  const r = await fetch('/api/fs?path=' + encodeURIComponent(rel));
  const d = await r.json();
  $('cwdLabel').textContent = '~/' + (d.path || '');
  const box = $('fileList');
  if (d.type === 'file') {
    const parentDir = d.path.split('/').slice(0,-1).join('/');
    box.innerHTML = `
      <div style="display:flex;gap:6px;margin-bottom:6px">
        <button onclick="loadDir('${parentDir}')">⬅ BACK</button>
        <button class="tp" onclick="saveFile('${d.path}')">💾 SAVE TO DISK</button>
      </div>
      <textarea id="fileEditor" style="width:100%;height:calc(100% - 34px);resize:none;background:#02060d;color:#00ff9d;border:1px solid #38bdf866;border-radius:6px;padding:6px;font-family:monospace;font-size:11px"></textarea>`;
    document.getElementById('fileEditor').value = d.content;
    return;
  }
  let html = d.path ? `<div class="fitem dir" onclick="loadDir('${d.parent}')">⬅ ..</div>` : '';
  for (const it of d.items) {
    html += `<div class="fitem ${it.is_dir ? 'dir' : 'file'}" onclick="loadDir('${it.rel}')"><span>${it.is_dir ? '📁 ' : '📄 '}${it.name}</span><span>${it.is_dir ? 'DIR' : it.size + 'B'}</span></div>`;
  }
  box.innerHTML = html || '(empty)';
}

function connectWS() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { setPill('wsPill', true, 'WS: LIVE'); logStream('WebSocket telemetry + oscilloscope locked.'); };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    $('clock').textContent = new Date(m.ts * 1000).toLocaleTimeString();
    $('mRam').textContent = m.ram_pct + '%';
    $('mDisk').textContent = m.disk_pct + '%';
    $('mLoad').textContent = m.load1 + ' (' + m.cores + 'c)';
    $('mTemp').textContent = m.soc_temp_c !== null ? m.soc_temp_c + '°C' : 'N/A';
    $('mBatt').textContent = m.batt_pct !== null ? m.batt_pct + '%' : 'N/A';
    $('mGpu').textContent = (m.gpu_pct !== null ? m.gpu_pct + '%' : 'SOC') + (m.npu_ready ? ' / NPU' : '');
    ramHist.push(m.ram_pct); ramHist.shift();
    loadHist.push(m.load1); loadHist.shift();
    setPill('p8099', m.nodes.agent_8099);
    setPill('p8101', m.nodes.compute_8101);
    setPill('p8090', m.nodes.gateway_8090);
    setPill('p8165', m.nodes.sentinel_8165);
    setPill('p8102', m.nodes.orbital_8102);
    if (m.orbital && m.orbital.h) {
      const o = m.orbital;
      $('orbTicker').textContent = `BLK #${o.h} | ISS ${o.lat}, ${o.lon} | BTC $${Number(o.btc||0).toFixed(0)} | ETH $${Number(o.eth||0).toFixed(0)}`;
    }
  };
  ws.onclose = () => { setPill('wsPill', false, 'WS: RETRY'); setTimeout(connectWS, 1500); };
}
loadDir('');
connectWS();
</script>
</body>
</html>'''

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _send(self, code, ctype, body):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/": return self._send(200, "text/html; charset=utf-8", HTML)
        if u.path == "/api/fs":
            q = urllib.parse.parse_qs(u.query).get("path", [""])[0]
            return self._send(200, "application/json", json.dumps(list_workspace(q)))
        if u.path == "/ws":
            key = self.headers.get("Sec-WebSocket-Key", "")
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            self.wfile.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
            self.wfile.flush()
            try:
                while True:
                    payload = json.dumps(get_device_metrics()).encode("utf-8")
                    n = len(payload)
                    hdr = bytes([0x81, n]) if n < 126 else bytes([0x81, 126, (n >> 8) & 255, n & 255])
                    self.wfile.write(hdr + payload); self.wfile.flush(); time.sleep(0.5)
            except Exception:
                return
        self._send(404, "text/plain", "Not Found")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        if self.path == "/api/fs/save":
            return self._send(200, "application/json", json.dumps(write_workspace_file(body.get("path", ""), body.get("content", ""))))
        if self.path == "/api/provision":
            return self._send(200, "application/json", json.dumps(proxy_provision(body.get("target", "gpu_datacenter"), body.get("name", "build"))))
        if self.path == "/api/trigger":
            return self._send(200, "application/json", json.dumps(run_trigger(body.get("kind", ""), body.get("code", ""))))
        if self.path == "/api/teleport":
            res = proxy_teleport(body.get("action", "pull"), body.get("slot", "default"), body.get("state"))
            return self._send(200, "application/json", json.dumps(res))
        self._send(404, "text/plain", "Not Found")

if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("127.0.0.1", PORT), DashboardHandler).serve_forever()
