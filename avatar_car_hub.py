from polyglot_router import enrich_payload, POLYGLOT_SYSTEM_DIRECTIVE
#!/usr/bin/env python3
"""
SalathanieAI — Dual-Port Electric Flying Car (:8101) & Tri-Avatar Command Hub (:8102)
Serves:
  - :8101 -> Astra + Alstra = SalathanieAI Electric Flying Car, S-Zero Plus eVTOL & Solar Deck
  - :8102 -> Tri-Avatar Cabin Deck (Astra, Alstra, and SalathanieAI Half-Man / Half-Robot Avatar)
Additive-only, single lightweight process.
"""
import http.server
import json
import mimetypes
import threading
import time
from pathlib import Path

REPO = Path("/data/data/com.termux/files/home/live-command-center")
STATIC_DIR = REPO / "static"


def _read_json(name: str) -> dict:
    p = REPO / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _hub_state() -> dict:
    bridge = _read_json("car_port_bridge_state.json")
    solar = _read_json("solar_telemetry_state.json")
    szero = _read_json("szero_plus_evtol_state.json")
    custom_img = None
    for cand in ("salathanie_cyborg.jpg", "salathanie_cyborg.png", "salathanie_avatar.jpg", "salathanie_avatar.png"):
        if (STATIC_DIR / cand).exists():
            custom_img = f"/static/{cand}"
            break
    return {
        "ok": True,
        "ts": int(time.time()),
        "ports": {"car_deck": 8101, "avatar_deck": 8102, "gateway": 8090, "ingress": 8088, "bridge": 8132},
        "custom_avatar_url": custom_img,
        "bridge": bridge,
        "solar": solar,
        "szero": szero,
    }


