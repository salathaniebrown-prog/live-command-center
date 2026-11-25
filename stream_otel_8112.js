const http = require("http");
const crypto = require("crypto");

const PORT = Number(process.env.STREAM_OTEL_PORT || 8112);
const WATCH_PORTS = [8088, 8090, 8095, 8099, 8110, 8125, 8170];

const state = {
  started_at: Date.now(),
  stream_events: [],
  ws_clients: new Set(),
  otel_metrics_batches: 0,
  otel_logs_batches: 0,
  fluentbit_records: 0,
  prom_scrapes: 0,
  last_probe: [],
};

function pushEvent(platform, kind, payload) {
  const item = {
    id: state.stream_events.length + 1,
    ts: new Date().toISOString(),
    platform: String(platform || "kick").toLowerCase(),
    kind: String(kind || "chat"),
    payload,
  };
  state.stream_events.push(item);
  if (state.stream_events.length > 200) state.stream_events.shift();

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
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port: p, path: "/", timeout: 700 }, (res) => {
      res.resume();
      resolve({ port: p, up: true, status: res.statusCode || 200 });
    });
    req.on("timeout", () => { req.destroy(); resolve({ port: p, up: false, status: 0 }); });
    req.on("error", () => resolve({ port: p, up: false, status: 0 }));
  });
}

async function refreshProbes() {
  state.last_probe = await Promise.all(WATCH_PORTS.map(probePort));
  return state.last_probe;
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

const server = http.createServer(async (req, res) => {
  const url = (req.url || "/").split("?")[0];

  if (req.method === "GET" && url === "/") {
    const probes = await refreshProbes();
    return jsonOut(res, 200, {
      ok: true,
      service: "DUAL_STREAM_OTEL_BRIDGE_8112",
      port: PORT,
      ws_clients: state.ws_clients.size,
      stream_events_buffered: state.stream_events.length,
      otel: { metrics_batches: state.otel_metrics_batches, logs_batches: state.otel_logs_batches },
      fluentbit_records: state.fluentbit_records,
      prom_scrapes: state.prom_scrapes,
      watched_ports: probes,
    });
  }

  if (req.method === "GET" && url === "/api/stream/events") {
    return jsonOut(res, 200, { ok: true, events: state.stream_events.slice(-50) });
  }

  if (req.method === "POST" && url === "/api/stream/event") {
    const raw = await readBody(req);
    let parsed = {};
    try { parsed = JSON.parse(raw || "{}"); } catch (_) { parsed = { text: raw }; }
    const item = pushEvent(
      parsed.platform || "kick",
      parsed.kind || "chat",
      parsed.payload || parsed
    );
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
      "# HELP astra_bridge_up Dual-stream and OTel bridge health",
      "# TYPE astra_bridge_up gauge",
      "astra_bridge_up 1",
      "# HELP astra_bridge_rss_mb Process RSS memory in MiB",
      "# TYPE astra_bridge_rss_mb gauge",
      `astra_bridge_rss_mb ${rssMb}`,
      "# HELP astra_bridge_uptime_seconds Bridge uptime in seconds",
      "# TYPE astra_bridge_uptime_seconds counter",
      `astra_bridge_uptime_seconds ${upSec}`,
      "# HELP astra_otel_batches_total Received OTel batches",
      "# TYPE astra_otel_batches_total counter",
      `astra_otel_batches_total{signal="metrics"} ${state.otel_metrics_batches}`,
      `astra_otel_batches_total{signal="logs"} ${state.otel_logs_batches}`,
      "# HELP astra_fluentbit_records_total Fluent Bit records ingested",
      "# TYPE astra_fluentbit_records_total counter",
      `astra_fluentbit_records_total ${state.fluentbit_records}`,
      "# HELP astra_watched_port_up Monitored local port status",
      "# TYPE astra_watched_port_up gauge",
      ...probes.map((x) => `astra_watched_port_up{port="${x.port}"} ${x.up ? 1 : 0}`),
    ];
    const out = lines.join("\n") + "\n";
    res.writeHead(200, { "Content-Type": "text/plain; version=0.0.4; charset=utf-8" });
    return res.end(out);
  }

  jsonOut(res, 404, { ok: false, error: "not_found", path: url });
});

server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) { socket.destroy(); return; }
  const accept = crypto
    .createHash("sha1")
    .update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
    .digest("base64");
  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\n" +
    "Upgrade: websocket\r\n" +
    "Connection: Upgrade\r\n" +
    `Sec-WebSocket-Accept: ${accept}\r\n\r\n`
  );
  state.ws_clients.add(socket);
  socket.on("close", () => state.ws_clients.delete(socket));
  socket.on("error", () => state.ws_clients.delete(socket));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[v] Dual-Stream + OTel/FluentBit/Prometheus Bridge active on 127.0.0.1:${PORT}`);
});
