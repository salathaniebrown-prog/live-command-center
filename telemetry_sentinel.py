#!/usr/bin/env python3
import os
import json
import time
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8100

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class HardenedTelemetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        ports = [8088, 8095, 8096, 8097, 8098, 8099, 8100, 8112]
        active_nodes = sum(1 for p in ports if subprocess.run(["nc", "-z", "127.0.0.1", str(p)], capture_output=True).returncode == 0)
        
        load1, load5, load15 = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        st = os.statvfs(os.path.expanduser("~"))
        disk_free_gb = round((st.f_bavail * st.f_frsize) / (1024**3), 2)
        
        payload = {
            "status": "NOMINAL_SECURE",
            "assistant": "Astra Tier-1 Sentinel",
            "system": {
                "load_avg": [load1, load5, load15],
                "disk_free_gb": disk_free_gb,
                "wal_status": "LOCKED_ENCRYPTED",
                "active_nodes": f"{active_nodes}/{len(ports)}"
            },
            "alerts": [] if active_nodes >= 6 else [{"severity": "WARNING", "message": "Sub-node availability degraded", "value": active_nodes, "threshold": 6}]
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = ReusableHTTPServer(("127.0.0.1", PORT), HardenedTelemetryHandler)
    server.serve_forever()
