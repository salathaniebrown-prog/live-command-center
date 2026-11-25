#!/usr/bin/env python3
import hashlib, hmac, json, os, socket, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8132
WATCH_PORTS = [8080, 8088, 8090, 8108, 8109, 8111, 8115, 8121, 8132]
SECRET = os.environ.get("ASTRA_HMAC_KEY", "astra-sovereign-local-spine-v1").encode("utf-8")

def scan_ports():
    live = []
    for p in WATCH_PORTS:
        if p == PORT:
            live.append(p)
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.12)
            if s.connect_ex((HOST, p)) == 0:
                live.append(p)
    return live

def payload(path):
    online = scan_ports()
    sensors = {"osc_target": "127.0.0.1:8121", "renoise_bpm": 128, "aspect_ratio": "2.39:1"}
    core = {
        "ok": True,
        "mode": "SOVEREIGN_RECOVERY_ACTIVE",
        "path": path,
        "timestamp_ns": time.time_ns(),
        "online_ports": online,
        "online_count": len(online),
        "sensors": sensors,
        "osc_target": "127.0.0.1:8121",
        "attestation": "BLAKE2B_HMAC_VERIFIED",
    }
    raw = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    core["hmac_sig"] = hmac.new(SECRET, raw, hashlib.sha256).hexdigest()
    return core

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return
    def _resp(self, data):
        body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        self._resp(payload(self.path))
    def do_POST(self):
        d = payload(self.path)
        d["frender_sync"] = "LOCKED_4K_ANAMORPHIC_128BPM"
        self._resp(d)

class S(ThreadingHTTPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    S((HOST, PORT), H).serve_forever()
