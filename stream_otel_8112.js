const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");

const PORT = Number(process.env.STREAM_OTEL_PORT || 8112);
const RAM_FLOOR_MIB = 520.0;
const WATCH_PORTS = [8088, 8090, 8095, 8099, 8110, 8112, 8125, 8170, 8160];
const PORT_PATHS = { 8110: "/api/telemetry/status", 8125: "/api/telemetry/iot-process" };
const OLLAMA_BASE = (process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/+$/, "");
const OLLAMA_MODEL = process.env.GOD_QWEN_MODEL || "god-qwen:latest";
const HOME_DIR = process.env.HOME || "/data/data/com.termux/files/home";
const REPO_DIR = path.join(HOME_DIR, "live-command-center");

const PORT_CMDS = {
  8088: `cd "${HOME_DIR}" && nohup python3 -u "${HOME_DIR}/dashboard_server.py" >>"${HOME_DIR}/astra_logs/dash-8088.log" 2>&1 </dev/null &`,
  8090: `cd "${REPO_DIR}" && nohup python3 -u "${REPO_DIR}/alstra_unified_8090_gateway.py" >>"${HOME_DIR}/astra_logs/gw-8090.log" 2>&1 </dev/null &`,
  8095: `cd "${HOME_DIR}" && nohup python3 -u "${HOME_DIR}/alstra_master_spine_8095.py" >>"${HOME_DIR}/astra_logs/spine-8095.log" 2>&1 </dev/null &`,
  8099: `cd "${HOME_DIR}" && nohup python3 -u "${HOME_DIR}/alstra_genius_brain_8099.py" >>"${HOME_DIR}/astra_logs/brain-8099.log" 2>&1 </dev/null &`,
  8110: `cd "${HOME_DIR}" && nohup python3 -u "${HOME_DIR}/astra-enterprise-core/runtime_backup/telemetry_assistant.py" >>"${HOME_DIR}/astra_logs/telem-8110.log" 2>&1 </dev/null &`,
  8112: `cd "${HOME_DIR}" && nohup node "${TARGET_8112}" >>"${HOME_DIR}/tmp/stream_8112.log" 2>&1 </dev/null &`,
  8125: `cd "${HOME_DIR}" && nohup python3 -u "${HOME_DIR}/iot_handler.py" >>"${HOME_DIR}/astra_logs/iot-8125.log" 2>&1 </dev/null &`,
  8170: `cd "${HOME_DIR}" && nohup python3 -u "${HOME_DIR}/local_shm_monitor/shm_port_monitor.py" >>"${HOME_DIR}/astra_logs/shm-8170.log" 2>&1 </dev/null &`,
};

const state = {
  started_at: Date.now(),
  ws_clients: new Set(),
  stream_events: [],
  chat_history: [],
  action_log: [],
  otel_metrics_batches: 0,
  otel_logs_batches: 0,
  fluentbit_records: 0,
  prom_scrapes: 0,
  last_probe: [],
};

function readFreeRamMib() {
  try {
    const m = fs.readFileSync("/proc/meminfo", "utf8").match(/MemAvailable:\s+(\d+)/);
    if (m) return Number((Number(m[1]) / 1024).toFixed(1));
  } catch (_) {}
  return 0;
}

function recordAction(kind, detail, ok = true) {
  const row = {
    ts: new Date().toISOString().slice(11, 19),
    kind,
    detail,
    ok,
  };
  state.action_log.push(row);
  if (state.action_log.length > 80) state.action_log.shift();
  return row;
}

function pushEvent(platform, kind, payload) {
  const item = {
    id: state.stream_events.length + 1,
    ts: new Date().toISOString().slice(11, 19),
    platform: String(platform || "lightning").toLowerCase(),
    kind: String(kind || "forensic"),
    payload,
  };
  state.stream_events.push(item);
  if (state.stream_events.length > 140) state.stream_events.shift();

  const frame = JSON.stringify({ type: "stream_event", data: item });
  for (const sock of state.ws_clients) {
    try {
      const buf = Buffer.from(frame, "utf8");
      const len = buf.length;
      const hdr = len < 126
        ? Buffer.from([0x81, len])
        : Buffer.concat([Buffer.from([0x81, 126]), Buffer.from([(len >> 8) & 255, len & 255])]);
      sock.write(Buffer.concat([hdr, buf]));
    } catch (_) {
      state.ws_clients.delete(sock);
    }
  }
  return item;
}

