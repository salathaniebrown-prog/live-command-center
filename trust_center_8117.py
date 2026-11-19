#!/usr/bin/env python3
import http.server
import json
import os
import socketserver
import time
import uuid

PORT = int(os.environ.get("ALSTRA_SHADOW_PORT", "8117"))

class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True

class TrustCenterHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _reply(self):
        payload = {
            "ok": True,
            "status": "ONLINE",
            "trust_center": "ONLINE",
            "service": "TRUST_CENTER_8117",
            "port": PORT,
            "query_id": f"trust8117-{uuid.uuid4().hex[:12]}",
            "timestamp": time.time(),
        }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._reply()

    def do_GET(self):
        self._reply()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            self.rfile.read(length)
        self._reply()

if __name__ == "__main__":
    with ReuseTCP(("127.0.0.1", PORT), TrustCenterHandler) as srv:
        srv.serve_forever()
