#!/usr/bin/env python3
import os, json, time, sqlite3, shutil
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = os.path.expanduser("~/astra_telemetry.db")
ALERT_THRESHOLDS = {"max_load_avg": 3.5, "min_disk_free_gb": 5.0}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            event_type TEXT,
            payload TEXT
        )
    """)
    conn.commit()
    conn.close()

def evaluate_thresholds(metrics: dict) -> list:
    alerts = []
    load_avg = metrics["system"]["load_avg"][0]
    disk_free = metrics["system"]["disk_free_gb"]
    if load_avg > ALERT_THRESHOLDS["max_load_avg"]:
        alerts.append({
            "severity": "WARNING",
            "metric": "load_avg",
            "value": load_avg,
            "threshold": ALERT_THRESHOLDS["max_load_avg"],
            "message": f"Load average {load_avg} exceeded threshold."
        })
    if disk_free < ALERT_THRESHOLDS["min_disk_free_gb"]:
        alerts.append({
            "severity": "CRITICAL",
            "metric": "disk_free_gb",
            "value": disk_free,
            "threshold": ALERT_THRESHOLDS["min_disk_free_gb"],
            "message": f"Free disk space {disk_free}GB fell below threshold."
        })
    return alerts

class TelemetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/telemetry/status":
            try:
                total, used, free = shutil.disk_usage("/")
                load1, load5, load15 = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
                metrics = {
                    "status": "ONLINE",
                    "assistant": "Astra Python Telemetry",
                    "system": {
                        "load_avg": [load1, load5, load15],
                        "disk_free_gb": round(free / (2**30), 2),
                        "wal_status": "INTACT"
                    }
                }
                triggered = evaluate_thresholds(metrics)
                if triggered:
                    conn = sqlite3.connect(DB_PATH)
                    for alert in triggered:
                        conn.execute("INSERT INTO telemetry_logs (timestamp, event_type, payload) VALUES (?, ?, ?)",
                                     (time.time(), f"ALERT_{alert['severity']}", json.dumps(alert)))
                    conn.commit()
                    conn.close()
                metrics["alerts"] = triggered
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(metrics, indent=2).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/telemetry/log":
            ln = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(ln) if ln > 0 else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO telemetry_logs (timestamp, event_type, payload) VALUES (?, ?, ?)",
                             (time.time(), body.get("event_type", "INFO"), json.dumps(body)))
                conn.commit()
                conn.close()
                res = {"status": "LOGGED", "received": body}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode())
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        self.send_response(404)
        self.end_headers()

def run(server_class=HTTPServer, handler_class=TelemetryHandler, port=8110):
    init_db()
    server_address = ('127.0.0.1', port)
    httpd = server_class(server_address, handler_class)
    print(f"[OK] Python Telemetry Assistant running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
