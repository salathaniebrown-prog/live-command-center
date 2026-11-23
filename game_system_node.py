#!/usr/bin/env python3
"""
Astra + Alstra // New Game System Session, Leaderboard & Self-Healing Node (:8150)
"""
import http.server
import json
import time

PORT = 8150
RAM_CEILING = 83.0

STATE = {
    "ok": True,
    "system": "SALATHANIE_NEW_GAME_SYSTEM",
    "port": PORT,
    "mode": "STANDBY_READY",
    "telemetry_health": "NOMINAL",
    "heal_count": 0,
    "last_heal_reason": None,
    "active_sessions": 0,
    "rounds_completed": 0,
    "score": 0,
    "level": 1,
    "leaderboard": [
        {"pilot": "ASTR-01", "track": "TRIAD_SKYWAY", "score": 1250, "level": 3},
        {"pilot": "SZR-PLUS", "track": "EVTOL_VECTOR", "score": 980, "level": 2},
    ],
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
        if p == "/api/game/leaderboard":
            ranked = sorted(STATE["leaderboard"], key=lambda x: x.get("score", 0), reverse=True)
            return self._send(200, {"ok": True, "system": STATE["system"], "leaderboard": ranked, "ts": int(time.time())})
        if p in ("/", "/health", "/api/game/state"):
            return self._send(200, {**STATE, "ram_used_pct": _ram_used_pct(), "ts": int(time.time())})
        return self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        p = (self.path or "/").split("?", 1)[0]
        data = self._read_json()
        if p == "/api/game/session":
            STATE["mode"] = str(data.get("mode") or "ACTIVE_SIM")
            STATE["active_sessions"] = int(data.get("sessions", STATE["active_sessions"] + 1))
            STATE["level"] = int(data.get("level", STATE["level"]))
            STATE["score"] += int(data.get("points", 100))
            return self._send(200, {**STATE, "ts": int(time.time())})
        if p == "/api/game/round":
            pts = int(data.get("points", 250))
            pilot = str(data.get("pilot") or "SALATHANIE-01")
            track = str(data.get("track") or "TWIN_FLIGHT_ARCADE")
            STATE["rounds_completed"] += 1
            STATE["score"] += pts
            STATE["level"] = max(STATE["level"], 1 + (STATE["score"] // 500))
            STATE["mode"] = "ROUND_COMPLETE"
            STATE["leaderboard"].append({"pilot": pilot, "track": track, "score": STATE["score"], "level": STATE["level"]})
            return self._send(200, {**STATE, "ts": int(time.time())})
        if p == "/api/game/heal":
            ram = _ram_used_pct()
            STATE["heal_count"] += 1
            STATE["last_heal_reason"] = str(data.get("reason") or "game_telemetry_self_heal")
            STATE["telemetry_health"] = "RAM_GUARD_THROTTLED" if ram >= RAM_CEILING else "SELF_HEALED_NOMINAL"
            if STATE["mode"] == "ERROR_STATE":
                STATE["mode"] = "STANDBY_READY"
            return self._send(200, {**STATE, "ram_used_pct": ram, "ts": int(time.time())})
        return self._send(404, {"ok": False, "error": "not_found"})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
