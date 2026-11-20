import sqlite3, json, subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_PATH = "/data/data/com.termux/files/home/astra_state.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS streams (stream TEXT, key TEXT, value TEXT, writes INTEGER, PRIMARY KEY (stream, key))")
    conn.commit()
    conn.close()

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class ThreeStreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        parts = [p for p in self.path.strip("/").split("/") if p]
        stream = parts[0] if len(parts) > 0 else "dashboard"
        key = parts[1] if len(parts) > 1 else "status"

        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT value, writes FROM streams WHERE stream=? AND key=?", (stream, key)).fetchone()
        conn.close()
        val = json.loads(row[0]) if row else None
        cnt = row[1] if row else 0
        self._send(200, {"stream": stream, "key": key, "data": val, "writes": cnt})

    def do_POST(self):
        parts = [p for p in self.path.strip("/").split("/") if p]
        stream = parts[0] if len(parts) > 0 else "dashboard"
        key = parts[1] if len(parts) > 1 else "status"
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode() if length > 0 else "{}"
        payload = json.loads(raw or "{}")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT writes FROM streams WHERE stream=? AND key=?", (stream, key)).fetchone()
        writes = (cur[0] + 1) if cur else 1
        conn.execute("REPLACE INTO streams (stream, key, value, writes) VALUES (?, ?, ?, ?)", (stream, key, json.dumps(payload), writes))
        conn.commit()
        conn.close()

        if stream == "github" and payload.get("action") == "sync":
            subprocess.Popen(["git", "-C", "/data/data/com.termux/files/home/live-command-center", "status", "-s"])

        self._send(200, {"status": "committed", "stream": stream, "key": key, "writes": writes})

if __name__ == "__main__":
    init_db()
    ReusableHTTPServer(("127.0.0.1", 8105), ThreeStreamHandler).serve_forever()