function probePort(p) {
  const probePath = PORT_PATHS[Number(p)] || "/";
  return new Promise((resolve) => {
    const t0 = Date.now();
    const req = http.get({ host: "127.0.0.1", port: p, path: probePath, timeout: 650 }, (res) => {
      res.resume();
      const sc = res.statusCode || 200;
      resolve({ port: p, up: sc < 500, code: sc, ms: Date.now() - t0 });
    });
    req.on("timeout", () => { req.destroy(); resolve({ port: p, up: false, code: 0, ms: 650 }); });
    req.on("error", () => resolve({ port: p, up: false, code: 0, ms: Date.now() - t0 }));
  });
}

async function refreshProbes() {
  state.last_probe = await Promise.all(WATCH_PORTS.map(probePort));
  return state.last_probe;
}

function httpJsonPost(baseUrl, pathName, payload, timeoutMs) {
  return new Promise((resolve, reject) => {
    const u = new URL(baseUrl);
    const body = JSON.stringify(payload);
    const req = http.request(
      {
        hostname: u.hostname,
        port: Number(u.port || 11434),
        path: pathName,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
        timeout: timeoutMs,
      },
      (res) => {
        let buf = "";
        res.on("data", (c) => { buf += c; });
        res.on("end", () => {
          if ((res.statusCode || 500) >= 400) {
            return reject(new Error(`HTTP ${res.statusCode}: ${buf.slice(0, 180)}`));
          }
          try {
            resolve(JSON.parse(buf));
          } catch (err) {
            reject(err);
          }
        });
      }
    );
    req.on("timeout", () => { req.destroy(); reject(new Error("timeout")); });
    req.on("error", (err) => reject(err));
    req.write(body);
    req.end();
  });
}

async function askGodQwen(prompt, probes) {
  const up = probes.filter((x) => x.up).map((x) => ":" + x.port).join(", ") || "none";
  const ram = readFreeRamMib();
  const sysCtx = `Forensic Blue-Lightning HUD | Online nodes: ${up} | Free RAM: ${ram} MiB (floor ${RAM_FLOOR_MIB} MiB). Respond directly and concisely.`;

  try {
    const chatRes = await httpJsonPost(
      OLLAMA_BASE,
      "/api/chat",
      {
        model: OLLAMA_MODEL,
        stream: false,
        messages: [
          { role: "system", content: sysCtx },
          { role: "user", content: prompt },
        ],
      },
      30000
    );
    const txt = (chatRes && chatRes.message && chatRes.message.content) || "";
    if (txt.trim()) {
      return { reply: txt.trim(), engine: `ollama:${OLLAMA_MODEL}` };
    }
  } catch (_) {}

  try {
    const genRes = await httpJsonPost(
      OLLAMA_BASE,
      "/api/generate",
      {
        model: OLLAMA_MODEL,
        system: sysCtx,
        prompt,
        stream: false,
      },
      30000
    );
    const txt = (genRes && genRes.response) || "";
    if (txt.trim()) {
      return { reply: txt.trim(), engine: `ollama:${OLLAMA_MODEL}` };
    }
  } catch (err) {
    return {
      reply: `Ollama unreachable at ${OLLAMA_BASE} for "${OLLAMA_MODEL}" (${err.message}). Free RAM: ${ram} MiB (floor >= ${RAM_FLOOR_MIB} MiB).`,
      engine: "ollama_offline",
    };
  }

  return {
    reply: `Empty response from ${OLLAMA_MODEL} at ${OLLAMA_BASE}.`,
    engine: "ollama_empty",
  };
}

function runShellShort(cmdStr, timeoutSec = 20) {
  return new Promise((resolve) => {
    execFile("bash", ["-lc", cmdStr], { timeout: timeoutSec * 1000, maxBuffer: 512 * 1024 }, (err, stdout, stderr) => {
      resolve({
        ok: !err,
        code: err ? (err.code || 1) : 0,
        stdout: String(stdout || "").trim().slice(-1200),
        stderr: String(stderr || "").trim().slice(-600),
      });
    });
  });
}

