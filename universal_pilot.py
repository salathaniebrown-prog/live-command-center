#!/usr/bin/env python3
"""
Salathanie A.I — Universal Pilot + Trinity Control Plane + VR Data Circle
Serves on 0.0.0.0:8125 (proxied by salathanie-tunnel) with RAM Safe-Mode Guard.
"""
import glob
import json
import cisco_mdt_tunnel_gis_otel as cisco_gis
import astra_alstra_flying_car as fcar
import self_ram_telemetry as ram_tel
import ram_watchdog_telemetry as rwatch
import os
import re
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv
import infra_sre_engine as infra
import salathanie_v3_suite as v3
import creative_production_studio as creative
import astra_jet_engine as jet
import astra_jet_hud as jet3d
import salathanie_mesh_studio as mesh
import astra_memory_spine as memspine
import salathanie_v1_shim as v1shim
import astra_unified_deck as deck
import astra_flight_ledger as fledger
import astra_alstra_jet_bridge as jbridge

PREFERRED_PORT = 8125
ACTIVE_PORT = PREFERRED_PORT
TRINITY_BASE = "http://127.0.0.1:8126"


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def get_mem_avail_mb() -> int:
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


def get_live_tunnel_url() -> str:
    pattern = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")
    url = ""
    for path in sorted(glob.glob(os.path.expanduser("~/.pm2/logs/salathanie-tunnel-*.log"))):
        try:
            with open(path, "r", errors="ignore") as f:
                matches = pattern.findall(f.read())
                if matches:
                    url = matches[-1]
        except OSError:
            pass
    return url


def probe_http(url: str, timeout: float = 4.0) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Salathanie-Universal-Pilot/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return {"ok": True, "url": url, "status": resp.status, "latency_ms": ms}
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return {"ok": False, "url": url, "status": 0, "latency_ms": ms, "error": str(e)[:120]}


def get_agents_base() -> str:
    try:
        reg = json.loads(open("/data/data/com.termux/files/usr/tmp/salathanie_ports.json").read())
        if "salathanie-agents" in reg:
            return f"http://127.0.0.1:{reg['salathanie-agents']['port']}"
    except Exception:
        pass
    return "http://127.0.0.1:8128"


def proxy_json(url: str, timeout: float = 12.0) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return 502, {"ok": False, "error": str(e)[:160]}


def collect_telemetry() -> dict:
    mem_mb = get_mem_avail_mb()
    safe_mode = 0 < mem_mb < 400
    broadband = probe_http("https://1.1.1.1/cdn-cgi/trace", timeout=3.0)
    wal = probe_http("http://127.0.0.1:8182/health", timeout=2.0)
    trinity = probe_http(f"{TRINITY_BASE}/health", timeout=2.0)
    ingress_8088 = probe_http("http://127.0.0.1:8088/", timeout=1.5)
    gateway_8090 = probe_http("http://127.0.0.1:8090/", timeout=1.5)
    spatial_8151 = probe_http("http://127.0.0.1:8151/", timeout=1.5)
    tunnel_url = get_live_tunnel_url()

    ring_info = {"attested": False, "seq": 0, "node": "none"}
    try:
        with HDCSharedMemoryBus() as bus:
            with bus.read_latest_view() as rec:
                if rec:
                    ring_info = {"attested": bool(rec.get("hmac_ok")), "seq": rec["seq"], "node": rec["node"]}
    except Exception:
        pass

    return {
        "ts": int(time.time()),
        "lan_ip": get_lan_ip(),
        "pilot_port": ACTIVE_PORT,
        "tunnel_url": tunnel_url,
        "mem_avail_mb": mem_mb,
        "safe_mode": safe_mode,
        "broadband": broadband,
        "local_wal": wal,
        "trinity": trinity,
        "ingress_8088": ingress_8088,
        "gateway_8090": gateway_8090,
        "spatial_8151": spatial_8151,
        "hdc_ring": ring_info,
    }


