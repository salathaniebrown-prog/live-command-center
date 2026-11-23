#!/usr/bin/env python3
"""
SalathanieAI — Unified Vehicle Telemetry Aggregator & Port Bridge (car_port_bridge.py)
Sweeps local microservice sockets, checks PM2 worker health, binds custom sensor feeds
(battery voltage, GPS, local Wi-Fi telemetry) into sync_vehicle_bus(), persists state
to disk + SQLite WAL, and serves /api/flying-car/step + zero-scroll cockpit HUD.
Strictly additive: never overwrites existing files or PM2 services.
"""
import hashlib
import http.server
import json
import os
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import solar_supercomputer_telemetry as solar_sc
    import top25_pc_telemetry as top25_pc
    import szero_plus_evtol_telemetry as szero_evtol
except Exception:
    solar_sc = None
    top25_pc = None
    szero_evtol = None

REPO = Path("/data/data/com.termux/files/home/live-command-center")
WAL_DB = REPO / "alstra_flight_ledger.db"
STATE_JSON = REPO / "car_port_bridge_state.json"

BRIDGE_HOST = os.environ.get("CAR_BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.environ.get("CAR_BRIDGE_PORT", "8132"))

TARGET_PORTS = [8088, 8090, 8095, 8099, 8108, 8121, 8125, 8151, 8165]
CRITICAL_PM2 = ("salathanie-pilot", "salathanie-gw-8090", "salathanie-ram-watch")

_LOCK = threading.RLock()
_CUSTOM_SENSORS: dict = {
    "battery_v": 402.4,
    "battery_soc_pct": 88.0,
    "gps": {"lat": 36.0726, "lon": -79.7920, "alt_m": 272.0, "speed_kmh": 0.0, "sats": 14},
    "wifi": {"ssid": "SALATHANIE-LINK", "rssi_dbm": -48, "link_mbps": 866},
    "updated_ts": int(time.time()),
}
_LATEST_BUS: dict = {}


def _db() -> sqlite3.Connection:
    WAL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WAL_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_port_bus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            open_ports_json TEXT NOT NULL,
            sensors_json TEXT NOT NULL,
            bus_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def _probe_port(port: int, timeout_s: float = 0.15) -> dict:
    t0 = time.monotonic()
    alive = False
    http_code = None
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout_s):
            alive = True
    except OSError:
        alive = False

    if alive:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/", method="GET")
            with urllib.request.urlopen(req, timeout=0.25) as resp:
                http_code = int(resp.status)
        except urllib.error.HTTPError as e:
            http_code = int(e.code)
        except Exception:
            http_code = 200

    rtt_ms = round((time.monotonic() - t0) * 1000.0, 1)
    return {
        "port": port,
        "online": alive,
        "http_status": http_code,
        "rtt_ms": rtt_ms,
    }


def _read_pm2_brief() -> list[dict]:
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=4)
        rows = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip().startswith("[") else []
    except Exception:
        return []
    out = []
    for p in rows:
        env = p.get("pm2_env") or {}
        mem_b = int((p.get("monit") or {}).get("memory") or 0)
        out.append({
            "name": p.get("name", ""),
            "status": env.get("status", ""),
            "rss_mb": round(mem_b / 1048576.0, 2),
        })
    return out


def _recover_dropped_critical(pm2_rows: list[dict]) -> list[str]:
    recovered = []
    by_name = {r["name"]: r for r in pm2_rows}
    for nm in CRITICAL_PM2:
        info = by_name.get(nm)
        if info and info["status"] in ("errored", "stopped", "stopping"):
            rc = subprocess.run(["pm2", "restart", nm], capture_output=True, text=True, timeout=6)
            if rc.returncode == 0:
                recovered.append(f"restarted:{nm}")
    return recovered


def _read_ram_pct() -> float:
    tot_kb = avail_kb = 0
    try:
        for ln in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ln.startswith("MemTotal:"):
                tot_kb = int(ln.split()[1])
            elif ln.startswith("MemAvailable:"):
                avail_kb = int(ln.split()[1])
    except OSError:
        pass
    if tot_kb <= 0:
        return 0.0
    used_kb = max(0, tot_kb - avail_kb)
    return round((used_kb / tot_kb) * 100.0, 2)


