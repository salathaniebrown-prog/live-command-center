#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORT = 8112
DB_PATH = os.path.expanduser("~/astra-enterprise-core/alstra_stream_ledger.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS stream_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            platform TEXT NOT NULL,
            event_type TEXT NOT NULL,
            username TEXT,
            payload TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_event(platform, event_type, username="system", payload=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO stream_events (ts, platform, event_type, username, payload) VALUES (?, ?, ?, ?, ?)",
        (time.time(), platform, event_type, username, payload)
    )
    conn.commit()
    conn.close()

def launch_android_intent(url):
    try:
        res = subprocess.run(
            ["am", "start", "-a", "android.intent.action.VIEW", "-d", url],
            capture_output=True, text=True, timeout=4
        )
        return res.returncode == 0, (res.stdout or res.stderr).strip()
    except Exception as e:
        return False, str(e)

class DualStreamHandler(BaseHTTPRequestHandler):
    def _send_json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path.endswith("/status"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            total_events = c.execute("SELECT COUNT(*) FROM stream_events").fetchone()[0]
            twitch_count = c.execute("SELECT COUNT(*) FROM stream_events WHERE platform='twitch'").fetchone()[0]
            kick_count = c.execute("SELECT COUNT(*) FROM stream_events WHERE platform='kick'").fetchone()[0]
            recent = c.execute(
                "SELECT ts, platform, event_type, username, payload FROM stream_events ORDER BY id DESC LIMIT 12"
            ).fetchall()
            conn.close()
            self._send_json(200, {
                "service": "alstra-dual-stream-bridge",
                "port": PORT,
                "online": True,
                "metrics": {
                    "total_events": total_events,
                    "twitch_events": twitch_count,
                    "kick_events": kick_count
                },
                "recent_feed": [
                    {"ts": r[0], "platform": r[1], "type": r[2], "user": r[3], "msg": r[4]}
                    for r in recent
                ]
            })
        elif path.endswith("/telemetry"):
            # OBS Browser-Source lightweight JSON payload
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            cutoff = time.time() - 60
            msg_per_min = c.execute(
                "SELECT COUNT(*) FROM stream_events WHERE event_type='chat' AND ts > ?", (cutoff,)
            ).fetchone()[0]
            conn.close()
            self._send_json(200, {
                "obs_overlay": "READY",
                "chat_velocity_1m": msg_per_min,
                "bridge_uptime_ts": time.time()
            })
        else:
            self._send_json(404, {"error": "unknown_stream_route", "path": path})

    def do_POST(self):
        path = urlparse(self.path).path
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln).decode("utf-8") if ln > 0 else "{}"
        try:
            body = json.loads(raw)
        except Exception:
            body = {}

        if path.endswith("/launch"):
            kick_channel = body.get("kick_channel", "https://kick.com")
            twitch_channel = body.get("twitch_channel", "https://twitch.tv")
            k_ok, k_out = launch_android_intent(kick_channel)
            time.sleep(0.6)
            t_ok, t_out = launch_android_intent(twitch_channel)
            log_event("dual", "intent_launch", "operator", f"kick={k_ok}, twitch={t_ok}")
            self._send_json(200, {
                "launched": True,
                "kick": {"ok": k_ok, "detail": k_out, "target": kick_channel},
                "twitch": {"ok": t_ok, "detail": t_out, "target": twitch_channel}
            })
        elif path.endswith("/ingest"):
            platform = body.get("platform", "unknown").lower()
            event_type = body.get("event_type", "chat")
            username = body.get("username", "viewer")
            payload = body.get("message", "")
            log_event(platform, event_type, username, payload)
            self._send_json(200, {"ingested": True, "platform": platform})
        else:
            self._send_json(404, {"error": "unknown_post_route", "path": path})

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    init_db()
    log_event("system", "boot", "daemon", "Port 8112 Dual-Stream Bridge initialized")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), DualStreamHandler)
    print(f"[OK] Alstra Dual-Stream Bridge listening on 127.0.0.1:{PORT}")
    server.serve_forever()
