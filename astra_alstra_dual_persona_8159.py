#!/usr/bin/env python3
"""
Port 8159: Dual-Persona AI Router & Locked Telemetry Core
- ASTRA (Female Avatar): Real-time Edge & Sovereign Cluster Orchestrator
- ALSTRA (Male Half-Human/Half-Robot Avatar): Deep Supercomputer Training & Telemetry Engine
"""
import http.server
import json
import socketserver
import time
import urllib.request

PORT = 8159
START_TS = time.time()

PERSONAS = {
    "astra": {
        "name": "ASTRA",
        "avatar_type": "female_sovereign_ai",
        "role": "Real-Time Edge Execution & Self-Healing Orchestrator",
        "latency_tier": "sub-5ms_local",
        "locked_ports": [8090, 8134, 8135, 3000],
        "status": "LOCKED_ACTIVE",
    },
    "alstra": {
        "name": "ALSTRA",
        "avatar_type": "male_half_human_half_robot_cybernetic",
        "role": "Deep Supercomputer Training, Multi-Node Telemetry & Strategic Core",
        "latency_tier": "deep_compute_fabric",
        "locked_ports": [8088, 8136, 8138, 8159],
        "status": "LOCKED_ACTIVE",
    },
}

class ReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_): pass

    def _send(self, code, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        p = self.path.split("?")[0]
        up_sec = round(time.time() - START_TS, 1)
        if p in ("/", "/telemetry", "/v1/persona/telemetry"):
            self._send(200, {
                "ok": True,
                "port": PORT,
                "service": "dual-persona-ai-router",
                "uptime_s": up_sec,
                "telemetry_lock": "ENFORCED_PERSISTENT",
                "active_personas": PERSONAS,
            })
        elif p == "/astra":
            self._send(200, {"ok": True, "selected": PERSONAS["astra"], "uptime_s": up_sec})
        elif p == "/alstra":
            self._send(200, {"ok": True, "selected": PERSONAS["alstra"], "uptime_s": up_sec})
        else:
            self._send(404, {"ok": False, "error": "unknown_route"})

    def do_POST(self):
        clen = int(self.headers.get("Content-Length", "0") or "0")
        body = json.loads(self.rfile.read(clen).decode("utf-8")) if clen > 0 else {}
        prompt = str(body.get("prompt", "")).lower()
        target = "alstra" if any(k in prompt for k in ("train", "supercomputer", "deep", "telemetry", "analyze", "alstra", "architecture")) else "astra"
        self._send(200, {
            "ok": True,
            "routed_to": PERSONAS[target]["name"],
            "avatar_type": PERSONAS[target]["avatar_type"],
            "role": PERSONAS[target]["role"],
            "telemetry_lock": "ENFORCED",
        })

if __name__ == "__main__":
    with ReuseTCP(("0.0.0.0", PORT), Handler) as s:
        print(f"[✔] Dual-Persona Router (ASTRA + ALSTRA) locked on port {PORT}")
        s.serve_forever()