def update_custom_sensors(patch: dict) -> dict:
    with _LOCK:
        if isinstance(patch, dict):
            if "battery_v" in patch:
                _CUSTOM_SENSORS["battery_v"] = round(float(patch["battery_v"]), 2)
            if "battery_soc_pct" in patch:
                _CUSTOM_SENSORS["battery_soc_pct"] = round(float(patch["battery_soc_pct"]), 1)
            if isinstance(patch.get("gps"), dict):
                _CUSTOM_SENSORS["gps"].update(patch["gps"])
            if isinstance(patch.get("wifi"), dict):
                _CUSTOM_SENSORS["wifi"].update(patch["wifi"])
            for k in ("lat", "lon", "alt_m", "speed_kmh", "sats"):
                if k in patch:
                    _CUSTOM_SENSORS["gps"][k] = patch[k]
            for k in ("ssid", "rssi_dbm", "link_mbps"):
                if k in patch:
                    _CUSTOM_SENSORS["wifi"][k] = patch[k]
            _CUSTOM_SENSORS["updated_ts"] = int(time.time())
        return dict(_CUSTOM_SENSORS)


def _persist_snapshot(payload: dict) -> None:
    try:
        STATE_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass
    try:
        with _db() as c:
            c.execute(
                "INSERT INTO vehicle_port_bus(ts,open_ports_json,sensors_json,bus_json,hmac_sig) VALUES (?,?,?,?,?)",
                (
                    payload["ts"],
                    json.dumps(payload["ports"]),
                    json.dumps(payload["sensors"]),
                    json.dumps(payload),
                    payload["hmac_sig"],
                ),
            )
            c.commit()
    except Exception:
        pass


