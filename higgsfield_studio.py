import json
import os
import sqlite3
import time
import urllib.request
from urllib.parse import urlparse

DB_PATH = os.path.expanduser("~/tmp/higgsfield_shots.db")
PORT_ROUTES = {
    "8088": "/api/telemetry/chronicle",
    "8090": "/api/telemetry/chronicle",
    "8095": "/",
    "8099": "/",
    "8110": "/api/telemetry/status",
    "8125": "/api/telemetry/iot-process",
    "8170": "/",
}

def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=3) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS shots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                compiled_prompt TEXT NOT NULL,
                settings_json TEXT NOT NULL,
                mode TEXT NOT NULL
            )"""
        )

def _send(handler, code, ctype, body_bytes):
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body_bytes)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body_bytes)

def _send_json(handler, code, obj):
    _send(handler, code, "application/json; charset=utf-8", json.dumps(obj).encode("utf-8"))

def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return {}

def _probe_port(port, message):
    route = PORT_ROUTES.get(str(port), "/")
    url = f"http://127.0.0.1:{port}{route}"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"X-Astra-Chat": message[:120]})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            raw = resp.read(320).decode("utf-8", errors="replace").strip()
            ms = round((time.time() - t0) * 1000, 1)
            return {"port": str(port), "ok": True, "http": resp.status, "ms": ms, "reply": raw}
    except Exception as e:
        ms = round((time.time() - t0) * 1000, 1)
        return {"port": str(port), "ok": False, "http": 0, "ms": ms, "reply": str(e)}

GIANT_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Astra Giant Dashboard — :8112 Bridge + OTel/FluentBit/Prometheus</title>
<style>
  :root{--bg:#06090f;--panel:#0e1420;--line:#1f2b3d;--txt:#edf2f7;--muted:#8899b3;--ok:#34d399;--warn:#fbbf24;--bad:#f87171;--acc:#38bdf8}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);font:13px/1.4 system-ui,sans-serif}
  header{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;background:#0a0f18;border-bottom:1px solid var(--line)}
  .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:12px}
  .span2{grid-column:span 2} .span4{grid-column:span 4}
  @media(max-width:900px){.grid{grid-template-columns:1fr}.span2,.span4{grid-column:span 1}}
  .box{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
  .kpi{font-size:22px;font-weight:700;margin-top:4px}
  .ports{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-top:8px}
  .pchip{padding:8px;border-radius:8px;border:1px solid var(--line);background:#090d14;font-family:monospace;font-size:12px}
  .up{border-color:#10b98166;color:var(--ok)} .dn{border-color:#ef444466;color:var(--bad)}
  .feed{height:170px;overflow:auto;background:#070a10;border:1px solid var(--line);border-radius:8px;padding:8px;font-family:monospace;font-size:11.5px}
  input,select,button{background:#090e17;color:var(--txt);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit}
  button{background:var(--acc);color:#041018;font-weight:700;border:0;cursor:pointer}
  .row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
</style>
</head>
<body>
<header>
  <div><strong>ASTRA GIANT COMMAND WALL</strong> · Kick/Twitch :8112 · OTel · Fluent Bit · Prometheus</div>
  <div id="clock">--:--:--</div>
</header>
<div class="grid">
  <div class="box"><div style="color:var(--muted)">FREE RAM (FLOOR 520 MiB)</div><div class="kpi" id="kRam">--</div></div>
  <div class="box"><div style="color:var(--muted)">:8112 BRIDGE / WS</div><div class="kpi" id="kBridge">--</div></div>
  <div class="box"><div style="color:var(--muted)">OTEL + FLUENT BIT</div><div class="kpi" id="kPipe">--</div></div>
  <div class="box"><div style="color:var(--muted)">PROMETHEUS SCRAPES</div><div class="kpi" id="kProm">--</div></div>

  <div class="box span4">
    <strong>7-PORT CONTROL + INTELLIGENCE MESH</strong>
    <div class="ports" id="portGrid"></div>
  </div>

  <div class="box span2">
    <strong>KICK + TWITCH LIVE STREAM FEED (:8112)</strong>
    <div class="feed" id="streamFeed"></div>
    <div class="row">
      <select id="plat"><option value="kick">Kick</option><option value="twitch">Twitch</option></select>
      <input id="evText" style="flex:1" placeholder="Push live stream chat/alert test event..."/>
      <button onclick="sendStreamEvent()">Emit Event</button>
    </div>
  </div>

  <div class="box span2">
    <strong>TELEMETRY PIPELINE INGEST TEST (OTEL / FLUENT BIT)</strong>
    <div class="feed" id="pipeLog"></div>
    <div class="row">
      <button onclick="sendPipe('otel')">Send OTel Batch</button>
      <button onclick="sendPipe('fluentbit')">Send Fluent Bit Record</button>
      <button onclick="refreshAll()">Refresh Now</button>
    </div>
  </div>
</div>
<script>
function logPipe(msg){
  const el = document.getElementById('pipeLog');
  el.textContent += msg + "\n"; el.scrollTop = el.scrollHeight;
}
async function refreshAll(){
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
  try {
    const st = await (await fetch('/api/higgsfield/status')).json();
    const ch = await (await fetch('/api/telemetry/chronicle')).json();
    const ram = Number(ch.free_ram_mib || 0);
    const rEl = document.getElementById('kRam');
    rEl.textContent = ram.toFixed(1) + ' MiB';
    rEl.style.color = ram >= 520 ? 'var(--ok)' : 'var(--warn)';
  } catch(e){}
  try {
    const b = await (await fetch('http://127.0.0.1:8112/')).json();
    document.getElementById('kBridge').textContent = (b.ok ? 'ONLINE' : 'DOWN') + ' · WS:' + b.ws_clients;
    document.getElementById('kPipe').textContent = 'OTel:' + (b.otel.metrics_batches + b.otel.logs_batches) + ' · FB:' + b.fluentbit_records;
    document.getElementById('kProm').textContent = String(b.prom_scrapes);
    document.getElementById('portGrid').innerHTML = (b.watched_ports || []).map(p =>
      `<div class="pchip ${p.up ? 'up' : 'dn'}">:${p.port} ${p.up ? 'UP ('+p.status+')' : 'DOWN'}</div>`
    ).join('');
  } catch(e){
    document.getElementById('kBridge').textContent = 'OFFLINE';
  }
  try {
    const ev = await (await fetch('http://127.0.0.1:8112/api/stream/events')).json();
    document.getElementById('streamFeed').innerHTML = (ev.events || []).slice(-20).map(x =>
      `[${x.ts.slice(11,19)}] <strong>${x.platform.toUpperCase()}</strong> (${x.kind}): ${JSON.stringify(x.payload)}`
    ).join('<br/>') || 'No stream events yet.';
  } catch(e){}
}
async function sendStreamEvent(){
  const plat = document.getElementById('plat').value;
  const text = document.getElementById('evText').value.trim() || 'Live test ping';
  document.getElementById('evText').value = '';
  await fetch('http://127.0.0.1:8112/api/stream/event', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({platform: plat, kind: 'chat', payload: {text}})
  });
  refreshAll();
}
async function sendPipe(kind){
  if(kind === 'otel'){
    const r = await (await fetch('http://127.0.0.1:8112/v1/metrics', {method:'POST', body:'{"metric":"ram_mib"}'})).json();
    logPipe('OTel batch accepted -> total=' + r.accepted_batches);
  } else {
    const r = await (await fetch('http://127.0.0.1:8112/api/fluentbit/ingest', {method:'POST', body:'[{"tag":"astra.log","msg":"ok"}]'})).json();
    logPipe('Fluent Bit ingested -> total=' + r.total_records);
  }
  refreshAll();
}
refreshAll(); setInterval(refreshAll, 4000);
</script>
</body>
</html>
"""

