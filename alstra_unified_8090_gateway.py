from polyglot_router import detect_language, enrich_payload, POLYGLOT_SYSTEM_DIRECTIVE
import ecosystem_router as _eco_router
#!/usr/bin/env python3
"""
SalathanieAI — Unified Port 8090 Gateway Proxy
Serves 8095 (3D Jet HUD -> fallback :8125/jet-3d), 8088 (Ingress -> fallback :8125/),
and live astra_flight_ledger.db / PX4 APIs under one gateway.
"""
import http.server
import json
import socket
import socketserver
import time
import urllib.request
from pathlib import Path

import astra_flight_ledger as ledger

PORT = 8090


def _proxy_try(targets: list[str], method: str = "GET", body: bytes = b"", ct: str = "application/json") -> tuple[int, str, bytes]:
    for url in targets:
        try:
            headers = {"User-Agent": "Salathanie-GW-8090/2.0"}
            if method == "POST":
                headers["Content-Type"] = ct
            req = urllib.request.Request(url, data=(body if method == "POST" else None), headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=4.0) as r:
                return r.status, r.headers.get("Content-Type", "text/html; charset=utf-8"), r.read()
        except Exception:
            continue
    return 502, "application/json", json.dumps({"error": "upstream_unreachable", "tried": targets}).encode("utf-8")


def _port_up(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.15)
        return s.connect_ex(("127.0.0.1", port)) == 0