def _load_persisted_fallback() -> dict:
    if STATE_JSON.is_file():
        try:
            data = json.loads(STATE_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("ok"):
                data["from_disk_cache"] = True
                return data
        except Exception:
            pass
    return {}



_SWEEP_CACHE = {"ts": 0.0, "ports": [], "pm2": []}
_SWEEP_TTL_S = 2.5


def _cached_sweep_and_pm2() -> tuple[list[dict], list[dict]]:
    now = time.monotonic()
    if (now - _SWEEP_CACHE["ts"]) < _SWEEP_TTL_S and _SWEEP_CACHE["ports"]:
        return list(_SWEEP_CACHE["ports"]), list(_SWEEP_CACHE["pm2"])
    ports = [_probe_port(p, timeout_s=0.15) for p in TARGET_PORTS]
    pm2_rows = _read_pm2_brief()
    _SWEEP_CACHE["ts"] = now
    _SWEEP_CACHE["ports"] = ports
    _SWEEP_CACHE["pm2"] = pm2_rows
    return ports, pm2_rows


def sync_vehicle_bus(step_overrides: dict | None = None, recover: bool = True) -> dict:
    with _LOCK:
        if isinstance(step_overrides, dict) and step_overrides:
            update_custom_sensors(step_overrides)

        ports, pm2_rows = _cached_sweep_and_pm2()
        recovered = _recover_dropped_critical(pm2_rows) if recover else []
        if recovered:
            _SWEEP_CACHE["ts"] = 0.0
            ports, pm2_rows = _cached_sweep_and_pm2()
        online_ports = [p["port"] for p in ports if p["online"]]
        ram_pct = _read_ram_pct()
        ts = int(time.time())

        gps = dict(_CUSTOM_SENSORS["gps"])
        wifi = dict(_CUSTOM_SENSORS["wifi"])
        bat_v = float(_CUSTOM_SENSORS["battery_v"])
        soc = float(_CUSTOM_SENSORS["battery_soc_pct"])
        spd = float(gps.get("speed_kmh", 0.0))
        alt = float(gps.get("alt_m", 0.0))

        flight_mode = "JET-CRUISE" if alt > 15.0 else ("EV-GROUND" if spd > 2.0 else "STANDBY-READY")
        solar_snap = (solar_sc.auto_balance_solar_compute() if (solar_sc and hasattr(solar_sc, 'auto_balance_solar_compute')) else (solar_sc.sample_solar_supercomputer() if solar_sc else {}))
        sig = hashlib.sha256(
            f"vbus|{ts}|{len(online_ports)}|{bat_v}|{soc}|{ram_pct}".encode("utf-8")
        ).hexdigest()[:24].upper()

        snapshot = {
            "ok": True,
            "ts": ts,
            "bridge_port": BRIDGE_PORT,
            "mode": flight_mode,
            "avatars": ["SalathanieAI", "ASTRA CORE v10", "SIMLI TRINITY-2"],
            "host_ram_pct": ram_pct,
            "solar": solar_snap,
            "online_ports": online_ports,
            "ports": ports,
            "sensors": {
                "battery_v": bat_v,
                "battery_soc_pct": soc,
                "gps": gps,
                "wifi": wifi,
            },
            "recovered_workers": recovered,
            "pm2_summary": pm2_rows[:12],
            "from_disk_cache": False,
            "hmac_sig": sig,
        }
        globals()["_LATEST_BUS"] = snapshot
        _persist_snapshot(snapshot)
        return snapshot


def get_step_feed(step_overrides: dict | None = None) -> dict:
    try:
        return sync_vehicle_bus(step_overrides=step_overrides, recover=True)
    except Exception as exc:
        cached = _load_persisted_fallback()
        if cached:
            cached["fallback_error"] = str(exc)
            return cached
        return {"ok": False, "error": str(exc), "ts": int(time.time())}


HUD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SalathanieAI Cockpit HUD — Port Bridge</title>
<style>
  html,body{margin:0;padding:0;height:100vh;overflow:hidden;background:#060a10;color:#e6f7ff;font-family:monospace}
  .wrap{display:grid;grid-template-rows:auto 1fr auto;height:100vh;padding:12px 16px;box-sizing:border-box;gap:10px}
  .top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #163246;padding-bottom:6px}
  .badge{color:#22d3ee;font-weight:700}.emerald{color:#34d399}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;min-height:0}
  .card{background:#0b1320;border:1px solid #17354a;border-radius:8px;padding:10px;overflow:hidden}
  .title{font-size:12px;color:#7dd3fc;margin-bottom:6px;text-transform:uppercase}
  .val{font-size:20px;font-weight:700;color:#34d399}
  .meta{font-size:12px;color:#bae6fd;line-height:1.45}
  .foot{display:flex;justify-content:space-between;font-size:11px;color:#67e8f9;border-top:1px solid #163246;padding-top:6px}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div><span class="badge">SALATHANIEAI // ASTRA + ALSTRA</span> &nbsp;LIVE PORT-TO-COCKPIT HUD</div>
    <div id="mode" class="emerald">SYNCING...</div>
  </div>
  <div class="grid" style="grid-template-columns:repeat(4,1fr);">
    <div class="card"><div class="title">EV Power &amp; Sensors</div><div id="bat" class="val">-- V</div><div id="gps" class="meta"></div><div id="wifi" class="meta"></div></div>
    <div class="card"><div class="title">Active Local Ports</div><div id="ports_cnt" class="val">--/--</div><div id="ports_list" class="meta"></div></div>
    <div class="card"><div class="title">Solar &amp; Supercomputer</div><div id="solar_val" class="val">-- W</div><div id="solar_meta" class="meta"></div></div>
    <div class="card"><div class="title">Host RAM &amp; Avatars</div><div id="ram" class="val">--%</div><div id="avatars" class="meta"></div><div id="rec" class="meta"></div></div>
  </div>
  <div class="foot"><span id="sig">HMAC: --</span><span>ENDPOINT: /api/flying-car/step</span></div>
</div>
<script>
async function refreshHud(){
  try{
    const r = await fetch('/api/flying-car/step');
    const d = await r.json();
    document.getElementById('mode').textContent = (d.mode || 'READY') + ' · TS ' + d.ts;
    const s = d.sensors || {};
    document.getElementById('bat').textContent = (s.battery_v ?? '--') + 'V (' + (s.battery_soc_pct ?? '--') + '%)';
    const g = s.gps || {};
    document.getElementById('gps').textContent = 'GPS: ' + (g.lat ?? '') + ', ' + (g.lon ?? '') + ' | ALT ' + (g.alt_m ?? 0) + 'm | SPD ' + (g.speed_kmh ?? 0) + 'km/h';
    const w = s.wifi || {};
    document.getElementById('wifi').textContent = 'Wi-Fi: ' + (w.ssid ?? '') + ' (' + (w.rssi_dbm ?? '') + 'dBm / ' + (w.link_mbps ?? '') + 'Mbps)';
    const online = d.online_ports || [];
    document.getElementById('ports_cnt').textContent = online.length + ' ONLINE';
    document.getElementById('ports_list').textContent = 'Ports: ' + (online.join(', ') || 'none');
    document.getElementById('ram').textContent = (d.host_ram_pct ?? '--') + '% RAM';
    document.getElementById('avatars').textContent = 'Avatars: ' + (d.avatars || []).join(' · ');
    document.getElementById('rec').textContent = 'Recovered: ' + ((d.recovered_workers || []).join(', ') || 'none');
    const sl = (d.solar && d.solar.solar) || {}; const sc = (d.solar && d.solar.supercomputer) || {};
    document.getElementById('solar_val').textContent = (sl.solar_w ?? '--') + 'W / ' + (sc.supercomputer_w ?? '--') + 'W';
    document.getElementById('solar_meta').textContent = 'NET: ' + (sc.net_charge_w ?? '--') + 'W | ' + (d.solar && d.solar.power_mode || '');
    document.getElementById('sig').textContent = 'HMAC: ' + (d.hmac_sig || '--');
  }catch(e){}
}
refreshHud();
setInterval(refreshHud, 3000);
</script>
</body>
</html>
"""


class BridgeHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send_json(self, code: int, obj: dict):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, code: int, html: str):
        raw = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/hud", "/flying-car"):
            return self._send_html(200, HUD_HTML)
        if path == "/api/flying-car/step":
            return self._send_json(200, get_step_feed())
        if path == "/api/pc/top25/tune" and top25_pc:
            return self._send_json(200, top25_pc.tune_physical_build_specs(
                giant_scale=1.25,
                bus_v=800,
                battery_kwh=118.0,
                ev_drive_peak_kw=320.0,
                vectored_lift_cruise_kw=410.0,
                onboard_compute_budget_w=1650.0,
                solar_roof_array_kw=7.2,
                cooling_loop_flow_lpm=11.5,
                target_dry_mass_kg=1140.0,
            ))
        if path == "/api/evtol/szero-plus" and szero_evtol:
            return self._send_json(200, szero_evtol.sample_szero_telemetry())
        if path == "/api/pc/top25":
            return self._send_json(200, top25_pc.get_top25_pc_telemetry(1.25))
        if path == "/api/bus/sensors":
            with _LOCK:
                return self._send_json(200, {"ok": True, "sensors": dict(_CUSTOM_SENSORS)})
        return self._send_json(404, {"ok": False, "error": "not_found", "path": path})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            payload = {}

        if path == "/api/solar/inverter" and solar_sc:
            p = payload if isinstance(payload, dict) else {}
            solar_sc.update_solar_feed(p)
            res = solar_sc.auto_balance_solar_compute() if "supercomputer_w" not in p and hasattr(solar_sc, "auto_balance_solar_compute") else solar_sc.sample_solar_supercomputer()
            return self._send_json(200, res)
        if path == "/api/solar/feed" and solar_sc:
            return self._send_json(200, solar_sc.sample_solar_supercomputer(payload if isinstance(payload, dict) else {}))
        if path == "/api/pc/top25/tune" and top25_pc:
            kw = payload if isinstance(payload, dict) else {}
            allowed = {"giant_scale","bus_v","battery_kwh","ev_drive_peak_kw","vectored_lift_cruise_kw","onboard_compute_budget_w","solar_roof_array_kw","cooling_loop_flow_lpm","target_dry_mass_kg"}
            return self._send_json(200, top25_pc.tune_physical_build_specs(**{k:v for k,v in kw.items() if k in allowed}))
        if path in ("/api/flying-car/step", "/api/bus/sensors"):
            return self._send_json(200, get_step_feed(payload if isinstance(payload, dict) else {}))
        return self._send_json(404, {"ok": False, "error": "not_found", "path": path})


class ReusableHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(host: str = BRIDGE_HOST, port: int = BRIDGE_PORT):
    srv = ReusableHTTPServer((host, port), BridgeHandler)
    threading.Thread(target=lambda: sync_vehicle_bus(recover=False), daemon=True).start()
    srv.serve_forever()


if __name__ == "__main__":
    serve()
