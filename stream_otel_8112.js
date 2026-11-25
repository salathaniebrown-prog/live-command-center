const http = require("http");
const crypto = require("crypto");
const fs = require("fs");

const PORT = Number(process.env.STREAM_OTEL_PORT || 8112);
const WATCH_PORTS = [8088, 8090, 8160, 8095, 8099, 8110, 8125, 8170];
const GOD_QWEN_URL = process.env.GOD_QWEN_URL || "http://127.0.0.1:11434/api/generate";
const GOD_QWEN_MODEL = process.env.GOD_QWEN_MODEL || "god-qwen:latest";

const state = {
  started_at: Date.now(),
  ws_clients: new Set(),
  stream_events: [],
  chat_history: [],
  otel_metrics_batches: 0,
  otel_logs_batches: 0,
  fluentbit_records: 0,
  prom_scrapes: 0,
  last_probe: [],
};

function pushEvent(platform, kind, payload) {
  const item = {
    id: state.stream_events.length + 1,
    ts: new Date().toISOString().slice(11, 19),
    platform: String(platform || "kick").toLowerCase(),
    kind: String(kind || "node"),
    payload,
  };
  state.stream_events.push(item);
  if (state.stream_events.length > 120) state.stream_events.shift();

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

const PORT_PATHS = { 8110: "/api/telemetry/status", 8125: "/api/telemetry/iot-process" };
function probePort(p) {
  const probePath = PORT_PATHS[Number(p)] || "/";
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port: p, path: probePath, timeout: 650 }, (res) => {
      res.resume();
      const sc = res.statusCode || 200;
      resolve({ port: p, up: sc < 500, code: sc });
    });
    req.on("timeout", () => { req.destroy(); resolve({ port: p, up: false, code: 0 }); });
    req.on("error", () => resolve({ port: p, up: false, code: 0 }));
  });
}

async function refreshProbes() {
  state.last_probe = await Promise.all(WATCH_PORTS.map(probePort));
  return state.last_probe;
}



const OLLAMA_BASE = (process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/+$/, "");
const OLLAMA_MODEL = process.env.GOD_QWEN_MODEL || "god-qwen:latest";

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
  const sysCtx = `Live nodes online: ${up}. Respond concisely and directly.`;

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
      reply: `Ollama unreachable at ${OLLAMA_BASE} for model "${OLLAMA_MODEL}" (${err.message}). Start Ollama when MemAvailable >= 520.0 MiB to run live inference.`,
      engine: "ollama_offline",
    };
  }

  return {
    reply: `Empty response from ${OLLAMA_MODEL} at ${OLLAMA_BASE}.`,
    engine: "ollama_empty",
  };
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

