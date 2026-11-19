#!/usr/bin/env python3
import http.server, json, socketserver, subprocess, time
from pathlib import Path

PORT = 8141

class ReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_):
        pass
    def do_GET(self):
        try:
            head = subprocess.check_output(["git", "-C", str(Path.home()), "rev-parse", "--short", "HEAD"], text=True, timeout=2).strip()
        except Exception:
            head = "main"
        raw = json.dumps({"ok": True, "status": "ONLINE", "port": PORT, "git_head": head, "ts": time.time()}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

if __name__ == "__main__":
    with ReuseTCP(("0.0.0.0", PORT), H) as s:
        s.serve_forever()
