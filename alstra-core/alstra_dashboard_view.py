#!/usr/bin/env python3
"""
Alstra Sovereign Centralized Web Dashboard (Python 3.13 Thread-Safe Optimized)
"""

import os
import sqlite3
import html
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_PATH = os.path.expanduser("~/alstra-core/alstra_core.db")
HOST = "0.0.0.0"
PORT = 8100

class SystemHardwareProfiler:
    @staticmethod
    def get_cpu_usage_pct() -> float:
        return 12.4
    @staticmethod
    def get_ram_usage_metrics() -> tuple:
        return 41.5, 3.2, 8.0

class DashboardViewHandler(BaseHTTPRequestHandler):
    def _fetch_cluster_nodes(self) -> list:
        default_nodes = {
            "NODE-01": {"name": "NODE-01 (Primary)", "type": "Termux Core", "status": "status-online", "latency": "0ms"},
            "NODE-02": {"name": "NODE-02 (Quant)", "type": "Arbitrage Lab", "status": "status-offline", "latency": "0ms"},
            "NODE-03": {"name": "NODE-03 (Edge)", "type": "Handshake Gate", "status": "status-offline", "latency": "0ms"},
        }
        if not os.path.exists(DB_PATH): return list(default_nodes.values())
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT node_id, node_type, status, latency, last_seen FROM node_cluster_states")
            rows = cursor.fetchall()
            conn.close()
            current_time = time.time()
            for r_id, r_type, r_status, r_lat, r_seen in rows:
                try:
                    struct_time = time.strptime(r_seen, "%Y-%m-%dT%H:%M:%SZ")
                    if current_time - (time.mktime(struct_time) - time.timezone) > 45: 
                        r_status = "status-offline"
                except Exception: pass
                default_nodes[r_id] = {"name": r_id, "type": r_type, "status": r_status, "latency": r_lat}
        except Exception: pass
        return list(default_nodes.values())

    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        nodes = self._fetch_cluster_nodes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        
        # Build layout directly into the safe stream
        from alstra_dashboard_view import DashboardTemplateEngine
        html_out = DashboardTemplateEngine.get_header()
        html_out += '<div class="cluster-grid">'
        for n in nodes:
            html_out += f"""
                <div class="node-card">
                    <div class="node-info">
                        <span class="node-name">{html.escape(n['name'])}</span>
                        <span class="node-meta">{html.escape(n['type'])} • ping: {html.escape(n['latency'])}</span>
                    </div>
                    <div class="node-status-dot {n['status']}"></div>
                </div>
            """
        html_out += "</div>" + DashboardTemplateEngine.get_footer()
        self.wfile.write(html_out.encode("utf-8"))

    def log_message(self, format, *args): return

def launch_dashboard():
    server = HTTPServer((HOST, PORT), DashboardViewHandler)
    print(f"[⚡] Centralized Visualization Interface online at -> http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    launch_dashboard()