const HUD_V4_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"/>
<title>Giant Tactical HUD V4 - :8112 - god-qwen:latest</title>
<style>
  :root{--bg:#04070d;--panel:#0b111c;--line:#1c2a3e;--txt:#e6f1ff;--muted:#7d93b2;--cyan:#22d3ee;--amber:#fbbf24;--emerald:#34d399;--rose:#fb7185}
  *{box-sizing:border-box}
  html,body{margin:0;padding:0;width:100vw;height:100dvh;overflow:hidden;background:var(--bg);color:var(--txt);font:12px/1.3 "JetBrains Mono",ui-monospace,monospace}
  .hud{display:grid;grid-template-rows:34px 1fr;width:100%;height:100%}
  .topbar{display:flex;justify-content:space-between;align-items:center;padding:0 12px;background:#070c15;border-bottom:1px solid var(--line);font-size:11px;white-space:nowrap;overflow:hidden}
  .brand{color:var(--cyan);font-weight:700;letter-spacing:.06em}
  .main{display:grid;grid-template-columns:250px 1fr 320px;gap:8px;padding:8px;min-height:0;height:100%}
  @media(max-width:960px){.main{grid-template-columns:1fr;grid-template-rows:auto 170px 1fr}}
  .col{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px;display:flex;flex-direction:column;min-height:0;overflow:hidden}
  .title{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px;display:flex;justify-content:space-between}
  .nodes{display:grid;grid-template-columns:repeat(2,1fr);gap:5px;overflow:auto;min-height:0}
  .node{padding:5px 7px;border-radius:6px;border:1px solid var(--line);background:#070b13;font-size:11px;display:flex;justify-content:space-between;align-items:center}
  .up{border-color:#10b98166;color:var(--emerald)}
  .dn{border-color:#f43f5e55;color:var(--rose)}
  .center{position:relative;background:#050810;border:1px solid var(--line);border-radius:8px;min-height:0;overflow:hidden;display:flex;flex-direction:column}
  canvas#gyro{width:100%;height:100%;display:block;flex:1;min-height:0}
  .overlay-stat{position:absolute;top:8px;left:10px;font-size:10px;color:var(--cyan);pointer-events:none}
  .overlay-right{position:absolute;top:8px;right:10px;font-size:10px;color:var(--amber);text-align:right;pointer-events:none}
  .console-out{flex:1;min-height:0;overflow:auto;background:#060911;border:1px solid var(--line);border-radius:6px;padding:6px;font-size:11px;margin-bottom:6px}
  .line{margin-bottom:4px;word-break:break-word}
  .u-msg{color:var(--cyan)} .a-msg{color:var(--emerald)} .s-msg{color:var(--muted)}
  .bar{display:flex;gap:5px}
  input{flex:1;min-width:0;background:#060a12;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font:inherit;font-size:11px}
  button{background:var(--cyan);color:#031018;border:0;border-radius:6px;padding:6px 10px;font:inherit;font-size:11px;font-weight:700;cursor:pointer}
</style>
</head>
<body>
<div class="hud">
  <div class="topbar">
    <span class="brand">GIANT TACTICAL HUD V4 // :8112</span>
    <span id="topMeta">PROBES: 8088 - 8090 - 8160 | MODEL: god-qwen:latest</span>
  </div>
  <div class="main">
    <div class="col">
      <div class="title"><span>NODE PROBES</span><span id="upCnt">--</span></div>
      <div class="nodes" id="nodeGrid"></div>
      <div class="title" style="margin-top:8px"><span>STREAM / TELEMETRY</span><span id="pipeCnt">0</span></div>
      <div class="console-out" id="evFeed" style="flex:.8"></div>
    </div>

    <div class="center">
      <div class="overlay-stat" id="gyroReadout">GYRO-SPHERE // 3D RADIAL LOCK</div>
      <div class="overlay-right" id="ramReadout">RAM -- MiB</div>
      <canvas id="gyro"></canvas>
    </div>

    <div class="col">
      <div class="title"><span>GOD-QWEN:LATEST CONSOLE</span><span id="engTag">READY</span></div>
      <div class="console-out" id="chatOut">
        <div class="line s-msg">[V4] god-qwen:latest tactical link armed. Query nodes, sweeps, or directives.</div>
      </div>
      <div class="bar">
        <input id="cmdIn" placeholder="Command god-qwen:latest..." onkeydown="if(event.key==='Enter')sendCmd()"/>
        <button onclick="sendCmd()">RUN</button>
      </div>
    </div>
  </div>
</div>
<script>
const cv = document.getElementById("gyro"), ctx = cv.getContext("2d");
let t = 0, pulse = 0, activeUp = 0, totalNodes = 8;

function resizeCanvas(){
  const r = cv.getBoundingClientRect();
  cv.width = Math.max(200, Math.floor(r.width * (window.devicePixelRatio || 1)));
  cv.height = Math.max(160, Math.floor(r.height * (window.devicePixelRatio || 1)));
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

function project3D(x, y, z, rx, ry, fov, cx, cy){
  const cy1 = Math.cos(ry), sy1 = Math.sin(ry);
  const x1 = x * cy1 + z * sy1;
  const z1 = -x * sy1 + z * cy1;
  const cx1 = Math.cos(rx), sx1 = Math.sin(rx);
  const y2 = y * cx1 - z1 * sx1;
  const z2 = y * sx1 + z1 * cx1;
  const sc = fov / Math.max(120, fov + z2);
  return { x: cx + x1 * sc, y: cy + y2 * sc, sc, z: z2 };
}

function drawGyro(){
  t += 0.018;
  pulse = Math.max(0, pulse - 0.03);
  const w = cv.width, h = cv.height, cx = w / 2, cy = h / 2;
  const rad = Math.min(w, h) * (0.28 + pulse * 0.05);
  ctx.fillStyle = "#050810";
  ctx.fillRect(0, 0, w, h);

  const rings = [
    { rx: t * 0.7, ry: t * 0.4, col: "#22d3ee" },
    { rx: -t * 0.5, ry: t * 0.9, col: "#34d399" },
    { rx: t * 0.3, ry: -t * 0.6, col: "#fbbf24" },
  ];
  rings.forEach((rg, idx) => {
    ctx.strokeStyle = rg.col + "aa";
    ctx.lineWidth = 1.6 + (idx === 0 ? pulse * 2 : 0);
    ctx.beginPath();
    const steps = 48;
    for(let i = 0; i <= steps; i++){
      const a = (i / steps) * Math.PI * 2;
      const p = project3D(Math.cos(a) * rad, Math.sin(a) * rad, 0, rg.rx, rg.ry + idx, rad * 2.2, cx, cy);
      if(i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
    }
    ctx.stroke();
  });

  ctx.strokeStyle = "#22d3ee33";
  ctx.lineWidth = 1;
  for(let k = 0; k < 8; k++){
    const phi = (k / 8) * Math.PI * 2 + t * 0.25;
    ctx.beginPath();
    for(let j = 0; j <= 24; j++){
      const th = (j / 24) * Math.PI - Math.PI / 2;
      const x = Math.cos(th) * Math.cos(phi) * rad * 0.85;
      const y = Math.sin(th) * rad * 0.85;
      const z = Math.cos(th) * Math.sin(phi) * rad * 0.85;
      const p = project3D(x, y, z, 0.35, t * 0.5, rad * 2.2, cx, cy);
      if(j === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
    }
    ctx.stroke();
  }

  ctx.fillStyle = "#e6f1ff";
  ctx.font = "bold 12px monospace";
  ctx.textAlign = "center";
  ctx.fillText("NODES " + activeUp + "/" + totalNodes + " - GYRO-3D", cx, cy + 4);
  requestAnimationFrame(drawGyro);
}
drawGyro();

async function pollHUD(){
  try {
    const r = await fetch("/api/hud/status");
    const d = await r.json();
    const probes = d.probes || [];
    totalNodes = probes.length || 8;
    activeUp = probes.filter(x => x.up).length;
    document.getElementById("upCnt").textContent = activeUp + "/" + totalNodes + " UP";
    document.getElementById("nodeGrid").innerHTML = probes.map(p =>
      '<div class="node ' + (p.up ? "up" : "dn") + '"><span>:' + p.port + '</span><span>' + (p.up ? p.code : "OFF") + '</span></div>'
    ).join("");
    document.getElementById("pipeCnt").textContent = "OTel:" + (d.otel.metrics_batches + d.otel.logs_batches) + " FB:" + d.fluentbit_records;
    document.getElementById("ramReadout").textContent = "RAM " + Number(d.free_ram_mib || 0).toFixed(1) + " MiB";
    document.getElementById("gyroReadout").textContent = "GYRO-SPHERE // 8088-8090-8160 PROBED";
    document.getElementById("evFeed").innerHTML = (d.events || []).slice(-10).map(e =>
      '<div class="line s-msg">[' + e.ts + '] ' + e.platform + ':' + e.kind + ' ' + JSON.stringify(e.payload).slice(0,48) + '</div>'
    ).join("");
  } catch(_){}
}

async function sendCmd(){
  const inp = document.getElementById("cmdIn");
  const prompt = inp.value.trim();
  if(!prompt) return;
  inp.value = "";
  pulse = 1.0;
  const out = document.getElementById("chatOut");
  out.innerHTML += '<div class="line u-msg">&gt; ' + prompt.replace(/</g,"&lt;") + '</div>';
  const r = await fetch("/api/god-qwen/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt })
  });
  const d = await r.json();
  document.getElementById("engTag").textContent = d.engine || "GOD-QWEN";
  out.innerHTML += '<div class="line a-msg">' + String(d.reply || "").replace(/</g,"&lt;") + '</div>';
  out.scrollTop = out.scrollHeight;
  pollHUD();
}

pollHUD();
setInterval(pollHUD, 3000);
</script>
</body>
</html>
`;

const server = http.createServer(async (req, res) => {
  const url = (req.url || "/").split("?")[0];

  if (req.method === "GET" && (url === "/" || url === "/hud" || url === "/v4" || url === "/giant")) {
    const body = Buffer.from(HUD_V4_HTML, "utf8");
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Content-Length": body.length });
    return res.end(body);
  }

  if (req.method === "GET" && url === "/api/hud/status") {
    const probes = await refreshProbes();
    let freeRam = 0;
    try {
      const m = fs.readFileSync("/proc/meminfo", "utf8").match(/MemAvailable:\s+(\d+)/);
      if (m) freeRam = Number(m[1]) / 1024;
    } catch (_) {}
    return jsonOut(res, 200, {
      ok: true,
      hud_version: "V4",
      model: GOD_QWEN_MODEL,
      free_ram_mib: Number(freeRam.toFixed(1)),
      probes,
      events: state.stream_events.slice(-20),
      otel: { metrics_batches: state.otel_metrics_batches, logs_batches: state.otel_logs_batches },
      fluentbit_records: state.fluentbit_records,
      prom_scrapes: state.prom_scrapes,
    });
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
    return jsonOut(res, 200, { ok: true, model: GOD_QWEN_MODEL, ...ans });
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
      "# HELP astra_bridge_up Giant Tactical HUD V4 bridge status",
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
  console.log(`[v] Giant Tactical HUD V4 active on 127.0.0.1:${PORT}`);
});
