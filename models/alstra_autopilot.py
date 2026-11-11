import http.server
import socketserver
import sqlite3
import json
import os
import sys
import time

PORT = 8080
DB_PATH = os.path.expanduser("~/astra_deepspace_ledger.db")

class AlstraAutopilotHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == "/api/status":
                response_data = {
                    "status": "ONLINE",
                    "pilot": "Alstra Self-Pilot",
                    "operator": "Salathaniel Brown Sr.",
                    "routing": "053100465",
                    "account": "8823901421",
                    "timestamp": time.time()
                }
                payload = json.dumps(response_data).encode("utf-8")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Astra-Pilot", "Autonomous-Active")
                self.end_headers()
                self.wfile.write(payload)
                
                self.log_to_ledger("AUTOPILOT_GET", response_data)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"404 - Endpoint Not Found")
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)

    def log_to_ledger(self, event_type, data):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS master_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    payload TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("INSERT INTO master_events (event_type, payload) VALUES (?, ?);", (event_type, json.dumps(data)))
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"[DB Error] {db_err}", file=sys.stderr)

    def log_message(self, format, *args):
        print(f"[ALSTRA-PILOT] {self.client_address[0]} - {format % args}")

if __name__ == "__main__":
    print(f"[✔] Alstra Self-Pilot initializing on port {PORT}...")
    try:
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", PORT), AlstraAutopilotHandler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        print(f"[CRITICAL] Server crashed: {e}")
        sys.exit(1)
