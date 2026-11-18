#!/usr/bin/env python3
"""
Unified Mirror Gateway on Port 8090:
- Proxies all live 8088 API & UI routes seamlessly so 8090 never breaks
- Injects live Genius Brain (8099) & Master Spine (8095) control deck into the UI
"""
import http.server
import socketserver
import urllib.request
import urllib.error

PORT = 8090
UPSTREAM_8088 = "http://127.0.0.1:8088"

OVERLAY_WIDGET = """
<div id="alstra-8095-8099-deck" style="margin:12px auto;max-width:1280px;padding:12px;background:#06131f;border:1px solid #00f0ff;border-radius:8px;font-family:monospace;color:#d6f8ff;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <strong style="color:#00f0ff;">ALSTRA UNIVERSAL TELEMETRY & GENIUS BRAIN MESH (8095 MASTER SPINE // 8099 WAL BRAIN)</strong>
    <button onclick="syncAlstraBrain()" style="background:#00f0ff;color:#041018;border:none;padding:4px 10px;border-radius:4px;font-weight:bold;cursor:pointer;">SYNC 8095 + 8099</button>
  </div>
  <div id="alstra-brain-telemetry-bar" style="font-size:12px;color:#00ff9d;">Connecting to 127.0.0.1:8095 & 127.0.0.1:8099...</div>
</div>
<script>
async function syncAlstraBrain() {
  try {
    const [mRes, bRes] = await Promise.all([
      fetch('http://127.0.0.1:8095/v1/telemetry').then(r => r.json()),
      fetch('http://127.0.0.1:8099/v1/telemetry').then(r => r.json())
    ]);
    const hw = mRes.hardware || {};
    document.getElementById('alstra-brain-telemetry-bar').textContent =
      `[MASTER 8095: ${mRes.status}] Temp: ${hw.temperature_c}°C | Load: ${hw.load_1m} | Workers: ${mRes.worker_count}  ||  ` +
      `[BRAIN 8099 WAL: ${bRes.status}] Context Keys: ${bRes.context_keys_count} | Ledger Tasks: ${bRes.cumulative_tasks_executed}`;
  } catch (e) {
    document.getElementById('alstra-brain-telemetry-bar').textContent = 'Syncing 8095/8099 endpoints...';
  }
}
syncAlstraBrain();
setInterval(syncAlstraBrain, 6000);
</script>
"""

class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True

class GatewayHandler(http.server.BaseHTTPRequestHandler):
    def _proxy(self, method: str):
        target = UPSTREAM_8088 + self.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else None
        headers = {"Content-Type": self.headers.get("Content-Type", "application/json")} if body else {}
        req = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "text/html")
                if "text/html" in ctype and b"alstra-8095-8099-deck" not in raw:
                    html = raw.decode("utf-8", errors="ignore")
                    if "</body>" in html:
                        html = html.replace("</body>", OVERLAY_WIDGET + "\n</body>")
                    else:
                        html += OVERLAY_WIDGET
                    raw = html.encode("utf-8")
                self.send_response(resp.status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        except Exception as exc:
            err = json.dumps({"ok": False, "upstream": target, "error": str(exc)}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def do_GET(self):
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")

if __name__ == "__main__":
    import json
    with ReuseTCP(("127.0.0.1", PORT), GatewayHandler) as srv:
        print(f"[✔] Unified Mirror Gateway active on 127.0.0.1:{PORT} -> proxying 8088 + 8095/8099")
        srv.serve_forever()
