import json
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.environ.get("ASTRA_HOST", "127.0.0.1")
PORT = int(os.environ.get("ASTRA_SVC_8182_PORT", "8182"))
DB_PATH = os.environ.get(
    "ASTRA_SVC_8182_DB",
    os.path.expanduser("~/.local/share/astra/svc_8182.db"),
)

DB_LOCK = threading.Lock()


def init_db() -> None:
    parent = os.path.dirname(os.path.abspath(DB_PATH))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def log_event(kind: str, detail: str) -> int:
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000;")
            cur = conn.execute(
                "INSERT INTO events (ts, kind, detail) VALUES (?, ?, ?)",
                (int(time.time()), kind, detail),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def count_events() -> int:
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        try:
            row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()


def fetch_events(limit: int = 20) -> list[dict]:
    safe_limit = max(1, min(int(limit), 200))
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, ts, kind, detail FROM events ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "ts": int(r["ts"]),
                    "kind": str(r["kind"]),
                    "detail": str(r["detail"]),
                }
                for r in rows
            ]
        finally:
            conn.close()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/health", "/"):
            event_id = log_event("health", f"GET {self.path}")
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "astra-svc-8182",
                    "port": PORT,
                    "journal_mode": "wal",
                    "logged_event_id": event_id,
                    "total_events": count_events(),
                },
            )
        elif path == "/events":
            raw_limit = query.get("limit", ["20"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                limit = 20
            rows = fetch_events(limit=limit)
            self._send_json(
                200,
                {
                    "service": "astra-svc-8182",
                    "count": len(rows),
                    "events": rows,
                },
            )
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/log":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            event_id = log_event("custom", raw[:1000])
            self._send_json(200, {"status": "logged", "id": event_id})
        else:
            self._send_json(404, {"error": "not_found"})

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    init_db()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