GW_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alstra Unified Gateway // Port 8090</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:monospace}
body{background:#040812;color:#d6f5ff;padding:8px;font-size:11px}
.bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;justify-content:space-between;background:#0b1528;border:1px solid #0ff5;padding:6px 8px;border-radius:6px;margin-bottom:8px}
a.btn,button{background:#0ea5e9;color:#030812;border:none;padding:4px 8px;border-radius:4px;font-family:monospace;font-size:10px;font-weight:bold;text-decoration:none;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:6px;margin-bottom:8px}
.box{background:#0b1528;border:1px solid #1e3a5f;border-radius:6px;padding:6px}
.up{color:#39ff14;font-weight:bold}.fb{color:#fbbf24;font-weight:bold}
pre{background:#070d18;border:1px solid #1e3a5f;border-radius:6px;padding:6px;font-size:10px;max-height:170px;overflow:auto;white-space:pre-wrap}
</style></head><body>
<div class="bar">
  <b>ALSTRA UNIFIED GATEWAY (:8090)</b>
  <div>
    <a class="btn" href="/jet" target="_top">3D Jet (8095)</a>
    <a class="btn" style="background:#39ff14" href="/ingress" target="_top">Pilot/8088</a>
    <a class="btn" style="background:#f59e0b" href="http://127.0.0.1:8099" target="_top">Deck 8099</a>
  </div>
</div>
<div class="grid" id="nodes">Checking mesh routes...</div>
<pre id="led">Loading WAL flight ledger...</pre>
<script>
async function poll(){
  try{
    const s=await(await fetch('/api/gw/status')).json();
    document.getElementById('nodes').innerHTML=Object.entries(s.routes).map(([k,v])=>
      `<div class="box"><b>${k}</b><br><span class="${v.up?'up':'fb'}">${v.up?'DIRECT UP':'FAILOVER :8125'}</span><br><small>${v.target}</small></div>`
    ).join('');
    const l=await(await fetch('/api/ledger')).json();
    const g=(l.generations||[])[0]||{};
    document.getElementById('led').textContent=
      `WAL DB: ${l.wal.db_kb}KB (WAL ${l.wal.wal_kb}KB) | Gens: ${l.totals.generations} | Ext: ${l.totals.external_events} | PX4: ${l.totals.px4_points}\n`+
      `Latest: ${g.gen_id||'--'} | Fit: ${g.fitness??'--'} | Pods: ${g.pods_mask||'--'} | Stick: (${g.pilot_pitch??0}, ${g.pilot_roll??0}) | HMAC: ${g.hmac_sig||'--'}\n`+
      `PX4: ${l.px4_latest.vehicle_id} @ (${l.px4_latest.lat}, ${l.px4_latest.lon}) alt=${l.px4_latest.alt_m}m [${l.px4_latest.flight_mode}]`;
  }catch(e){}
}
poll(); setInterval(poll, 3000);
</script></body></html>""".encode("utf-8")



# _DIRECT_8090_FLYING_CAR_STEP
def _handle_8090_flying_car_step(handler, method: str = "GET", body: bytes = b"") -> bool:
    raw_p = getattr(handler, "path", "") or ""
    p = raw_p.split("?", 1)[0]
    if p not in ("/api/flying-car/step", "/api/evtol/szero-plus", "/api/evtol/szero-plus/simulate-runaway"):
        return False
    out = None
    try:
        import urllib.request
        req = urllib.request.Request(
            f"http://127.0.0.1:8132{p}",
            data=(body if method == "POST" else None),
            method=method,
            headers={"Content-Type": "application/json"} if method == "POST" else {},
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            out = resp.read()
    except Exception:
        pass
    if not out:
        try:
            import json, car_port_bridge as _cb
            ov = json.loads(body.decode("utf-8") or "{}") if (method == "POST" and body) else None
            out = json.dumps(_cb.get_step_feed(ov if isinstance(ov, dict) else None)).encode("utf-8")
        except Exception:
            out = b'{"ok":false,"gateway":8090,"endpoint":"/api/flying-car/step"}'
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(out)))
        handler.end_headers()
        handler.wfile.write(out)
    except Exception:
        pass
    return True


# _DIRECT_8090_HUB_ROUTES
def _handle_8090_hub_routes(handler) -> bool:
    import urllib.request
    from pathlib import Path as _P
    p = (getattr(handler, "path", "") or "").split("?", 1)[0]
    targets = {
        "/flying-car": ("http://127.0.0.1:8101/", "text/html; charset=utf-8"),
        "/avatars": ("http://127.0.0.1:8102/", "text/html; charset=utf-8"),
        "/api/hub/state": ("http://127.0.0.1:8101/api/hub/state", "application/json; charset=utf-8"),
        "/api/flying-car/step": ("http://127.0.0.1:8132/api/flying-car/step", "application/json; charset=utf-8"),
    }
    if p.startswith("/static/"):
        targets[p] = (f"http://127.0.0.1:8102{p}", "image/jpeg")
    if p == "/ecosystem":
        mf = _P("/data/data/com.termux/files/home/live-command-center/master_ecosystem_map.json")
        data = mf.read_text(encoding="utf-8") if mf.exists() else "{}"
        page = (
            "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>SalathanieAI Master Ecosystem Map</title>"
            "<style>body{background:#060b14;color:#e2f1ff;font-family:system-ui;padding:14px}a{color:#34f5c5;margin-right:10px}pre{background:#0b1524;border:1px solid #1a3554;padding:12px;border-radius:8px;overflow:auto;font-size:12px}</style>"
            "</head><body><h2>SALATHANIE AI // ALL REPOS, PORTS & GOLDEN VAULTS</h2>"
            "<p><a href='http://127.0.0.1:8088/'>:8088 OMEGA Dashboard</a>"
            "<a href='http://127.0.0.1:8090/flying-car'>:8090 Flying Car</a>"
            "<a href='http://127.0.0.1:8090/avatars'>:8090 Avatars</a>"
            "<a href='http://127.0.0.1:8090/jet'>:8090 3D Jet HUD</a>"
            "<a href='http://127.0.0.1:8132/'>:8132 Car HUD</a>"
            "<a href='http://127.0.0.1:8159/'>:8159 Dual-Persona</a></p>"
            "<pre>" + data.replace("&","&amp;").replace("<","&lt;") + "</pre></body></html>"
        ).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(page)))
        handler.end_headers()
        handler.wfile.write(page)
        return True
    if p not in targets:
        return False
    url, ctype = targets[p]
    body = None
    try:
        with urllib.request.urlopen(url, timeout=0.9) as r:
            body = r.read()
    except Exception:
        if p == "/api/flying-car/step":
            sf = _P("/data/data/com.termux/files/home/live-command-center/car_port_bridge_state.json")
            if sf.exists():
                body = sf.read_bytes()
    if not body:
        body = b'{"ok":true,"fallback":true,"source":"8090-direct"}'
        ctype = "application/json; charset=utf-8"
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except Exception:
        pass
    return True

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class H(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        if _eco_router.handle_get(self):
            return
        if _handle_8090_hub_routes(self):
            return
        if _handle_8090_flying_car_step(self, 'GET'):
            return
        p = self.path.split("?")[0]
        if p in ("/api/languages", "/api/polyglot"):
            body = json.dumps({
                "ok": True,
                "all_languages": True,
                "mode": "ISO-639-UNIVERSAL-AUTO",
                "directive": POLYGLOT_SYSTEM_DIRECTIVE,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p in ("/api/manifest", "/api/telemetry/spine", "/api/evtol/spine"):
            c, ct, data = _proxy_try([f"http://127.0.0.1:8159{self.path}"])
            self.send_response(c)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(data)
            return
        if p == "/":
            return self._send(200, "text/html; charset=utf-8", GW_HTML)
        if p == "/api/gw/status":
            st = {
                "ok": True, "port": PORT, "ts": int(time.time()),
                "routes": {
                    "8095_JET_HUD": {"up": _port_up(8095), "target": "/jet -> 8095 | 8125/jet-3d"},
                    "8088_INGRESS": {"up": _port_up(8088), "target": "/ingress -> 8088 | 8125/"},
                    "8099_DECK": {"up": _port_up(8099), "target": "127.0.0.1:8099"},
                    "8125_PILOT": {"up": _port_up(8125), "target": "127.0.0.1:8125"},
                },
            }
            return self._send(200, "application/json", json.dumps(st).encode("utf-8"))
        if p == "/api/ledger":
            return self._send(200, "application/json", json.dumps(ledger.get_ledger_snapshot(15)).encode("utf-8"))
        if p in ("/jet", "/jet/", "/8095"):
            c, ct, data = _proxy_try(["http://127.0.0.1:8095/", "http://127.0.0.1:8125/jet-3d"])
            return self._send(c, ct, data)
        if p in ("/ingress", "/ingress/", "/8088"):
            c, ct, data = _proxy_try(["http://127.0.0.1:8088/", "http://127.0.0.1:8125/"])
            return self._send(c, ct, data)
        if p == "/api/hud":
            c, ct, data = _proxy_try(["http://127.0.0.1:8095/api/hud", "http://127.0.0.1:8125/api/hud"])
            return self._send(c, ct, data)
        c, ct, data = _proxy_try([f"http://127.0.0.1:8125{self.path}"])
        return self._send(c, ct, data)

    def do_POST(self):
        _ln = int(self.headers.get('Content-Length') or '0')
        _bd = self.rfile.read(_ln) if _ln > 0 else b'{}'
        if _eco_router.handle_post(self, _bd):
            return
        if _handle_8090_flying_car_step(self, 'POST', _bd):
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(min(length, 65536)) if length else b"{}"
        p = self.path.split("?")[0]
        if p in ("/api/polyglot/route", "/api/languages/detect"):
            try:
                req = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                req = {}
            enriched = enrich_payload(req, self.headers.get("Accept-Language"))
            body = json.dumps({"ok": True, **enriched}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p in ("/api/telemetry/spine", "/api/telemetry/ingest", "/api/evtol/spine"):
            c, ct, data = _proxy_try([f"http://127.0.0.1:8159{self.path}"], "POST", raw)
            self.send_response(c)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(data)
            return
        if p == "/api/px4":
            body = json.loads(raw.decode("utf-8", errors="ignore") or "{}")
            return self._send(200, "application/json", json.dumps({"ok": True, "px4": ledger.record_px4(body, "px4_gw_8090")}).encode("utf-8"))
        if p in ("/api/mode", "/api/pods", "/api/pilot"):
            c, ct, data = _proxy_try([f"http://127.0.0.1:8095{p}", f"http://127.0.0.1:8125{p}"], "POST", raw)
            return self._send(c, ct, data)
        c, ct, data = _proxy_try([f"http://127.0.0.1:8125{self.path}"], "POST", raw)
        return self._send(c, ct, data)

    def _send(self, code, ct, data):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    with Server(("0.0.0.0", PORT), H) as srv:
        srv.serve_forever()
