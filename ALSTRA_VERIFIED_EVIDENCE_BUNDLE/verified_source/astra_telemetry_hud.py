#!/usr/bin/env python3
"""
Astra Sovereign OS - Additive HUD Telemetry & Port Health Monitor (Port 8088 Extension)
Runs concurrently without modifying underlying SQLite WAL databases or existing endpoints.
"""

import http.server
import json
import socket
import urllib.parse

PORT = 8088
TARGETS = {
    8088: "Unified Command Center HUD",
    8095: "Alstra Legal & Crypto Asset Shield",
    8096: "45M-Token Knowledge Graph & FTS5",
    8097: "Infinite Brain OODA Loop & SOP",
    8098: "Business Superintelligence SQL Warehouse",
    8099: "Wyler & Dealerslink Crypto Dealership",
    8100: "177B 8-GPU Sparse Model Nexus",
    8101: "Glass-Box Gemma 4 / LiteRT-LM / RAG",
    8102: "24h SQLite Backup & Watchdog",
    8103: "Predictive Location & Triad Optimizer",
    8104: "World Web & Tor OSINT Harvester",
    8105: "Electron/Node Re-Engineering Engine",
    8106: "Enterprise Governance & GDPR/SOC2",
    8107: "AI SEO, GEO & Franchise Cloner",
    8108: "One-Prompt Multi-Model Studio Pro",
    8109: "Auto-Astra Cluster & Compute Router",
    9050: "Tor SOCKS5 Encrypted Mesh Proxy"
}

def check_port(p):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(('127.0.0.1', p)) == 0

class HUDHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/hud/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "node": "Termux-Android / Piedmont Triad (36.0726, -79.7920)",
                "services": {p: {"name": name, "online": check_port(p)} for p, name in TARGETS.items()}
            }
            self.wfile.write(json.dumps(data, indent=2).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<!DOCTYPE html>
            <html><head><title>Astra Sovereign HUD</title>
            <style>body{background:#090d16;color:#00ffcc;font-family:monospace;padding:2rem;}
            .card{background:#111827;border:1px solid #1f2937;padding:1rem;margin-bottom:1rem;border-radius:6px;}
            a{color:#ff0077;text-decoration:none;}</style></head>
            <body>
              <h1>ASTRA SOVEREIGN OS // LIVE HUD EXTENSION</h1>
              <p>Additive Microservice HUD running on Port 8088.</p>
              <div class="card"><a href="/api/hud/status">[Query Live Port Health JSON]</a></div>
            </body></html>""")

    def log_message(self, fmt, *args):
        pass

if __name__ == "__main__":
    srv = http.server.HTTPServer(("0.0.0.0", PORT), HUDHandler)
    print(f"[ASTRA] HUD telemetry extension active on port {PORT}")
    srv.serve_forever()