UI_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — Universal Pilot & Trinity</title>
<style>
body{font-family:monospace;background:#0b0f14;color:#e6edf3;margin:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
.ok{color:#3fb950}.bad{color:#f85149}.warn{color:#d29922}.cy{color:#58a6ff}
input,button{background:#0d1117;color:#e6edf3;border:1px solid #30363d;padding:7px 10px;border-radius:6px;font-family:monospace}
button{background:#238636;border:none;cursor:pointer;margin:3px 2px}
button.alt{background:#1f6feb}button.purp{background:#8957e5}
pre{white-space:pre-wrap;word-break:break-all;font-size:12px;max-height:240px;overflow:auto;background:#0d1117;padding:8px;border-radius:6px}
a{color:#58a6ff}
</style></head><body>
<h2>Salathanie A.I — Universal Pilot & Trinity</h2>

<div class="card">
  <button onclick="refreshAll()">Refresh All</button>
  <button class="alt" onclick="dispatch('edge recover')">Self-Heal Stack</button>
  <a href="/agents"><button class="purp">18-Agent Studio</button></a>
  <a href="/trader"><button style="background:#d29922;color:#0b0f14">Web Trader / OMS</button></a>
  <a href="/infra"><button style="background:#0ea5e9;color:#0b0f14">Infra / SRE</button></a>
  <a href="/dealership"><button style="background:#238636">Dealership</button></a>
  <a href="/eagle-eyes"><button style="background:#0891b2">Eagle Eyes</button></a>
  <a href="/codes"><button style="background:#db2777">50 Codes</button></a>
  <a href="/artifacts"><button style="background:#4f46e5">Artifacts</button></a>
  <a href="/creative"><button style="background:#f97316;color:#080c14">Creative Studio</button></a>
  <a href="/astra-jet"><button style="background:#38bdf8;color:#060a12">Astra Jet AI</button></a>
  <a href="/jet-3d"><button style="background:#39ff14;color:#030812">3D Jet HUD</button></a>
  <a href="/mesh-hub"><button style="background:#10b981;color:#050912">Mesh &amp; Offline Wiki</button></a>
  <a href="/broadcast"><button style="background:#ec4899">iPad Broadcast Studio</button></a>
  <a href="/scrintal"><button style="background:#a855f7">AI Scrintal</button></a>
  <a href="/memory"><button style="background:#06b6d4;color:#050912">Memory Spine</button></a>
  <a href="/deck"><button style="background:#c084fc;color:#050912">SalathanieAI Deck</button></a>
  <div id="summary" style="margin-top:10px;line-height:1.6">Loading...</div>
</div>

<div class="card">
  <b>Trinity Control Plane (Heart / Brain / Driver)</b><br><br>
  <button class="alt" onclick="dispatch('github status')">GitHub Status</button>
  <button class="alt" onclick="dispatch('github log')">Git Log</button>
  <button class="purp" onclick="dispatch('linux free')">Linux RAM</button>
  <button class="purp" onclick="dispatch('linux uptime')">Uptime</button>
  <button onclick="dispatch('vr frame')">VR Circle</button><br><br>
  <input id="cmd" value="github status" style="width:66%">
  <button onclick="dispatch(document.getElementById('cmd').value)">Execute</button>
  <pre id="trinityOut">Ready.</pre>
</div>

<div class="card">
  <b>Live VR Data Circle (HMAC-Attested Ring)</b><br>
  <svg id="vrSvg" width="280" height="220" viewBox="0 0 280 220" style="display:block;margin:8px auto;background:#0d1117;border-radius:8px;border:1px solid #30363d"></svg>
</div>

<div class="card">
  <b>Broadband / HTTP Probe</b><br><br>
  <input id="url" value="https://1.1.1.1" style="width:66%">
  <button onclick="runProbe()">Probe</button>
  <pre id="probeOut">Ready.</pre>
</div>

<script>
async function loadStatus(){
  const r = await fetch('/api/pilot/status'); const d = await r.json();
  const bb = d.broadband.ok ? '<span class="ok">ONLINE ('+d.broadband.latency_ms+'ms)</span>' : '<span class="bad">OFFLINE</span>';
  const tun = d.tunnel_url ? '<a href="'+d.tunnel_url+'" target="_blank">'+d.tunnel_url+'</a> <span class="ok">(ONLINE)</span>' : '<span class="warn">STARTING...</span>';
  const sm = d.safe_mode ? '<span class="warn">SAFE MODE</span>' : '<span class="ok">NOMINAL</span>';
  document.getElementById('summary').innerHTML =
    'LAN: <b>'+d.lan_ip+':'+d.pilot_port+'</b> | Free RAM: <b>'+d.mem_avail_mb+' MB</b> ('+sm+')<br>'+
    'Tunnel: '+tun+'<br>'+
    'Broadband: '+bb+' | WAL 8182: '+(d.local_wal.ok?'<span class="ok">UP</span>':'<span class="bad">DOWN</span>')+
    ' | Trinity 8126: '+(d.trinity.ok?'<span class="ok">UP</span>':'<span class="bad">DOWN</span>')+
    ' | HDC HMAC: '+(d.hdc_ring.attested?'<span class="ok">VERIFIED</span>':'<span class="warn">WAIT</span>')+'<br>'+'Mesh Nodes -> 8088: '+(d.ingress_8088&&d.ingress_8088.ok?'<span class="ok">UP</span>':'<span class="warn">IDLE</span>')+' | 8090: '+(d.gateway_8090&&d.gateway_8090.ok?'<span class="ok">UP</span>':'<span class="warn">IDLE</span>')+' | 8151: '+(d.spatial_8151&&d.spatial_8151.ok?'<span class="ok">UP</span>':'<span class="warn">IDLE</span>');
}
async function loadVR(){
  const r = await fetch('/api/pilot/trinity/vr-frame'); const d = await r.json();
  const svg = document.getElementById('vrSvg');
  let html = '<circle cx="140" cy="110" r="75" fill="none" stroke="#30363d" stroke-dasharray="4 4"/>';
  html += '<circle cx="140" cy="110" r="18" fill="#1f6feb" opacity="0.3"/><text x="140" y="114" fill="#e6edf3" font-size="10" text-anchor="middle">HEART</text>';
  const nodes = d.vr_circle_nodes || [];
  nodes.forEach(n => {
    const rad = (n.angle_deg * Math.PI) / 180;
    const x = 140 + Math.cos(rad) * 75 * (n.radius || 1);
    const y = 110 + Math.sin(rad) * 75 * (n.radius || 1);
    html += `<line x1="140" y1="110" x2="${x}" y2="${y}" stroke="#238636" stroke-width="1.5"/>`;
    html += `<circle cx="${x}" cy="${y}" r="8" fill="#3fb950"/>`;
    html += `<text x="${x}" y="${y-12}" fill="#e6edf3" font-size="9" text-anchor="middle">${n.node}:${n.port}</text>`;
  });
  svg.innerHTML = html;
}
async function dispatch(cmd){
  document.getElementById('cmd').value = cmd;
  document.getElementById('trinityOut').textContent = 'Running: '+cmd+'...';
  const r = await fetch('/api/pilot/trinity/dispatch?cmd='+encodeURIComponent(cmd));
  document.getElementById('trinityOut').textContent = JSON.stringify(await r.json(), null, 2);
  loadVR();
}
async function runProbe(){
  const u = encodeURIComponent(document.getElementById('url').value);
  const r = await fetch('/api/pilot/probe?url='+u);
  document.getElementById('probeOut').textContent = JSON.stringify(await r.json(), null, 2);
}
function refreshAll(){ loadStatus(); loadVR(); }
refreshAll(); setInterval(refreshAll, 10000);
</script></body></html>"""


class PilotHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/ui"):
            return self._send(200, UI_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/pilot/nasa-jet":
            return self._send(200, json.dumps(sync_nasa_to_jet()).encode("utf-8"))
        if parsed.path == "/api/pilot/status":
            return self._send(200, json.dumps(collect_telemetry()).encode("utf-8"))
        if parsed.path == "/api/pilot/probe":
            qs = urllib.parse.parse_qs(parsed.query)
            target = qs.get("url", ["https://1.1.1.1"])[0]
            return self._send(200, json.dumps(probe_http(target)).encode("utf-8"))
        if parsed.path == "/api/pilot/trinity/vr-frame":
            code, data = proxy_json(f"{TRINITY_BASE}/api/trinity/vr-frame")
            return self._send(code, json.dumps(data).encode("utf-8"))
        if parsed.path == "/agents":
            try:
                with urllib.request.urlopen(f"{get_agents_base()}/", timeout=6) as resp:
                    return self._send(resp.status, resp.read(), "text/html; charset=utf-8")
            except Exception as e:
                return self._send(502, f"Agents offline: {e}".encode("utf-8"), "text/plain")
        if parsed.path == "/deck":
            return self._send(200, deck.DECK_HTML, "text/html; charset=utf-8")
        if parsed.path == "/api/ledger":
            return self._send(200, json.dumps(fledger.get_ledger_snapshot(20)).encode("utf-8"))
        if parsed.path == "/proxy/jet":
            return self._send(200, jet3d.PAGE, "text/html; charset=utf-8")
        if parsed.path == "/proxy/8090":
            c, ct, data = deck._proxy(["http://127.0.0.1:8090/"])
            return self._send(c, ct, data)
        if parsed.path == "/v1/models":
            return self._send(200, json.dumps(v1shim.handle_v1_models()).encode("utf-8"))
        if parsed.path == "/api/salathanie-ai/neural":
            return self._send(200, json.dumps(v1shim.get_neural_state()).encode("utf-8"))
        if parsed.path == "/api/cisco-mdt/collect":
            return self._send(200, json.dumps(cisco_gis.collect_cisco_mdt()).encode("utf-8"))
        if parsed.path == "/tunnel-gis":
            return self._send(200, cisco_gis.TUNNEL_GIS_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/ram/watchdog":
            return self._send(200, json.dumps(rwatch.watchdog_status(15)).encode("utf-8"))
        if parsed.path == "/api/ram/telemetry":
            return self._send(200, json.dumps(ram_tel.sample_and_guard(auto_trim=True)).encode("utf-8"))
        if parsed.path == "/flying-car":
            return self._send(200, fcar.FLYING_CAR_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/flying-car/status":
            return self._send(200, json.dumps(fcar.flying_car_status()).encode("utf-8"))
        if parsed.path == "/memory":
            return self._send(200, memspine.MEMORY_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/memory/status":
            return self._send(200, json.dumps(memspine.spine_status()).encode("utf-8"))
        if parsed.path == "/mesh-hub":
            return self._send(200, mesh.MESH_HUB_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/broadcast":
            return self._send(200, mesh.BROADCAST_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/scrintal":
            return self._send(200, mesh.SCRINTAL_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/mesh/diag":
            return self._send(200, json.dumps(mesh.mesh_diagnostics()).encode("utf-8"))
        if parsed.path == "/api/mesh/wiki/search":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(mesh.wiki_search(qs.get("q", [""])[0])).encode("utf-8"))
        if parsed.path == "/api/mesh/lessons":
            return self._send(200, json.dumps(mesh.list_lessons()).encode("utf-8"))
        if parsed.path == "/api/scrintal/state":
            return self._send(200, json.dumps(mesh.scrintal_state()).encode("utf-8"))
        if parsed.path == "/jet-3d":
            return self._send(200, jet3d.PAGE, "text/html; charset=utf-8")
        if parsed.path == "/api/hud":
            return self._send(200, json.dumps(jet3d.read_hud_payload()).encode("utf-8"))
        if parsed.path == "/astra-jet":
            return self._send(200, jet.JET_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/jet/telemetry":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(jet.step_telemetry(qs.get("fault", ["none"])[0])).encode("utf-8"))
        if parsed.path == "/api/jet/lineage":
            return self._send(200, json.dumps(jet.get_lineage()).encode("utf-8"))
        if parsed.path == "/creative":
            return self._send(200, creative.CREATIVE_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/creative/catalog":
            return self._send(200, json.dumps(creative.list_workflows()).encode("utf-8"))
        if parsed.path == "/dealership":
            return self._send(200, v3.DEALERSHIP_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/eagle-eyes":
            return self._send(200, v3.EAGLE_EYES_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/codes":
            return self._send(200, v3.CODES_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/artifacts":
            return self._send(200, v3.ARTIFACTS_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/v3/dealership/state":
            return self._send(200, json.dumps(v3.dealership_state()).encode("utf-8"))
        if parsed.path == "/api/v3/receipt":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, v3.dealership_receipt_html(qs.get("id", [""])[0]).encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/v3/eagle-eyes":
            return self._send(200, json.dumps(v3.eagle_eyes_telemetry()).encode("utf-8"))
        if parsed.path == "/api/v3/codes/list":
            return self._send(200, json.dumps({"count": len(v3.SECRET_CODES), "codes": v3.SECRET_CODES}).encode("utf-8"))
        if parsed.path == "/api/v3/artifacts/sync":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(v3.sync_artifact_memory(qs.get("audit", ["0"])[0] == "1")).encode("utf-8"))
        if parsed.path == "/api/v3/artifacts/search":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(v3.search_artifacts(qs.get("q", [""])[0])).encode("utf-8"))
        if parsed.path == "/infra":
            return self._send(200, infra.INFRA_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/metrics":
            bb = probe_http("https://1.1.1.1/cdn-cgi/trace", timeout=2.0)
            body = infra.prometheus_metrics(get_mem_avail_mb(), bb.get("latency_ms", 0.0))
            return self._send(200, body.encode("utf-8"), "text/plain; version=0.0.4; charset=utf-8")
        if parsed.path == "/api/infra/osi":
            return self._send(200, json.dumps(infra.osi_tcpip_diagnostics()).encode("utf-8"))
        if parsed.path == "/api/infra/errors":
            return self._send(200, json.dumps(infra.self_analyze_errors()).encode("utf-8"))
        if parsed.path == "/api/infra/blueprint":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(infra.generate_blueprint(qs.get("stack", ["observability_stack"])[0])).encode("utf-8"))
        if parsed.path == "/api/infra/copilot":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(infra.linux_ai_copilot(qs.get("q", ["status"])[0])).encode("utf-8"))
        if parsed.path == "/api/infra/validate":
            qs = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(infra.validate_code_zero_error(qs.get("lang", ["bash"])[0], qs.get("code", [""])[0])).encode("utf-8"))
        if parsed.path == "/api/infra/learning":
            return self._send(200, json.dumps(infra.LEARNING_HUB).encode("utf-8"))
        if parsed.path == "/trader":
            try:
                with urllib.request.urlopen(f"{get_agents_base()}/trader", timeout=6) as resp:
                    return self._send(resp.status, resp.read(), "text/html; charset=utf-8")
            except Exception as e:
                return self._send(502, f"Trader offline: {e}".encode("utf-8"), "text/plain")
        if parsed.path.startswith("/api/oms/"):
            q = f"?{parsed.query}" if parsed.query else ""
            code, data = proxy_json(f"{get_agents_base()}{parsed.path}{q}", timeout=10)
            return self._send(code, json.dumps(data).encode("utf-8"))
        if parsed.path == "/api/agents/run":
            code, data = proxy_json(f"{get_agents_base()}/api/agents/run?{parsed.query}", timeout=15)
            return self._send(code, json.dumps(data).encode("utf-8"))
        if parsed.path == "/api/pilot/trinity/dispatch":
            code, data = proxy_json(f"{TRINITY_BASE}/api/trinity/dispatch?{parsed.query}")
            return self._send(code, json.dumps(data).encode("utf-8"))
        return self._send(404, json.dumps({"error": "not_found"}).encode("utf-8"))


    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(min(length, 65536)).decode("utf-8", errors="ignore") if length else "{}"
        try:
            body = json.loads(raw) if raw.strip() else {}
        except Exception:
            body = {}
        if self.path == "/api/salathanie-ai/infer":
            return self._send(200, json.dumps(deck.salathanie_ai_infer(body)).encode("utf-8"))
        if self.path == "/api/px4":
            return self._send(200, json.dumps({"ok": True, "px4": fledger.record_px4(body, "px4_pilot_8125")}).encode("utf-8"))
        if self.path == "/api/external/sync":
            return self._send(200, json.dumps(fledger.sync_external_feeds()).encode("utf-8"))
        if self.path == "/api/wal/checkpoint":
            return self._send(200, json.dumps(fledger.wal_checkpoint()).encode("utf-8"))
        if self.path == "/api/bridge/cycle":
            return self._send(200, json.dumps(jbridge.run_closed_loop_cycle(bool(body.get("sync_ext")))).encode("utf-8"))
        if self.path == "/v1/chat/completions":
            return self._send(200, json.dumps(v1shim.handle_v1_chat_completions(body, deck.salathanie_ai_infer)).encode("utf-8"))
        if self.path == "/api/pilot/nasa-jet":
            return self._send(200, json.dumps(sync_nasa_to_jet()).encode("utf-8"))
        if self.path == "/api/flying-car/step":
            return self._send(200, json.dumps(fcar.step_flying_car(body if isinstance(body, dict) else {})).encode("utf-8"))
        if self.path == "/api/memory/snapshot":
            return self._send(200, json.dumps(memspine.take_snapshot(body.get("reason", "api"))).encode("utf-8"))
        if self.path == "/api/memory/restore":
            return self._send(200, json.dumps(memspine.restore_session(revive_pm2=not bool(body.get("dry_run")), dry_run=bool(body.get("dry_run")))).encode("utf-8"))
        if self.path == "/api/memory/rollback":
            return self._send(200, json.dumps(memspine.rollback_code_file(body.get("file", ""), body.get("version_id"))).encode("utf-8"))
        if self.path == "/api/mesh/wiki/import":
            return self._send(200, json.dumps(mesh.wiki_import_online(body.get("topic", ""), body.get("category", "Wikipedia"))).encode("utf-8"))
        if self.path == "/api/mesh/wiki/add":
            return self._send(200, json.dumps(mesh.wiki_add_manual(body.get("title", ""), body.get("category", "FieldNote"), body.get("body", ""))).encode("utf-8"))
        if self.path == "/api/mesh/pi5-script":
            return self._send(200, json.dumps(mesh.generate_pi5_mesh_script(body.get("ssid", "Salathanie-Mesh-Edu"), body.get("mesh_id", "salathanie-mesh"), body.get("channel", 6))).encode("utf-8"))
        if self.path == "/api/mesh/reconnect-script":
            return self._send(200, json.dumps(mesh.generate_termux_reconnect_script()).encode("utf-8"))
        if self.path == "/api/mesh/lesson/create":
            return self._send(200, json.dumps(mesh.create_lesson(body.get("topic", ""), body.get("level", "Beginner"))).encode("utf-8"))
        if self.path == "/api/broadcast/profile":
            return self._send(200, json.dumps(mesh.save_broadcast_profile(body.get("title", ""), body.get("ticker", ""), body.get("rtmp_url", ""))).encode("utf-8"))
        if self.path == "/api/scrintal/card":
            return self._send(200, json.dumps(mesh.scrintal_upsert_card(body.get("card_id", ""), body.get("title", ""), body.get("body", ""), body.get("tag", "Note"), body.get("x", 80), body.get("y", 80), body.get("color", "#38bdf8"))).encode("utf-8"))
        if self.path == "/api/scrintal/move":
            return self._send(200, json.dumps(mesh.scrintal_move_card(body.get("card_id", ""), body.get("x", 80), body.get("y", 80))).encode("utf-8"))
        if self.path == "/api/scrintal/delete":
            return self._send(200, json.dumps(mesh.scrintal_delete_card(body.get("card_id", ""))).encode("utf-8"))
        if self.path == "/api/scrintal/link":
            return self._send(200, json.dumps(mesh.scrintal_link_cards(body.get("src", ""), body.get("dst", ""), body.get("label", "links"))).encode("utf-8"))
        if self.path == "/api/scrintal/ai-expand":
            return self._send(200, json.dumps(mesh.scrintal_ai_expand(body.get("card_id", ""))).encode("utf-8"))
        if self.path in ("/api/mode", "/api/pods", "/api/pilot"):
            return self._send(200, json.dumps(jet3d.update_hud_state(self.path, body)).encode("utf-8"))
        if self.path == "/api/jet/mutate":
            res = jet.supercompute_mutate(int(body.get("cycles", 3)), body.get("fault", "turbulence"))
            return self._send(200, json.dumps(res).encode("utf-8"))
        if self.path == "/api/jet/rollback":
            res = jet.rollback_generation(body.get("gen_id", "GEN-000"))
            return self._send(200, json.dumps(res).encode("utf-8"))
        if self.path == "/api/creative/build":
            res = creative.aviator_build_workflow(body.get("brief", ""), body.get("style", "Cinematic 8K"), body.get("duration_s", 5), body.get("models"))
            return self._send(200, json.dumps(res).encode("utf-8"))
        if self.path == "/api/creative/execute":
            res = creative.execute_workflow(body.get("wf_id", ""), bool(body.get("live", False)), body.get("start_image_url", ""))
            return self._send(200, json.dumps(res).encode("utf-8"))
        if self.path == "/api/v3/dealership/acquire":
            res = v3.dealership_acquire(body.get("vehicle_id", ""), body.get("card_alias", "SALATHANIE_VCARD"), body.get("card_last4", "8842"), body.get("mopar_tier", "MAX_CARE"))
            return self._send(200, json.dumps(res).encode("utf-8"))
        if self.path == "/api/v3/dealership/advance":
            res = v3.dealership_advance(body.get("order_id", ""), body.get("stage", ""))
            return self._send(200, json.dumps(res).encode("utf-8"))
        if self.path == "/api/v3/codes/run":
            res = v3.run_secret_code(body.get("code", "/action plan"), body.get("topic", ""))
            return self._send(200, json.dumps(res).encode("utf-8"))
        return self._send(404, json.dumps({"error": "not_found"}).encode("utf-8"))



def sync_nasa_to_jet() -> dict:
    """Pull NASA EONET/orbital telemetry and fuse it into flight ledger & jet state."""
    import json, time, urllib.request
    import astra_flight_ledger as _fl
    ts = int(time.time())
    events = []
    try:
        url = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "SalathanieAI-Pilot-NASA/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as r:
            raw = json.loads(r.read().decode("utf-8", errors="ignore"))
        for ev in (raw.get("events") or [])[:5]:
            geoms = ev.get("geometry") or []
            g0 = geoms[-1] if geoms else {}
            coords = g0.get("coordinates") if isinstance(g0.get("coordinates"), list) else [0.0, 0.0]
            lon = float(coords[0]) if len(coords) >= 2 and isinstance(coords[0], (int, float)) else 0.0
            lat = float(coords[1]) if len(coords) >= 2 and isinstance(coords[1], (int, float)) else 0.0
            title = f"NASA: {ev.get('title', 'Orbital/Earth Event')}"[:140]
            events.append({"id": str(ev.get("id", ts)), "title": title, "lat": lat, "lon": lon})
            with _fl.db_conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO external_feeds (ts,source,event_id,title,severity,lat,lon,raw_json) VALUES (?,?,?,?,?,?,?,?)",
                    (ts, "NASA_EONET", f"nasa-{ev.get('id', ts)}", title, "NASA_TELEM", lat, lon, json.dumps({"date": g0.get("date")})),
                )
    except Exception:
        pass
    hz = _fl.external_hazard_score()
    st = _fl.atomic_write_state({"nasa_jet_sync_ts": ts, "nasa_hazard_score": hz, "nasa_events_count": len(events)}, preserve_overrides=True)
    return {"ok": True, "ts": ts, "nasa_events": len(events), "hazard_score": hz, "jet_state_ts": st.get("updated_ts"), "sample": events[:2]}


if __name__ == "__main__":
    with HDCSharedMemoryBus() as bus:
        ACTIVE_PORT = bus.allocate_port(PREFERRED_PORT)
        bus.publish("salathanie-universal-pilot", ACTIVE_PORT, 200, deterministic_hv(f"pilot:{ACTIVE_PORT}:UP"))
    print(f"[OK] Universal Pilot + Trinity UI live on http://{get_lan_ip()}:{ACTIVE_PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", ACTIVE_PORT), PilotHandler).serve_forever()
