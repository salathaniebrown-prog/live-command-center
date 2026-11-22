#!/usr/bin/env python3
"""
Salathanie A.I — Broadband Connector, Telemetry & Self-AI Universal Pilot
- Ultra-lean stdlib HTTP server + Live Web UI (Wi-Fi LAN 0.0.0.0)
- Real-time Broadband/DNS/HTTP/Tunnel telemetry & URL probe
- RAM Safe-Mode Guard (prevents Android kernel reboots)
"""
import json
import os
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv

PREFERRED_PORT = 8125
ACTIVE_PORT = PREFERRED_PORT


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


def probe_http(url: str, timeout: float = 4.0) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Salathanie-Universal-Pilot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return {"ok": True, "url": url, "status": resp.status, "latency_ms": ms}
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return {"ok": False, "url": url, "status": 0, "latency_ms": ms, "error": str(e)[:120]}


def probe_dns(host: str = "cloudflare.com") -> dict:
    t0 = time.perf_counter()
    try:
        ip = socket.gethostbyname(host)
        return {"ok": True, "host": host, "ip": ip, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except OSError as e:
        return {"ok": False, "host": host, "error": str(e)}


def collect_telemetry() -> dict:
    mem_mb = get_mem_avail_mb()
    safe_mode = mem_mb > 0 and mem_mb < 400
    dns = probe_dns("cloudflare.com")
    broadband = probe_http("https://1.1.1.1/cdn-cgi/trace", timeout=3.0)
    gw = probe_http("http://127.0.0.1:8090/", timeout=2.0)
    wal = probe_http("http://127.0.0.1:8182/health", timeout=2.0)

    ring_info = {"attested": False, "seq": 0}
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
        "mem_avail_mb": mem_mb,
        "safe_mode": safe_mode,
        "broadband": broadband,
        "dns": dns,
        "local_gateway": gw,
        "local_wal": wal,
        "hdc_ring": ring_info,
    }


UI_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — Universal Pilot</title>
<style>
body{font-family:monospace;background:#0b0f14;color:#e6edf3;margin:16px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
.ok{color:#3fb950}.bad{color:#f85149}.warn{color:#d29922}
input,button{background:#0d1117;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace}
button{background:#238636;border:none;cursor:pointer;margin-left:4px}
pre{white-space:pre-wrap;word-break:break-all;font-size:12px}
</style></head><body>
<h2>Salathanie A.I — Universal Pilot</h2>
<div class="card">
  <button onclick="loadStatus()">Refresh Telemetry</button>
  <button onclick="triggerHeal()" style="background:#1f6feb">Self-Heal Core</button>
  <div id="summary" style="margin-top:10px">Loading...</div>
</div>
<div class="card">
  <b>Universal HTTP / Broadband Probe</b><br><br>
  <input id="url" value="https://1.1.1.1" style="width:68%">
  <button onclick="runProbe()">Probe</button>
  <pre id="probeOut"></pre>
</div>
<div class="card"><b>Live Telemetry JSON</b><pre id="raw"></pre></div>
<script>
async function loadStatus(){
  const r = await fetch('/api/pilot/status'); const d = await r.json();
  const bb = d.broadband.ok ? '<span class="ok">ONLINE ('+d.broadband.latency_ms+'ms)</span>' : '<span class="bad">OFFLINE</span>';
  const sm = d.safe_mode ? '<span class="warn">SAFE MODE (LOW RAM)</span>' : '<span class="ok">NOMINAL</span>';
  document.getElementById('summary').innerHTML =
    'LAN: <b>'+d.lan_ip+':'+d.pilot_port+'</b> | RAM Free: <b>'+d.mem_avail_mb+' MB</b> ('+sm+')<br>'+
    'Broadband: '+bb+' | Gateway 8090: '+(d.local_gateway.ok?'<span class="ok">UP</span>':'<span class="bad">DOWN</span>')+
    ' | WAL 8182: '+(d.local_wal.ok?'<span class="ok">UP</span>':'<span class="bad">DOWN</span>')+
    ' | HDC HMAC: '+(d.hdc_ring.attested?'<span class="ok">VERIFIED</span>':'<span class="warn">UNVERIFIED</span>');
  document.getElementById('raw').textContent = JSON.stringify(d, null, 2);
}
async function runProbe(){
  const u = encodeURIComponent(document.getElementById('url').value);
  const r = await fetch('/api/pilot/probe?url='+u);
  document.getElementById('probeOut').textContent = JSON.stringify(await r.json(), null, 2);
}
async function triggerHeal(){
  const r = await fetch('/api/pilot/heal', {method:'POST'});
  document.getElementById('probeOut').textContent = JSON.stringify(await r.json(), null, 2);
  loadStatus();
}
loadStatus(); setInterval(loadStatus, 10000);
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
        return self._send(404, json.dumps({"error": "not_found"}).encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/pilot/heal":
            mem_mb = get_mem_avail_mb()
            if 0 < mem_mb < 400:
                return self._send(200, json.dumps({"healed": False, "reason": "RAM Safe Mode active"}).encode("utf-8"))
            subprocess.Popen(["bash", "/data/data/com.termux/files/home/live-command-center/salathanie_recover.sh"])
            return self._send(200, json.dumps({"healed": True, "action": "triggered salathanie_recover.sh"}).encode("utf-8"))
        return self._send(404, json.dumps({"error": "not_found"}).encode("utf-8"))


if __name__ == "__main__":
    with HDCSharedMemoryBus() as bus:
        ACTIVE_PORT = bus.allocate_port(PREFERRED_PORT)
        bus.publish("salathanie-universal-pilot", ACTIVE_PORT, 200, deterministic_hv(f"pilot:{ACTIVE_PORT}:UP"))
    print(f"[OK] Universal Pilot UI live on http://{get_lan_ip()}:{ACTIVE_PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", ACTIVE_PORT), PilotHandler).serve_forever()
