#!/usr/bin/env python3
"""
SalathanieAI — Twin Flight Telemetry & Formation Node (:8152)
"""
import http.server
import json
import time

PORT = 8152
STATE = {
    "ok": True,
    "system": "SALATHANIE_TWIN_FLIGHT",
    "port": PORT,
    "mode": "DUAL_CRAFT_SYNC",
    "craft_a": {"id": "ASTR-01", "role": "LEAD_VECTOR", "alt_m": 120, "speed_kts": 145},
    "craft_b": {"id": "SZR-PLUS", "role": "WING_EVTOL", "alt_m": 120, "speed_kts": 145},
}



def _persistence_summary() -> dict:
    from pathlib import Path
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
            size_b = c.stat().st_size if exists else 0
            items.append({"path": str(c), "exists": exists, "bytes": size_b})
        except Exception as e:
            items.append({"path": str(c), "exists": False, "error": str(e)[:80]})
    return {"ok": True, "system": "SALATHANIE_TWIN_FLIGHT", "sources": items}


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

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p == "/api/twin-flight/persistence":
            return self._send(200, _persistence_summary())
        if p in ("/", "/health", "/api/twin-flight/state"):
            return self._send(200, {**STATE, "ts": int(time.time())})
        return self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        p = (self.path or "/").split("?", 1)[0]
        ln = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(ln) if ln > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            data = {}
        if p == "/api/twin-flight/update":
            STATE["mode"] = str(data.get("mode") or STATE["mode"])
            if "alt_m" in data:
                STATE["craft_a"]["alt_m"] = data["alt_m"]
                STATE["craft_b"]["alt_m"] = data["alt_m"]
            if "speed_kts" in data:
                STATE["craft_a"]["speed_kts"] = data["speed_kts"]
                STATE["craft_b"]["speed_kts"] = data["speed_kts"]
            return self._send(200, {**STATE, "ts": int(time.time())})
        return self._send(404, {"ok": False, "error": "not_found"})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
