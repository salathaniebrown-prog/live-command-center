#!/usr/bin/env python3
"""
Astra + Alstra // Twin Flight Telemetry, Formation & Self-Healing Node (:8152)
"""
import http.server
import json
import socket
import time
from pathlib import Path

PORT = 8152
RAM_CEILING = 83.0
CORE_PORTS = [8090, 8095, 8099, 8101, 8102, 8125, 8132, 8140, 8150, 8152]

STATE = {
    "ok": True,
    "system": "SALATHANIE_TWIN_FLIGHT",
    "port": PORT,
    "mode": "DUAL_CRAFT_SYNC",
    "formation": "ECHELON_RIGHT",
    "separation_m": 45.0,
    "telemetry_health": "NOMINAL",
    "heal_count": 0,
    "last_heal_reason": None,
    "craft_a": {"id": "ASTR-01", "role": "LEAD_VECTOR", "alt_m": 120, "speed_kts": 145, "bus_v": 640},
    "craft_b": {"id": "SZR-PLUS", "role": "WING_EVTOL", "alt_m": 120, "speed_kts": 145, "bus_v": 638},
}


def _ram_used_pct() -> float:
    total_kb = 0
    avail_kb = 0
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for ln in f:
                if ln.startswith("MemTotal:"):
                    total_kb = int(ln.split()[1])
                elif ln.startswith("MemAvailable:"):
                    avail_kb = int(ln.split()[1])
    except Exception:
        return 0.0
    return round(((total_kb - avail_kb) / total_kb) * 100.0, 1) if total_kb > 0 else 0.0


def _open_ports() -> list[int]:
    live = []
    for p in CORE_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.25)
            if s.connect_ex(("127.0.0.1", p)) == 0:
                live.append(p)
    return live


def _persistence_summary() -> dict:
    home = Path.home()
    repo = home / "live-command-center"
    candidates = [
        home / "persistent_twin_state.db",
        home / ".astra_golden_backup/persistent_twin_state.db.golden",
        repo / "astra_flight_ledger.db",
        repo / "alstra_flight_ledger.db",
    ]
    items = []
    for c in candidates:
        try:
            exists = c.exists()
            items.append({"path": str(c), "exists": exists, "bytes": c.stat().st_size if exists else 0})
        except Exception as e:
            items.append({"path": str(c), "exists": False, "error": str(e)[:80]})
    return {"ok": True, "system": "SALATHANIE_TWIN_FLIGHT", "sources": items}


def _engineering_telemetry() -> dict:
    ram = _ram_used_pct()
    ports = _open_ports()
    return {
        "ok": True,
        "system": "SALATHANIE_TWIN_FLIGHT",
        "ram_used_pct": ram,
        "ram_ceiling_pct": RAM_CEILING,
        "ram_guard_ok": ram < RAM_CEILING,
        "open_ports": ports,
        "open_port_count": len(ports),
        "telemetry_health": STATE["telemetry_health"],
        "heal_count": STATE["heal_count"],
        "last_heal_reason": STATE["last_heal_reason"],
    }


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        ln = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(ln) if ln > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p == "/api/twin-flight/persistence":
            return self._send(200, _persistence_summary())
        if p == "/api/twin-flight/telemetry":
            return self._send(200, _engineering_telemetry())
        if p in ("/", "/health", "/api/twin-flight/state"):
            return self._send(200, {**STATE, "telemetry": _engineering_telemetry(), "ts": int(time.time())})
        return self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        p = (self.path or "/").split("?", 1)[0]
        data = self._read_json()
        if p == "/api/twin-flight/update":
            STATE["mode"] = str(data.get("mode") or STATE["mode"])
            if "alt_m" in data:
                STATE["craft_a"]["alt_m"] = data["alt_m"]
                STATE["craft_b"]["alt_m"] = data["alt_m"]
            if "speed_kts" in data:
                STATE["craft_a"]["speed_kts"] = data["speed_kts"]
                STATE["craft_b"]["speed_kts"] = data["speed_kts"]
            return self._send(200, {**STATE, "ts": int(time.time())})
        if p == "/api/twin-flight/formation":
            STATE["formation"] = str(data.get("formation") or STATE["formation"])
            STATE["separation_m"] = float(data.get("separation_m", STATE["separation_m"]))
            STATE["mode"] = str(data.get("mode") or "FORMATION_LOCK")
            return self._send(200, {**STATE, "ts": int(time.time())})
        if p == "/api/twin-flight/heal":
            ram = _ram_used_pct()
            STATE["heal_count"] += 1
            STATE["last_heal_reason"] = str(data.get("reason") or "telemetry_self_heal")
            STATE["telemetry_health"] = "RAM_GUARD_THROTTLED" if ram >= RAM_CEILING else "SELF_HEALED_NOMINAL"
            return self._send(200, {**STATE, "telemetry": _engineering_telemetry(), "ts": int(time.time())})
        return self._send(404, {"ok": False, "error": "not_found"})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