STUDIO_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Higgsfield Cinema Studio — Astra Local (No Login)</title>
<style>
  :root{--bg:#0b0e14;--card:#131924;--line:#243044;--txt:#e6edf7;--muted:#8b9bb4;--acc:#5ce1e6;--acc2:#a78bfa;}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.45 system-ui,sans-serif}
  header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line);background:#0f141e}
  .badge{background:#182436;color:var(--acc);border:1px solid var(--line);padding:3px 9px;border-radius:999px;font-size:12px}
  main{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;padding:14px;max-width:1280px;margin:auto}
  @media(max-width:860px){main{grid-template-columns:1fr}}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
  h2{margin:0 0 10px;font-size:15px;color:var(--acc)}
  label{display:block;font-size:12px;color:var(--muted);margin:8px 0 3px}
  textarea,select,input{width:100%;background:#0c111a;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
  .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  button{background:var(--acc);color:#061018;border:0;border-radius:8px;padding:9px 13px;font-weight:700;cursor:pointer}
  button.sec{background:#1c273a;color:var(--txt);border:1px solid var(--line)}
  canvas{width:100%;aspect-ratio:16/9;background:#05070b;border-radius:10px;border:1px solid var(--line);display:block}
  #chatlog{height:300px;overflow:auto;background:#0a0e16;border:1px solid var(--line);border-radius:8px;padding:10px;font-size:12.5px}
  .msg{margin:0 0 8px;padding:7px 9px;border-radius:8px;background:#141d2b;word-break:break-word}
  .msg.me{background:#1d243b;border-left:3px solid var(--acc2)}
  .msg.ok{border-left:3px solid #34d399} .msg.err{border-left:3px solid #f87171}
  .shot{padding:8px;border-bottom:1px solid var(--line);font-size:12px}
  .muted{color:var(--muted)}
</style>
</head>
<body>
<header>
  <div><strong>HIGGSFIELD CINEMA STUDIO</strong> <span class="badge">NO LOGIN · LOCAL + CLOUD READY</span></div>
  <div class="badge" id="hdrPort">PORT</div>
</header>
<main>
  <section class="card">
    <h2>Director's Panel & Live Motion Canvas</h2>
    <canvas id="stage" width="640" height="360"></canvas>
    <label>Scene Prompt</label>
    <textarea id="prompt" rows="2" placeholder="Describe subject, action, and setting...">Neon-lit futuristic command center in Winston-Salem at night, rain on glass, cinematic reflection</textarea>
    <div class="grid3">
      <div><label>Camera Movement</label>
        <select id="move">
          <option value="Dolly In">Dolly In (Preset: Command Center Night)</option><option>Dolly In</option><option>Orbit 360</option><option>Crash Zoom</option>
          <option>Bullet Time</option><option>Crane Up</option><option>FPV Drone</option>
          <option>Robot Arm</option><option>Pan Left</option><option>Static Locked</option>
        </select>
      </div>
      <div><label>Genre</label>
        <select id="genre"><option>Action</option><option>Epic</option><option>Drama</option><option>Noir</option><option>Comedy</option><option>Horror</option></select>
      </div>
      <div><label>Lighting</label>
        <select id="lighting"><option>Soft Cross</option><option>Contre-jour</option><option>Overhead Fall</option><option>Practicals</option><option>Silhouette</option><option>Window</option></select>
      </div>
    </div>
    <div class="grid3">
      <div><label>Camera Body</label>
        <select id="camera"><option>35mm Film</option><option>Modern Digital</option><option>8mm Film</option><option>DV Camcorder</option></select>
      </div>
      <div><label>Lens</label>
        <select id="lens"><option>Anamorphic</option><option>Clean Sharp</option><option>Vintage Anamorphic</option><option>Warm Vintage</option><option>Halation Vintage</option></select>
      </div>
      <div><label>Aperture</label>
        <select id="aperture"><option>f/1.4 Wide Open</option><option>f/4 Moderate</option><option>f/11 Deep Focus</option></select>
      </div>
    </div>
    <div class="grid3">
      <div><label>Model Engine</label><select id="engine"><option value="Higgsfield Cinema">Higgsfield Cinema</option><option value="MiniMax H3">MiniMax H3 (2K + Stereo Audio)</option></select></div>
      <div><label>Aspect Ratio</label><select id="aspect"><option>16:9</option><option>21:9 Ultrawide</option><option>2.39:1 Anamorphic</option><option>4:3</option><option>1:1 Square</option><option>3:4</option><option>9:16 Vertical</option></select></div>
      <div><label>Duration (5–15s)</label><input id="duration" type="number" min="5" max="15" value="10"/></div>
      <div><label>H3 Audio / Ref / Edit Note</label><input id="h3note" placeholder="Stereo foley, voice ref, or edit..."/></div>
    </div>
    <div class="row">
      <button class="sec" onclick="applyCommandCenterPreset()">Preset: Command Center Night</button>
      <button onclick="generateShot()">Generate &amp; Preview</button>
      <button class="sec" onclick="recordClip()">Record .webm Clip</button>
      <button class="sec" onclick="copyPrompt()">Copy Compiled Prompt</button>
    </div>
    <p id="compiledOut" class="muted" style="font-size:12px;margin-top:10px"></p>
    <h2 style="margin-top:14px">Recent Shots (SQLite WAL)</h2>
    <div id="shots"></div>
  </section>

  <section class="card">
    <h2>All-Ports Live Chatbox (8088–8170)</h2>
    <div class="grid2" style="margin-bottom:8px">
      <div>
        <label>Target Port</label>
        <select id="chatPort">
          <option value="all">ALL 7 PORTS (Fan-Out)</option>
          <option value="8088">:8088 Dashboard Gateway</option>
          <option value="8090">:8090 Dashboard Core</option>
          <option value="8095">:8095 Alstra Master Spine</option>
          <option value="8099">:8099 Alstra WAL Brain</option>
          <option value="8110">:8110 Telemetry Assistant</option>
          <option value="8125">:8125 IoT Process Backend</option>
          <option value="8170">:8170 SHM Port Monitor</option>
        </select>
      </div>
      <div style="display:flex;align-items:flex-end">
        <button class="sec" style="width:100%" onclick="sendChat('ping')">Probe Selected Port(s)</button>
      </div>
    </div>
    <div id="chatlog"></div>
    <div class="row" style="margin-top:8px">
      <input id="chatIn" placeholder="Ask Mr. Higgs or send command to port(s)..." onkeydown="if(event.key==='Enter')sendChat()"/>
      <button onclick="sendChat()">Send</button>
    </div>
  </section>
</main>
<script>
document.getElementById('hdrPort').textContent = 'LIVE :' + (location.port || '80');
let animState = {t:0, move:'Dolly In', prompt:'Astra Cinema Studio Ready', genre:'Action', lens:'Anamorphic', lighting:'Soft Cross'};
const cv = document.getElementById('stage'), ctx = cv.getContext('2d');

function drawStage(){
  animState.t += 0.025;
  const t = animState.t, w = cv.width, h = cv.height;
  ctx.fillStyle = '#070b12'; ctx.fillRect(0,0,w,h);
  let scale = 1, dx = 0, dy = 0, rot = 0;
  if(animState.move === 'Dolly In') scale = 1 + 0.18 * Math.sin(t);
  else if(animState.move === 'Crash Zoom') scale = 1 + 0.35 * ((t % 2)/2);
  else if(animState.move === 'Orbit 360' || animState.move === 'Bullet Time'){ dx = Math.cos(t)*45; rot = Math.sin(t)*0.06; }
  else if(animState.move === 'Crane Up') dy = -30 * Math.sin(t);
  else if(animState.move === 'Pan Left') dx = -50 * Math.sin(t);
  else if(animState.move === 'FPV Drone' || animState.move === 'Robot Arm'){ dx = Math.sin(t*1.7)*35; dy = Math.cos(t*1.3)*20; rot = Math.sin(t)*0.08; }
  ctx.save();
  ctx.translate(w/2 + dx, h/2 + dy); ctx.rotate(rot); ctx.scale(scale, scale);
  const g = ctx.createRadialGradient(0,-20,10,0,0,260);
  g.addColorStop(0, animState.lighting === 'Contre-jour' ? '#f59e0b55' : '#5ce1e655');
  g.addColorStop(1, '#090d16');
  ctx.fillStyle = g; ctx.fillRect(-w/2,-h/2,w,h);
  ctx.strokeStyle = '#5ce1e644'; ctx.lineWidth = 1;
  for(let x=-280;x<=280;x+=40){ ctx.beginPath(); ctx.moveTo(x,-140); ctx.lineTo(x,140); ctx.stroke(); }
  for(let y=-140;y<=140;y+=40){ ctx.beginPath(); ctx.moveTo(-280,y); ctx.lineTo(280,y); ctx.stroke(); }
  ctx.fillStyle = '#e6edf7'; ctx.font = 'bold 18px system-ui'; ctx.textAlign = 'center';
  ctx.fillText(animState.move.toUpperCase() + ' · ' + animState.genre.toUpperCase(), 0, -10);
  ctx.fillStyle = '#8b9bb4'; ctx.font = '13px system-ui';
  ctx.fillText((animState.prompt || '').slice(0, 62), 0, 18);
  ctx.restore();
  if(animState.lens.includes('Anamorphic')){
    ctx.fillStyle = '#000'; ctx.fillRect(0,0,w,36); ctx.fillRect(0,h-36,w,36);
  }
  ctx.fillStyle = '#5ce1e6'; ctx.font = '11px monospace'; ctx.textAlign = 'left';
  ctx.fillText('REC ● ' + animState.lens + ' | ' + animState.lighting, 12, 22);
  requestAnimationFrame(drawStage);
}
drawStage();

async function generateShot(){
  const payload = {
    prompt: document.getElementById('prompt').value.trim(),
    move: document.getElementById('move').value,
    genre: document.getElementById('genre').value,
    lighting: document.getElementById('lighting').value,
    camera: document.getElementById('camera').value,
    lens: document.getElementById('lens').value,
    aperture: document.getElementById('aperture').value,
    engine: document.getElementById('engine').value,
    h3_note: document.getElementById('h3note').value.trim(),
    aspect: document.getElementById('aspect').value,
    duration: Number(document.getElementById('duration').value || 6)
  };
  animState = {...animState, ...payload, t:0};
  const r = await fetch('/api/higgsfield/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const d = await r.json();
  document.getElementById('compiledOut').textContent = 'Compiled Cinema Prompt: ' + d.compiled_prompt;
  loadShots();
}

function recordClip(){
  if(!cv.captureStream || typeof MediaRecorder === 'undefined'){ alert('MediaRecorder unsupported in this browser.'); return; }
  const stream = cv.captureStream(24), rec = new MediaRecorder(stream, {mimeType:'video/webm'});
  const chunks = [];
  rec.ondataavailable = e => { if(e.data.size) chunks.push(e.data); };
  rec.onstop = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(chunks, {type:'video/webm'}));
    a.download = 'higgsfield_local_preview.webm'; a.click();
  };
  rec.start(); setTimeout(() => rec.stop(), 3000);
}

function applyCommandCenterPreset(){
  document.getElementById('prompt').value = 'COMMAND_CENTER_NIGHT: dual telemetry monitors, glass reflections, calm tactical precision';
  document.getElementById('move').value = 'Dolly In';
  document.getElementById('genre').value = 'Noir';
  document.getElementById('lighting').value = 'Practicals';
  document.getElementById('camera').value = '35mm Film';
  document.getElementById('lens').value = 'Anamorphic';
  document.getElementById('aperture').value = 'f/1.4 Wide Open';
  generateShot();
}
function copyPrompt(){
  const txt = document.getElementById('compiledOut').textContent || document.getElementById('prompt').value;
  navigator.clipboard && navigator.clipboard.writeText(txt);
}

async function loadShots(){
  const r = await fetch('/api/higgsfield/shots'); const d = await r.json();
  document.getElementById('shots').innerHTML = (d.shots || []).map(s =>
    `<div class="shot"><strong>#${s.id}</strong> [${s.mode}] ${s.compiled_prompt}</div>`
  ).join('') || '<div class="muted">No shots yet.</div>';
}

function addMsg(cls, text){
  const el = document.createElement('div'); el.className = 'msg ' + cls; el.textContent = text;
  const log = document.getElementById('chatlog'); log.appendChild(el); log.scrollTop = log.scrollHeight;
}

async function sendChat(override){
  const input = document.getElementById('chatIn');
  const msg = (override !== undefined ? override : input.value).trim();
  if(!msg) return;
  if(override === undefined) input.value = '';
  const port = document.getElementById('chatPort').value;
  addMsg('me', `[YOU -> ${port.toUpperCase()}] ${msg}`);
  const r = await fetch('/api/allports/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({port, message:msg})});
  const d = await r.json();
  if(d.director_note) addMsg('ok', `[MR. HIGGS] ${d.director_note}`);
  for(const res of (d.results || [])){
    addMsg(res.ok ? 'ok' : 'err', `[:${res.port} HTTP ${res.http} · ${res.ms}ms] ${res.reply}`);
  }
}
loadShots();
</script>
</body>
</html>
"""

def handle_get(handler):
    path = urlparse(handler.path).path.rstrip("/") or "/"
    if path == "/giant":
        _send(handler, 200, "text/html; charset=utf-8", GIANT_HTML.encode("utf-8"))
        return True
    if path in ("/higgsfield", "/higginsfield", "/chat"):
        _send(handler, 200, "text/html; charset=utf-8", STUDIO_HTML.encode("utf-8"))
        return True
    if path == "/api/higgsfield/status":
        _init_db()
        with sqlite3.connect(DB_PATH, timeout=3) as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM shots").fetchone()[0]
        _send_json(handler, 200, {
            "status": "ONLINE",
            "studio": "Higgsfield Cinema Studio Local (No Login)",
            "cloud_bridge_configured": bool(os.environ.get("HIGGSFIELD_API_KEY")),
            "minimax_h3_configured": bool(os.environ.get("MINIMAX_API_KEY")),
            "models_supported": ["Higgsfield Cinema", "MiniMax H3"],
            "shots_saved": cnt,
            "chat_ports": sorted(PORT_ROUTES.keys()),
        })
        return True
    if path == "/api/higgsfield/shots":
        _init_db()
        with sqlite3.connect(DB_PATH, timeout=3) as conn:
            rows = conn.execute(
                "SELECT id, ts, prompt, compiled_prompt, mode FROM shots ORDER BY id DESC LIMIT 10"
            ).fetchall()
        _send_json(handler, 200, {
            "shots": [
                {"id": r[0], "ts": r[1], "prompt": r[2], "compiled_prompt": r[3], "mode": r[4]}
                for r in rows
            ]
        })
        return True
    return False

def handle_post(handler):
    path = urlparse(handler.path).path.rstrip("/") or "/"
    if path == "/api/higgsfield/generate":
        _init_db()
        d = _read_json(handler)
        prompt = str(d.get("prompt") or "Cinematic shot").strip()
        move = str(d.get("move") or "Dolly In")
        genre = str(d.get("genre") or "Action")
        camera = str(d.get("camera") or "35mm Film")
        lens = str(d.get("lens") or "Anamorphic")
        aperture = str(d.get("aperture") or "f/1.4 Wide Open")
        lighting = str(d.get("lighting") or "Soft Cross")
        aspect = str(d.get("aspect") or "16:9")
        duration = int(d.get("duration") or 6)
        engine = str(d.get("engine") or "Higgsfield Cinema").strip()
        h3_note = str(d.get("h3_note") or "").strip()
        h3_tag = f" | H3-Audio/Ref: {h3_note}" if (engine == "MiniMax H3" and h3_note) else (" | Native-Stereo-2K-24fps" if engine == "MiniMax H3" else "")
        compiled = (
            f"[{engine} | {genre} | #{move} | {camera} · {lens} · {aperture} | "
            f"{lighting} lighting | {aspect} · {duration}s{h3_tag}] {prompt}"
        )
        mode = "cloud_ready" if os.environ.get("HIGGSFIELD_API_KEY") else "local_preview"
        with sqlite3.connect(DB_PATH, timeout=3) as conn:
            cur = conn.execute(
                "INSERT INTO shots (ts, prompt, compiled_prompt, settings_json, mode) VALUES (?, ?, ?, ?, ?)",
                (int(time.time()), prompt, compiled, json.dumps(d), mode),
            )
            shot_id = cur.lastrowid
        _send_json(handler, 200, {"ok": True, "id": shot_id, "mode": mode, "compiled_prompt": compiled})
        return True

    if path == "/api/allports/chat":
        d = _read_json(handler)
        port = str(d.get("port") or "all").lower()
        msg = str(d.get("message") or "ping").strip()
        targets = sorted(PORT_ROUTES.keys()) if port == "all" else [port]
        results = [_probe_port(p, msg) for p in targets]
        note = None
        if any(k in msg.lower() for k in ("shot", "camera", "scene", "lens", "higgs", "video", "minimax", "h3", "hailuo")):
            note = f"Suggested setup for '{msg}': MiniMax H3 / #Dolly In + 35mm Film + Anamorphic f/1.4 + Contre-jour lighting + native stereo audio."
        _send_json(handler, 200, {"ok": True, "target": port, "director_note": note, "results": results})
        return True

    if path == "/api/higgsfield/dispatch_cloud":
        d = _read_json(handler)
        provider = str(d.get("provider") or "minimax").lower()
        prompt = str(d.get("prompt") or "").strip()
        if not prompt:
            _send_json(handler, 400, {"ok": False, "error": "prompt is required"})
            return True
        if provider == "minimax":
            key = os.environ.get("MINIMAX_API_KEY", "").strip()
            if not key:
                _send_json(handler, 200, {"ok": False, "configured": False, "provider": "minimax", "error": "Set MINIMAX_API_KEY in Termux env before live dispatch"})
                return True
            req_obj = urllib.request.Request(
                "https://api.minimax.io/v1/video_generation",
                data=json.dumps({"model": "MiniMax-H3", "prompt": prompt[:2000], "duration": int(d.get("duration") or 10)}).encode("utf-8"),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
        else:
            key = os.environ.get("HIGGSFIELD_API_KEY", "").strip()
            if not key:
                _send_json(handler, 200, {"ok": False, "configured": False, "provider": "higgsfield", "error": "Set HIGGSFIELD_API_KEY in Termux env before live dispatch"})
                return True
            req_obj = urllib.request.Request(
                "https://api.higgsfield.ai/v1/video/generations",
                data=json.dumps({"prompt": prompt[:2000]}).encode("utf-8"),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
        try:
            with urllib.request.urlopen(req_obj, timeout=15) as resp:
                body = resp.read(2048).decode("utf-8", errors="replace")
            _send_json(handler, 200, {"ok": True, "provider": provider, "response": body})
        except Exception as e:
            _send_json(handler, 502, {"ok": False, "provider": provider, "error": str(e)})
        return True
    return False
