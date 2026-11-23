#!/usr/bin/env python3
"""
SalathanieAI — New Game System Telemetry & Session Node (:8150)
"""
import http.server
import json
import time

PORT = 8150
STATE = {
    "ok": True,
    "system": "SALATHANIE_NEW_GAME_SYSTEM",
    "port": PORT,
    "mode": "STANDBY_READY",
    "active_sessions": 0,
    "score": 0,
    "level": 1,
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

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p in ("/", "/health", "/api/game/state"):
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
        if p == "/api/game/session":
            STATE["mode"] = str(data.get("mode") or "ACTIVE_SIM")
            STATE["active_sessions"] = int(data.get("sessions", STATE["active_sessions"] + 1))
            STATE["level"] = int(data.get("level", STATE["level"]))
            STATE["score"] += int(data.get("points", 100))
            return self._send(200, {**STATE, "ts": int(time.time())})
        return self._send(404, {"ok": False, "error": "not_found"})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