def _render_html(default_tab: str = "car") -> bytes:
    title = "SALATHANIE AI // ELECTRIC FLYING CAR (:8101)" if default_tab == "car" else "SALATHANIE AI // TRI-AVATAR DECK (:8102)"
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,-apple-system,sans-serif}}
  body{{background:#060b14;color:#e2f1ff;padding:12px}}
  .top{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;justify-content:space-between;border-bottom:1px solid #16304d;padding-bottom:10px;margin-bottom:12px}}
  .brand{{font-weight:800;font-size:15px;letter-spacing:.6px;color:#38f2d4}}
  .nav{{display:flex;flex-wrap:wrap;gap:6px}}
  .nav a{{text-decoration:none;font-size:12px;font-weight:700;padding:5px 9px;border-radius:6px;background:#102238;color:#c9ecff;border:1px solid #1e4268}}
  .nav a.hi{{background:#0b5c4d;color:#d8fff6;border-color:#28e0b9}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;margin-bottom:12px}}
  .card{{background:#0b1524;border:1px solid #1a3554;border-radius:10px;padding:12px}}
  .card h2{{font-size:13px;text-transform:uppercase;letter-spacing:.8px;color:#52d1ff;margin-bottom:8px}}
  .val{{font-size:20px;font-weight:800;color:#34f5c5;margin-bottom:4px}}
  .meta{{font-size:12px;color:#93b4d4;line-height:1.45}}
  .avatars{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}}
  .av{{background:#091321;border:1px solid #1f486e;border-radius:10px;padding:12px;text-align:center}}
  .av.cyborg{{border-color:#34f5c5;box-shadow:0 0 14px rgba(52,245,197,.16)}}
  .av-box{{width:128px;height:128px;margin:0 auto 8px;border-radius:50%;overflow:hidden;border:2px solid #34f5c5;display:flex;align-items:center;justify-content:center;background:#050a12}}
  .av-box img{{width:100%;height:100%;object-fit:cover}}
  .badge{{display:inline-block;margin-top:4px;font-size:11px;padding:2px 8px;border-radius:99px;background:#0d3b39;color:#52ffd8}}
</style>
</head>
<body>
<div class="top">
  <div class="brand">ASTRA + ALSTRA = SALATHANIE AI // CAR &amp; AVATAR COMMAND</div>
  <div class="nav">
    <a href="http://127.0.0.1:8090/">:8090 Gateway</a>
    <a href="http://127.0.0.1:8088/">:8088 Ingress</a>
    <a class="hi" href="http://127.0.0.1:8101/">:8101 Flying Car</a>
    <a class="hi" href="http://127.0.0.1:8102/">:8102 Avatars</a>
    <a href="http://127.0.0.1:8132/">:8132 Car HUD</a>
    <a href="http://127.0.0.1:8090/jet">3D Jet HUD</a>
  </div>
</div>

<div class="avatars" style="margin-bottom:12px">
  <div class="av cyborg">
    <div class="av-box" id="cyborg_slot">
      <svg viewBox="0 0 120 120" width="120" height="120">
        <defs><linearGradient id="g" x1="0" x2="1"><stop offset="0%" stop-color="#d49b6a"/><stop offset="50%" stop-color="#c68642"/><stop offset="51%" stop-color="#19334d"/><stop offset="100%" stop-color="#34f5c5"/></linearGradient></defs>
        <circle cx="60" cy="60" r="56" fill="#071220" stroke="#34f5c5" stroke-width="2"/>
        <path d="M60 18 C38 18 28 34 28 58 C28 84 42 100 60 102 Z" fill="#8d5524"/>
        <path d="M60 18 C82 18 92 34 92 58 C92 84 78 100 60 102 Z" fill="#132c44" stroke="#34f5c5" stroke-width="1.5"/>
        <ellipse cx="46" cy="54" rx="6" ry="3.5" fill="#111"/>
        <rect x="67" y="49" width="16" height="8" rx="3" fill="#34f5c5"/>
        <line x1="60" y1="18" x2="60" y2="102" stroke="#52d1ff" stroke-width="2"/>
        <path d="M44 74 Q52 77 60 75" stroke="#111" stroke-width="3" fill="none"/>
        <line x1="62" y1="74" x2="80" y2="74" stroke="#34f5c5" stroke-width="2"/>
        <line x1="66" y1="64" x2="86" y2="64" stroke="#52d1ff" stroke-width="1"/>
      </svg>
    </div>
    <div><strong>SALATHANIE AI (MODEL)</strong></div>
    <div class="meta">Half-Man / Half-Robot Cybernetic Pilot</div>
    <span class="badge">PRIMARY CORE ONLINE</span>
  </div>

  <div class="av">
    <div class="av-box">
      <svg viewBox="0 0 120 120" width="120" height="120">
        <circle cx="60" cy="60" r="54" fill="#091b33" stroke="#52d1ff" stroke-width="2"/>
        <circle cx="60" cy="48" r="22" fill="none" stroke="#52d1ff" stroke-width="2.5"/>
        <circle cx="52" cy="46" r="3" fill="#52d1ff"/><circle cx="68" cy="46" r="3" fill="#52d1ff"/>
        <path d="M32 96 Q60 74 88 96" fill="none" stroke="#52d1ff" stroke-width="2.5"/>
      </svg>
    </div>
    <div><strong>ASTRA CORE v10</strong></div>
    <div class="meta">Autonomous Flight &amp; Spatial Telemetry</div>
    <span class="badge">ACTIVE LINK</span>
  </div>

  <div class="av">
    <div class="av-box">
      <svg viewBox="0 0 120 120" width="120" height="120">
        <circle cx="60" cy="60" r="54" fill="#0d1730" stroke="#a78bfa" stroke-width="2"/>
        <polygon points="60,22 86,62 60,96 34,62" fill="none" stroke="#a78bfa" stroke-width="2.5"/>
        <circle cx="60" cy="58" r="8" fill="#a78bfa"/>
      </svg>
    </div>
    <div><strong>ALSTRA LEDGER ENGINE</strong></div>
    <div class="meta">EV Powertrain, Solar Bus &amp; Self-Healing</div>
    <span class="badge">SYNCED WAL</span>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Electric Flying Car Status</h2>
    <div class="val" id="car_mode">LOADING...</div>
    <div class="meta" id="car_meta">Waiting for bridge telemetry...</div>
  </div>
  <div class="card">
    <h2>S-Zero Plus eVTOL (400V-800V)</h2>
    <div class="val" id="sz_bus">-- V</div>
    <div class="meta" id="sz_meta">Waiting for eVTOL feed...</div>
  </div>
  <div class="card">
    <h2>Solar Supercomputer Bus</h2>
    <div class="val" id="sol_w">-- W</div>
    <div class="meta" id="sol_meta">Waiting for solar telemetry...</div>
  </div>
</div>

<script>
async function poll(){{
  try{{
    const r = await fetch('/api/hub/state');
    const d = await r.json();
    if(d.custom_avatar_url){{
      document.getElementById('cyborg_slot').innerHTML = '<img src="'+d.custom_avatar_url+'" alt="SalathanieAI Cyborg Avatar"/>';
    }}
    const b = d.bridge || {{}};
    document.getElementById('car_mode').textContent = b.mode || 'EV-FLIGHT READY';
    document.getElementById('car_meta').textContent =
      'Online Ports: ' + ((b.online_ports || []).join(', ') || '8090, 8101, 8102, 8125, 8132') +
      ' | Host RAM: ' + (b.host_ram_pct ?? '--') + '%';
    const z = d.szero || {{}}; const hv = z.hv_dc_bus || {{}}; const bt = z.btms || {{}};
    document.getElementById('sz_bus').textContent = (hv.bus_v ?? '--') + 'V | ' + (hv.thermal_runaway_indicator || 'NOMINAL');
    document.getElementById('sz_meta').textContent =
      'Phase: ' + (z.flight_phase || '--') + ' | SoC: ' + (hv.soc_pct ?? '--') + '% | BTMS Flow: ' + (bt.pump_flow_lpm ?? '--') + ' L/m';
    const s = d.solar || {{}}; const sl = s.solar || {{}}; const sc = s.supercomputer || {{}};
    document.getElementById('sol_w').textContent = (sl.solar_w ?? '--') + 'W / ' + (sc.supercomputer_w ?? '--') + 'W';
    document.getElementById('sol_meta').textContent =
      'Mode: ' + (s.power_mode || '--') + ' | Net Charge: ' + (sc.net_charge_w ?? '--') + 'W | Batt SoC: ' + (sc.battery_soc_pct ?? '--') + '%';
  }}catch(e){{}}
}}
poll(); setInterval(poll, 3000);
</script>
</body>
</html>"""
    return html.encode("utf-8")


class ReusableHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _make_handler(default_tab: str):
    class HubHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            p = (self.path or "/").split("?", 1)[0]
            if p == "/api/hub/state":
                return self._send(200, json.dumps(_hub_state()).encode("utf-8"), "application/json; charset=utf-8")
            if p.startswith("/static/"):
                fp = STATIC_DIR / Path(p).name
                if fp.exists() and fp.is_file():
                    ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
                    return self._send(200, fp.read_bytes(), ctype)
                return self._send(404, b"not found", "text/plain")
            if p == "/avatars":
                return self._send(200, _render_html("avatars"))
            if p == "/flying-car":
                return self._send(200, _render_html("car"))
            return self._send(200, _render_html(default_tab))
    return HubHandler


def serve():
    s8101 = ReusableHTTPServer(("127.0.0.1", 8101), _make_handler("car"))
    s8102 = ReusableHTTPServer(("127.0.0.1", 8102), _make_handler("avatars"))
    threading.Thread(target=s8101.serve_forever, daemon=True).start()
    s8102.serve_forever()


if __name__ == "__main__":
    serve()
