#!/usr/bin/env python3
"""
Salathanie A.I — Universal Pilot + Trinity Control Plane + VR Data Circle
Serves on 0.0.0.0:8125 (proxied by salathanie-tunnel) with RAM Safe-Mode Guard.
"""
import glob
import json
import os
import re
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv

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
    ' | HDC HMAC: '+(d.hdc_ring.attested?'<span class="ok">VERIFIED</span>':'<span class="warn">WAIT</span>');
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
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/ui"):
            return self._send(200, UI_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/api/pilot/status":
            return self._send(200, json.dumps(collect_telemetry()).encode("utf-8"))
        if parsed.path == "/api/pilot/probe":
            qs = urllib.parse.parse_qs(parsed.query)
            target = qs.get("url", ["https://1.1.1.1"])[0]
            return self._send(200, json.dumps(probe_http(target)).encode("utf-8"))
        if parsed.path == "/api/pilot/trinity/vr-frame":
            code, data = proxy_json(f"{TRINITY_BASE}/api/trinity/vr-frame")
            return self._send(code, json.dumps(data).encode("utf-8"))
        if parsed.path == "/api/pilot/trinity/dispatch":
            code, data = proxy_json(f"{TRINITY_BASE}/api/trinity/dispatch?{parsed.query}")
            return self._send(code, json.dumps(data).encode("utf-8"))
        return self._send(404, json.dumps({"error": "not_found"}).encode("utf-8"))


if __name__ == "__main__":
    with HDCSharedMemoryBus() as bus:
        ACTIVE_PORT = bus.allocate_port(PREFERRED_PORT)
        bus.publish("salathanie-universal-pilot", ACTIVE_PORT, 200, deterministic_hv(f"pilot:{ACTIVE_PORT}:UP"))
    print(f"[OK] Universal Pilot + Trinity UI live on http://{get_lan_ip()}:{ACTIVE_PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", ACTIVE_PORT), PilotHandler).serve_forever()