function jsonOut(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Access-Control-Allow-Origin": "*",
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
  });
}

const HUD_LIGHTNING_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"/>
<title>FORENSIC BLUE-LIGHTNING // :8112</title>
<style>
  :root{
    --bg:#020611;--panel:#071022;--panel2:#0a162e;--line:#16325b;--line-hi:#38bdf8;
    --txt:#e8f4ff;--muted:#7aa2cc;--bolt:#38bdf8;--cyan:#22d3ee;--amber:#fbbf24;
    --ok:#34d399;--err:#fb7185
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0;width:100vw;height:100dvh;overflow:hidden;background:var(--bg);color:var(--txt);font:11px/1.3 "JetBrains Mono",ui-monospace,monospace}
  .shell{display:grid;grid-template-rows:34px 1fr;width:100%;height:100%}
  .top{display:flex;justify-content:space-between;align-items:center;padding:0 10px;background:#040a17;border-bottom:1px solid var(--line);gap:8px;white-space:nowrap;overflow:hidden}
  .brand{color:var(--bolt);font-weight:700;letter-spacing:.08em;text-shadow:0 0 10px #38bdf866}
  .pill{padding:2px 7px;border-radius:999px;border:1px solid #38bdf855;background:#091830;color:var(--cyan);font-size:10px}
  .grid{display:grid;grid-template-columns:270px 1fr 330px;gap:7px;padding:7px;min-height:0;height:100%}
  @media(max-width:980px){.grid{grid-template-columns:1fr;grid-template-rows:auto 175px 1fr}}
  .box{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:7px;display:flex;flex-direction:column;min-height:0;overflow:hidden}
  .hdr{display:flex;justify-content:space-between;align-items:center;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:5px}
  .ports{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-bottom:6px}
  .pcell{background:var(--panel2);border:1px solid var(--line);border-radius:6px;padding:4px 5px;display:flex;flex-direction:column;gap:2px}
  .pcell.up{border-color:#38bdf877}
  .pcell.dn{border-color:#fb718555;opacity:.85}
  .ptop{display:flex;justify-content:space-between;font-weight:700;font-size:10px}
  .up .ptop{color:var(--cyan)} .dn .ptop{color:var(--err)}
  .pacts{display:flex;gap:3px}
  .pbtn{flex:1;background:#0c1e3b;color:var(--txt);border:1px solid #24487a;border-radius:4px;padding:1px 3px;font:inherit;font-size:9px;cursor:pointer}
  .pbtn:hover{border-color:var(--bolt);color:var(--bolt)}
  .wf-row{display:grid;grid-template-columns:repeat(2,1fr);gap:4px;margin-bottom:6px}
  .wbtn{background:#091933;color:var(--bolt);border:1px solid #224a80;border-radius:5px;padding:5px 6px;font:inherit;font-size:10px;font-weight:700;cursor:pointer;text-align:left}
  .wbtn:hover{background:#0f274d;border-color:var(--cyan)}
  .feed{flex:1;min-height:0;overflow:auto;background:#040914;border:1px solid var(--line);border-radius:6px;padding:5px;font-size:10px}
  .line{margin-bottom:3px;word-break:break-word}
  .u{color:var(--cyan)} .a{color:var(--ok)} .s{color:var(--muted)} .e{color:var(--err)}
  .stage{position:relative;background:#030814;border:1px solid var(--line);border-radius:8px;min-height:0;overflow:hidden;display:flex;flex-direction:column}
  canvas#boltCanvas{width:100%;height:100%;display:block;flex:1;min-height:0}
  .ov-l{position:absolute;top:7px;left:9px;font-size:10px;color:var(--bolt);pointer-events:none;text-shadow:0 0 8px #38bdf866}
  .ov-r{position:absolute;top:7px;right:9px;font-size:10px;color:var(--cyan);text-align:right;pointer-events:none}
  .bar{display:flex;gap:4px;margin-top:5px}
  input{flex:1;min-width:0;background:#040914;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:5px 7px;font:inherit;font-size:11px}
  input:focus{outline:none;border-color:var(--bolt)}
  .go{background:var(--bolt);color:#020914;border:0;border-radius:6px;padding:5px 9px;font:inherit;font-size:10px;font-weight:700;cursor:pointer}
</style>
</head>
<body>
<div class="shell">
  <div class="top">
    <span class="brand">⚡ FORENSIC BLUE-LIGHTNING // FULL BOARD CONTROL (:8112)</span>
    <span class="pill" id="topTelemetry">RAM -- / 520.0 MiB · MODEL ${OLLAMA_MODEL}</span>
  </div>
  <div class="grid">
    <div class="box">
      <div class="hdr"><span>PORT MATRIX &amp; CONTROLS</span><span id="upSummary">--</span></div>
      <div class="ports" id="portMatrix"></div>
      <div class="hdr"><span>WORKFLOW TRIGGERS</span><span>SHIELD</span></div>
      <div class="wf-row">
        <button class="wbtn" onclick="runWorkflow('verify_shield')">⚡ SHIELD VERIFY</button>
        <button class="wbtn" onclick="runWorkflow('backup_snapshot')">💾 BACKUP TAR.GZ</button>
        <button class="wbtn" onclick="runWorkflow('ping_8099')">🧠 PING :8099 DIRECTIVE</button>
        <button class="wbtn" onclick="runWorkflow('refresh_all')">🔄 FORCE PROBE SWEEP</button>
      </div>
      <div class="hdr"><span>FORENSIC TRACE &amp; AUDIT LOG</span><span id="pipeTag">--</span></div>
      <div class="feed" id="auditFeed"></div>
    </div>

    <div class="stage">
      <div class="ov-l" id="boltStatus">BLUE-LIGHTNING TELEMETRY ARC // FORENSIC LOCK</div>
      <div class="ov-r" id="boltMeta">NODES -- · WS 0</div>
      <canvas id="boltCanvas"></canvas>
    </div>

    <div class="box">
      <div class="hdr"><span>GOD-QWEN LIVE CONSOLE</span><span id="engineBadge">READY</span></div>
      <div class="feed" id="consoleOut" style="margin-bottom:4px">
        <div class="line s">[⚡] Forensic Blue-Lightning console ready. Control ports, inspect telemetry, or query god-qwen:latest.</div>
      </div>
      <div class="hdr" style="margin-top:4px"><span>DIRECTIVE / STREAM INJECT</span><span>:8099 + :8112</span></div>
      <div class="bar" style="margin-top:0;margin-bottom:5px">
        <input id="dirIn" placeholder="Push directive to :8099 & stream event..." onkeydown="if(event.key==='Enter')sendDirective()"/>
        <button class="go" onclick="sendDirective()">PUSH</button>
      </div>
      <div class="bar" style="margin-top:0">
        <input id="qwenIn" placeholder="Ask god-qwen:latest..." onkeydown="if(event.key==='Enter')sendQwen()"/>
        <button class="go" onclick="sendQwen()">SEND</button>
      </div>
    </div>
  </div>
</div>
<script>
const cv = document.getElementById("boltCanvas"), ctx = cv.getContext("2d");
let tick = 0, surge = 0, upCount = 0, totalCount = 9, freeRam = 0, wsCount = 0;

function fit(){
  const r = cv.getBoundingClientRect();
  cv.width = Math.max(220, Math.floor(r.width * (window.devicePixelRatio || 1)));
  cv.height = Math.max(160, Math.floor(r.height * (window.devicePixelRatio || 1)));
}
window.addEventListener("resize", fit);
fit();

function drawLightning(){
  tick += 0.025;
  surge = Math.max(0, surge - 0.035);
  const w = cv.width, h = cv.height, cx = w / 2, cy = h / 2;
  const baseR = Math.min(w, h) * (0.27 + surge * 0.06);

  ctx.fillStyle = "#030814";
  ctx.fillRect(0, 0, w, h);

  // Forensic radar grid
  ctx.strokeStyle = "#16325b55";
  ctx.lineWidth = 1;
  for(let r of [0.45, 0.72, 1.0]){
    ctx.beginPath();
    ctx.arc(cx, cy, baseR * r * 1.25, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Blue lightning radial bolts
  const rays = 6;
  for(let i = 0; i < rays; i++){
    const ang = (i / rays) * Math.PI * 2 + tick * 0.35;
    const x0 = cx + Math.cos(ang) * (baseR * 0.42);
    const y0 = cy + Math.sin(ang) * (baseR * 0.42);
    const x1 = cx + Math.cos(ang) * (baseR * 1.25);
    const y1 = cy + Math.sin(ang) * (baseR * 1.25);
    ctx.strokeStyle = i % 2 === 0 ? "#38bdf8cc" : "#22d3ee99";
    ctx.lineWidth = 1.4 + surge * 2;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    const segs = 5;
    for(let s = 1; s < segs; s++){
      const t = s / segs;
      const jitter = (Math.sin(tick * 7 + i * 3 + s * 5) * 8) * (1 + surge);
      const nx = -Math.sin(ang) * jitter;
      const ny = Math.cos(ang) * jitter;
      ctx.lineTo(x0 + (x1 - x0) * t + nx, y0 + (y1 - y0) * t + ny);
    }
    ctx.lineTo(x1, y1);
    ctx.stroke();
  }

  // Gyro core ring
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(cx, cy, baseR * 0.75, Math.max(8, Math.abs(Math.sin(tick)) * baseR * 0.75), tick * 0.2, 0, Math.PI * 2);
  ctx.stroke();

  ctx.fillStyle = "#e8f4ff";
  ctx.font = "bold 12px monospace";
  ctx.textAlign = "center";
  ctx.fillText("⚡ " + upCount + "/" + totalCount + " ONLINE · " + freeRam.toFixed(1) + " MiB", cx, cy + 4);
  requestAnimationFrame(drawLightning);
}
drawLightning();

function esc(s){ return String(s || "").replace(/[&<>]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;" }[c])); }

async function portAction(port, action){
  surge = 0.8;
  const r = await fetch("/api/control/port", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ port, action })
  });
  const d = await r.json();
  const out = document.getElementById("consoleOut");
  out.innerHTML += '<div class="line ' + (d.ok ? "a" : "e") + '">[PORT :' + port + ' ' + action + '] ' + esc(d.message || JSON.stringify(d)) + '</div>';
  out.scrollTop = out.scrollHeight;
  refreshState();
}

async function runWorkflow(workflow){
  surge = 0.9;
  const r = await fetch("/api/control/workflow", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow })
  });
  const d = await r.json();
  const out = document.getElementById("consoleOut");
  out.innerHTML += '<div class="line ' + (d.ok ? "a" : "e") + '">[WF ' + workflow + '] ' + esc(d.stdout || d.stderr || d.message || "") + '</div>';
  out.scrollTop = out.scrollHeight;
  refreshState();
}

async function sendDirective(){
  const inp = document.getElementById("dirIn");
  const directive = inp.value.trim();
  if(!directive) return;
  inp.value = "";
  surge = 0.7;
  const r = await fetch("/api/control/directive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ directive })
  });
  const d = await r.json();
  const out = document.getElementById("consoleOut");
  out.innerHTML += '<div class="line u">[DIR] ' + esc(directive) + ' -> ' + esc(JSON.stringify(d.brain_8099 || d)) + '</div>';
  out.scrollTop = out.scrollHeight;
  refreshState();
}

async function sendQwen(){
  const inp = document.getElementById("qwenIn");
  const prompt = inp.value.trim();
  if(!prompt) return;
  inp.value = "";
  surge = 1.0;
  const out = document.getElementById("consoleOut");
  out.innerHTML += '<div class="line u">&gt; ' + esc(prompt) + '</div>';
  const r = await fetch("/api/god-qwen/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt })
  });
  const d = await r.json();
  document.getElementById("engineBadge").textContent = d.engine || "GOD-QWEN";
  out.innerHTML += '<div class="line a">' + esc(d.reply || "") + '</div>';
  out.scrollTop = out.scrollHeight;
  refreshState();
}

async function refreshState(){
  try {
    const r = await fetch("/api/hud/status");
    const d = await r.json();
    const probes = d.probes || [];
    totalCount = probes.length || 9;
    upCount = probes.filter(x => x.up).length;
    freeRam = Number(d.free_ram_mib || 0);
    wsCount = Number(d.ws_clients || 0);

    document.getElementById("topTelemetry").textContent =
      "RAM " + freeRam.toFixed(1) + " / 520.0 MiB · MODEL " + (d.model || "god-qwen:latest");
    document.getElementById("upSummary").textContent = upCount + "/" + totalCount + " UP";
    document.getElementById("boltMeta").textContent = "NODES " + upCount + "/" + totalCount + " · WS " + wsCount;
    document.getElementById("pipeTag").textContent = "OTel:" + (d.otel.metrics_batches + d.otel.logs_batches) + " FB:" + d.fluentbit_records;

    document.getElementById("portMatrix").innerHTML = probes.map(p =>
      '<div class="pcell ' + (p.up ? "up" : "dn") + '">' +
        '<div class="ptop"><span>:' + p.port + '</span><span>' + (p.up ? p.code : "OFF") + '</span></div>' +
        '<div class="pacts">' +
          '<button class="pbtn" onclick="portAction(' + p.port + ',\'start\')">UP</button>' +
          '<button class="pbtn" onclick="portAction(' + p.port + ',\'stop\')">DN</button>' +
        '</div>' +
      '</div>'
    ).join("");

    const acts = (d.actions || []).slice(-6).reverse().map(a =>
      '<div class="line ' + (a.ok ? "a" : "e") + '">[' + esc(a.ts) + '] ' + esc(a.kind) + ': ' + esc(a.detail) + '</div>'
    );
    const evs = (d.events || []).slice(-6).reverse().map(e =>
      '<div class="line s">[' + esc(e.ts) + '] ' + esc(e.platform) + ':' + esc(e.kind) + ' ' + esc(JSON.stringify(e.payload).slice(0,54)) + '</div>'
    );
    document.getElementById("auditFeed").innerHTML = acts.concat(evs).join("");
  } catch(_){}
}

refreshState();
setInterval(refreshState, 3000);
</script>
</body>
</html>
`;

const server = http.createServer(async (req, res) => {
  const url = (req.url || "/").split("?")[0];

  if (req.method === "GET" && (url === "/" || url === "/hud" || url === "/v4" || url === "/giant" || url === "/forensic" || url === "/lightning")) {
    const body = Buffer.from(HUD_LIGHTNING_HTML, "utf8");
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Content-Length": body.length });
    return res.end(body);
  }

  if (req.method === "GET" && url === "/api/hud/status") {
    const probes = await refreshProbes();
    const freeRam = readFreeRamMib();
    return jsonOut(res, 200, {
      ok: true,
      hud_version: "V4-LIGHTNING",
      model: OLLAMA_MODEL,
      ram_floor_mib: RAM_FLOOR_MIB,
      free_ram_mib: freeRam,
      ws_clients: state.ws_clients.size,
      probes,
      events: state.stream_events.slice(-25),
      actions: state.action_log.slice(-25),
      otel: { metrics_batches: state.otel_metrics_batches, logs_batches: state.otel_logs_batches },
      fluentbit_records: state.fluentbit_records,
      prom_scrapes: state.prom_scrapes,
    });
  }

  if (req.method === "POST" && url === "/api/control/port") {
    const raw = await readBody(req);
    let p = {};
    try { p = JSON.parse(raw || "{}"); } catch (_) {}
    const targetPort = Number(p.port);
    const action = String(p.action || "start").toLowerCase();
    if (!PORT_CMDS[targetPort]) {
      return jsonOut(res, 400, { ok: false, message: `Port :${targetPort} is not controllable via PORT_CMDS` });
    }
    const freeRam = readFreeRamMib();
    if (action === "stop") {
      if (targetPort === PORT) {
        recordAction("port_stop", `Blocked self-stop on :${PORT}`, false);
        return jsonOut(res, 400, { ok: false, message: `Refusing to stop active HUD port :${PORT}` });
      }
      await runShellShort(`pkill -f ":${targetPort}|port.*${targetPort}|_${targetPort}\\.py" 2>/dev/null || true`, 5);
      const act = recordAction("port_stop", `Stopped listeners matching :${targetPort} (RAM ${freeRam} MiB)`, true);
      pushEvent("control", "port_stop", { port: targetPort });
      return jsonOut(res, 200, { ok: true, message: act.detail, action: act });
    }
    if (freeRam < RAM_FLOOR_MIB) {
      const act = recordAction("port_start_hold", `Held :${targetPort} start — RAM ${freeRam} MiB < ${RAM_FLOOR_MIB} MiB`, false);
      return jsonOut(res, 200, { ok: false, held: true, message: act.detail, action: act });
    }
    const out = await runShellShort(PORT_CMDS[targetPort], 8);
    const act = recordAction("port_start", `Started :${targetPort} (RAM ${freeRam} MiB)`, out.ok);
    pushEvent("control", "port_start", { port: targetPort, ok: out.ok });
    return jsonOut(res, 200, { ok: out.ok, message: act.detail, stdout: out.stdout, stderr: out.stderr, action: act });
  }

  if (req.method === "POST" && url === "/api/control/workflow") {
    const raw = await readBody(req);
    let p = {};
    try { p = JSON.parse(raw || "{}"); } catch (_) {}
    const wf = String(p.workflow || "").trim();
    const freeRam = readFreeRamMib();
    let cmd = "";
    if (wf === "verify_shield") {
      cmd = `cd "${REPO_DIR}" && ./protect_main.sh verify`;
    } else if (wf === "backup_snapshot") {
      cmd = `mkdir -p "${HOME_DIR}/backups" && tar -czf "${HOME_DIR}/backups/astra_lightning_$(date +%Y%m%d_%H%M%S).tar.gz" -C "${HOME_DIR}" stream_otel_8112.js alstra_genius_brain_8099.py dashboard_server.py higgsfield_studio.py astra_ram70.py astra_stack_boot.sh 2>/dev/null && ls -lh "${HOME_DIR}/backups" | tail -n 2`;
    } else if (wf === "ping_8099") {
      cmd = `curl -sS --max-time 2 -X POST -H 'Content-Type: application/json' -d '{"directive":"lightning-hud-ping"}' "http://127.0.0.1:8099/api/directive"`;
    } else if (wf === "refresh_all") {
      const probes = await refreshProbes();
      const act = recordAction("probe_sweep", `Probed ${probes.length} ports (RAM ${freeRam} MiB)`, true);
      return jsonOut(res, 200, { ok: true, message: act.detail, probes });
    } else {
      return jsonOut(res, 400, { ok: false, message: `Unknown workflow: ${wf}` });
    }
    const resExec = await runShellShort(cmd, 25);
    const act = recordAction(`wf_${wf}`, `exit=${resExec.code} (RAM ${freeRam} MiB)`, resExec.ok);
    pushEvent("workflow", wf, { ok: resExec.ok, code: resExec.code });
    return jsonOut(res, 200, { ok: resExec.ok, workflow: wf, stdout: resExec.stdout, stderr: resExec.stderr, action: act });
  }

  if (req.method === "POST" && url === "/api/control/directive") {
    const raw = await readBody(req);
    let p = {};
    try { p = JSON.parse(raw || "{}"); } catch (_) { p = { directive: raw }; }
    const directive = String(p.directive || "").trim();
    if (!directive) return jsonOut(res, 400, { ok: false, message: "Empty directive" });
    const ev = pushEvent("directive", "dispatched", { directive });
    const brainRes = await runShellShort(
      `curl -sS --max-time 2 -X POST -H 'Content-Type: application/json' -d ${JSON.stringify(JSON.stringify({ directive }))} "http://127.0.0.1:8099/api/directive" || echo '{"ok":false,"error":"8099_unreachable"}'`,
      5
    );
    let parsedBrain = null;
    try { parsedBrain = JSON.parse(brainRes.stdout || "null"); } catch (_) { parsedBrain = { raw: brainRes.stdout }; }
    recordAction("directive", `${directive.slice(0, 56)}`, true);
    return jsonOut(res, 200, { ok: true, event: ev, brain_8099: parsedBrain });
  }

  if (req.method === "POST" && url === "/api/god-qwen/chat") {
    const raw = await readBody(req);
    let parsed = {};
    try { parsed = JSON.parse(raw || "{}"); } catch (_) { parsed = { prompt: raw }; }
    const prompt = String(parsed.prompt || "status").trim();
    const probes = await refreshProbes();
    const ans = await askGodQwen(prompt, probes);
    const entry = { ts: new Date().toISOString().slice(11, 19), prompt, reply: ans.reply, engine: ans.engine };
    state.chat_history.push(entry);
    if (state.chat_history.length > 60) state.chat_history.shift();
    pushEvent("god-qwen", "console", { prompt: prompt.slice(0, 60), engine: ans.engine });
    return jsonOut(res, 200, { ok: true, model: OLLAMA_MODEL, ...ans });
  }

  if (req.method === "GET" && url === "/api/stream/events") {
    return jsonOut(res, 200, { ok: true, events: state.stream_events.slice(-50) });
  }

  if (req.method === "POST" && url === "/api/stream/event") {
    const raw = await readBody(req);
    let parsed = {};
    try { parsed = JSON.parse(raw || "{}"); } catch (_) { parsed = { text: raw }; }
    const item = pushEvent(parsed.platform || "kick", parsed.kind || "chat", parsed.payload || parsed);
    return jsonOut(res, 200, { ok: true, event: item });
  }

  if (req.method === "POST" && (url === "/v1/metrics" || url === "/api/otel/metrics")) {
    await readBody(req);
    state.otel_metrics_batches += 1;
    return jsonOut(res, 200, { ok: true, accepted_batches: state.otel_metrics_batches });
  }

  if (req.method === "POST" && (url === "/v1/logs" || url === "/api/otel/logs")) {
    await readBody(req);
    state.otel_logs_batches += 1;
    return jsonOut(res, 200, { ok: true, accepted_batches: state.otel_logs_batches });
  }

  if (req.method === "POST" && (url === "/api/fluentbit/ingest" || url === "/fluentbit")) {
    const raw = await readBody(req);
    let count = 1;
    try {
      const p = JSON.parse(raw || "[]");
      count = Array.isArray(p) ? Math.max(1, p.length) : 1;
    } catch (_) {
      count = Math.max(1, raw.trim().split("\n").filter(Boolean).length);
    }
    state.fluentbit_records += count;
    return jsonOut(res, 200, { ok: true, ingested: count, total_records: state.fluentbit_records });
  }

  if (req.method === "GET" && url === "/metrics") {
    state.prom_scrapes += 1;
    const probes = await refreshProbes();
    const rssMb = (process.memoryUsage().rss / (1024 * 1024)).toFixed(2);
    const upSec = Math.floor((Date.now() - state.started_at) / 1000);
    const lines = [
      "# HELP astra_bridge_up Forensic Blue-Lightning HUD bridge status",
      "# TYPE astra_bridge_up gauge",
      "astra_bridge_up 1",
      "# HELP astra_bridge_rss_mb Process RSS in MiB",
      "# TYPE astra_bridge_rss_mb gauge",
      `astra_bridge_rss_mb ${rssMb}`,
      "# HELP astra_bridge_uptime_seconds Bridge uptime in seconds",
      "# TYPE astra_bridge_uptime_seconds counter",
      `astra_bridge_uptime_seconds ${upSec}`,
      "# HELP astra_watched_port_up Monitored local port status",
      "# TYPE astra_watched_port_up gauge",
      ...probes.map((x) => `astra_watched_port_up{port="${x.port}"} ${x.up ? 1 : 0}`),
    ];
    res.writeHead(200, { "Content-Type": "text/plain; version=0.0.4; charset=utf-8" });
    return res.end(lines.join("\n") + "\n");
  }

  jsonOut(res, 404, { ok: false, error: "not_found", path: url });
});

server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) { socket.destroy(); return; }
  const accept = crypto.createHash("sha1").update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
  socket.write("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n");
  state.ws_clients.add(socket);
  socket.on("close", () => state.ws_clients.delete(socket));
  socket.on("error", () => state.ws_clients.delete(socket));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[⚡] Forensic Blue-Lightning HUD active on 127.0.0.1:${PORT}`);
});
