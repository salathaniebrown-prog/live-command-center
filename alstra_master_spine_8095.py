#!/usr/bin/env python3
"""
Alstra Primary Control Plane: Termux Master Spine (127.0.0.1:8095)
- Dynamic Worker Registry (POST /v1/register)
- Thermal & Load-Aware Execution Router (POST /v1/execute)
- Hardware & Thermal Telemetry (GET / & GET /v1/telemetry)
"""
import json
import os
import subprocess
import time
import urllib.request
import uuid
import http.server
import socketserver

PORT = 8095
WORKERS = {}

def read_thermal_and_load():
    load_1m = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.5
    cpu_cores = os.cpu_count() or 4
    temp_c = 36.5
    batt_pct = 100
    try:
        out = subprocess.check_output(["termux-battery-status"], timeout=2).decode("utf-8")
        b = json.loads(out)
        temp_c = float(b.get("temperature", 36.5))
        batt_pct = int(b.get("percentage", 100))
    except Exception:
        pass
    safe = (temp_c <= 42.0) and (load_1m <= 2.5)
    return {
        "cpu_cores": cpu_cores,
        "load_1m": round(load_1m, 2),
        "temperature_c": temp_c,
        "battery_pct": batt_pct,
        "thermal_safe": safe
    }

class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True

class SpineHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"spine8095-{uuid.uuid4().hex[:12]}")
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        hw = read_thermal_and_load()
        return self._send({
            "ok": True,
            "status": "ONLINE",
            "port": PORT,
            "service": "ALSTRA_TERMUX_MASTER_SPINE",
            "registered_workers": WORKERS,
            "worker_count": len(WORKERS),
            "hardware": hw,
            "timestamp": time.time()
        })

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if path == "/v1/register":
            name = str(body.get("node_name", "")).strip()
            url = str(body.get("endpoint_url", "")).strip()
            if not name or not url:
                return self._send({"ok": False, "error": "node_name and endpoint_url required"}, 400)
            WORKERS[name] = {"endpoint_url": url, "registered_at": time.time()}
            return self._send({"ok": True, "status": "REGISTERED", "node_name": name, "workers": WORKERS})

        if path == "/v1/execute":
            hw = read_thermal_and_load()
            target = body.get("target_node", "auto")
            # Offload to registered worker if thermally throttled or explicitly requested
            if (target != "termux-main" and not hw["thermal_safe"] and WORKERS) or (target in WORKERS):
                w_name = target if target in WORKERS else next(iter(WORKERS))
                w_url = WORKERS[w_name]["endpoint_url"].rstrip("/") + "/v1/execute"
                req = urllib.request.Request(
                    w_url, data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    res["routed_to"] = w_name
                    return self._send(res)

            # Execute locally via Genius Brain (8099) so AST validation + WAL ledger logging always apply
            req = urllib.request.Request(
                "http://127.0.0.1:8099/v1/execute",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                res["routed_to"] = "termux-main"
                res["hardware"] = hw
                return self._send(res)

        return self._send({"ok": False, "error": f"Unknown POST path: {path}"}, 404)

if __name__ == "__main__":
    with ReuseTCP(("127.0.0.1", PORT), SpineHandler) as srv:
        print(f"[✔] Alstra Termux Master Spine active on 127.0.0.1:{PORT}")
        srv.serve_forever()
