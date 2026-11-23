#!/usr/bin/env python3
"""
Astra + Alstra = SalathanieAI
Elite Avatar & Flying Car / EV Cognitive Cortex (:8156)
"""
import hashlib
import http.client
import http.server
import json
import os
import sqlite3
import time
import uuid

PORT = 8156
RAM_CEILING = 83.0
HOME = os.path.expanduser("~")
CORTEX_DB = os.path.join(HOME, "live-command-center", "elite_brain_cortex.db")

AVATAR_COUNCIL = {
    "ASTRA": {
        "role": "SOVEREIGN_FLIGHT_COMMANDER",
        "focus": "3D airspace vectoring, HUD threat synthesis, and pilot tactical clarity",
    },
    "ALSTRA": {
        "role": "DEEP_TELEMETRY_ENGINEER",
        "focus": "800V HV bus balancing, multi-rotor thermal margins, and ledger integrity",
    },
    "SALATHANIE": {
        "role": "EXECUTIVE_SYSTEM_ARCHITECT",
        "focus": "Autonomous mission optimization, self-healing governance, and predictive compute",
    },
}


def get_db():
    conn = sqlite3.connect(CORTEX_DB, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_cortex():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS cognitive_decisions (
        decision_id TEXT PRIMARY KEY,
        domain TEXT,
        intent TEXT,
        ev_mode TEXT,
        ram_pct REAL,
        council_json TEXT,
        attestation_hash TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()


init_cortex()


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


def _probe_json(port: int, path: str, timeout: float = 0.8) -> dict:
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        c.request("GET", path)
        r = c.getresponse()
        if r.status == 200:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception:
        pass
    return {}


def synthesize_elite_directive(payload: dict) -> dict:
    intent = str(payload.get("intent") or payload.get("prompt") or "OPTIMIZE_FLIGHT_AND_AVATAR_SYNC").strip()
    domain = str(payload.get("domain") or "UNIFIED_AVATAR_EV").upper()
    bus_v = float(payload.get("bus_v", 760.0))
    soc_pct = float(payload.get("soc_pct", 88.0))
    alt_m = float(payload.get("alt_m", 150.0))
    speed_kts = float(payload.get("speed_kts", 145.0))
    ram_pct = _ram_used_pct()

    twin_live = _probe_json(8152, "/api/twin-flight/state")
    gw_live = _probe_json(8090, "/api/flying-car/step")

    if bus_v < 520.0 or soc_pct < 20.0:
        ev_mode = "ENERGY_CONSERVATION_GLIDE"
        action = "Throttle auxiliary loads, lock eco-pitch vector, route to nearest vertiport"
    elif speed_kts > 180.0 or alt_m > 400.0:
        ev_mode = "HIGH_VELOCITY_AERO_TRIM"
        action = "Engage active rotor-wing stabilization, tighten twin-flight formation spacing to 35m"
    else:
        ev_mode = "ADAPTIVE_HYBRID_CRUISE"
        action = "Maintain balanced 800V bus draw, synchronize Tri-Avatar HUD telemetry at 60Hz"

    council_output = {
        "ASTRA": {
            "persona": "ASTRA // Flight Commander",
            "directive": f"Airspace corridor locked at {alt_m:.0f}m / {speed_kts:.0f} kts. {action}.",
        },
        "ALSTRA": {
            "persona": "ALSTRA // Powertrain & Telemetry",
            "directive": f"HV Bus {bus_v:.1f}V ({soc_pct:.1f}% SOC) nominal; Twin-Flight link={'ONLINE' if twin_live else 'STANDBY'}; Gateway={'ONLINE' if gw_live else 'STANDBY'}.",
        },
        "SALATHANIE": {
            "persona": "SALATHANIE // Sovereign Architect",
            "directive": f"Execution mode {ev_mode} verified under {ram_pct:.1f}% RAM ceiling ({'GUARD_OK' if ram_pct < RAM_CEILING else 'RAM_THROTTLED'}). Intent: {intent}",
        },
    }

    dec_id = "CORTEX-" + uuid.uuid4().hex[:8].upper()
    ts = time.time()
    attestation = "0x" + hashlib.sha256(f"{dec_id}|{domain}|{ev_mode}|{bus_v}|{ts}".encode("utf-8")).hexdigest()

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO cognitive_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (dec_id, domain, intent, ev_mode, ram_pct, json.dumps(council_output), attestation, ts),
    )
    total_decisions = conn.execute("SELECT COUNT(*) FROM cognitive_decisions").fetchone()[0]
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "system": "SALATHANIE_ELITE_AVATAR_EV_BRAIN",
        "port": PORT,
        "decision_id": dec_id,
        "domain": domain,
        "ev_flight_profile": {
            "mode": ev_mode,
            "bus_v": bus_v,
            "soc_pct": soc_pct,
            "alt_m": alt_m,
            "speed_kts": speed_kts,
        },
        "tri_avatar_council": council_output,
        "cortex_memory_entries": total_decisions,
        "ram_used_pct": ram_pct,
        "attestation_hash": attestation,
        "ts": int(ts),
    }


class EliteBrainHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_json(self) -> dict:
        ln = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(ln) if ln > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p == "/api/brain/history":
            conn = get_db()
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(
                "SELECT decision_id, domain, intent, ev_mode, ram_pct, attestation_hash, timestamp FROM cognitive_decisions ORDER BY timestamp DESC LIMIT 10"
            ).fetchall()]
            conn.close()
            return self._send(200, {"ok": True, "system": "SALATHANIE_ELITE_AVATAR_EV_BRAIN", "history": rows})
        if p in ("/", "/health", "/api/brain/state"):
            conn = get_db()
            count = conn.execute("SELECT COUNT(*) FROM cognitive_decisions").fetchone()[0]
            conn.close()
            return self._send(200, {
                "ok": True,
                "system": "SALATHANIE_ELITE_AVATAR_EV_BRAIN",
                "port": PORT,
                "status": "SOVEREIGN_COGNITION_ONLINE",
                "avatars_active": list(AVATAR_COUNCIL.keys()),
                "cortex_memory_entries": count,
                "ram_used_pct": _ram_used_pct(),
                "ts": int(time.time()),
            })
        return self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        p = (self.path or "/").split("?", 1)[0]
        data = self._read_json()
        if p in ("/api/brain/think", "/api/brain/ev-optimize", "/api/brain/avatar-directive"):
            return self._send(200, synthesize_elite_directive(data))
        return self._send(404, {"ok": False, "error": "not_found"})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), EliteBrainHandler).serve_forever()
