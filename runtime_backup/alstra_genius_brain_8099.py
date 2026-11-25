#!/usr/bin/env python3
"""
Alstra Persistent Telemetry & Context Genius Brain (127.0.0.1:8099)
- SQLite WAL mode (PRAGMA journal_mode=WAL)
- GET / & GET /v1/telemetry (TDD contract compliant with unique query_id)
- GET/POST /v1/context (Non-volatile JSON key-value store)
- POST /v1/execute & GET /v1/ledger (ast.parse() guarded execution + audit ledger)
"""
import ast
import json
import sqlite3
import subprocess
import time
import uuid
import http.server
import socketserver
from pathlib import Path

DB_PATH = Path.home() / ".astra_local_brain.db"
PORT = 8099

def init_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS persistent_context (
            ctx_key TEXT PRIMARY KEY,
            ctx_value TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            objective TEXT NOT NULL,
            language TEXT NOT NULL,
            code TEXT NOT NULL,
            exit_code INTEGER NOT NULL,
            stdout TEXT,
            stderr TEXT
        )
    """)
    conn.commit()
    conn.close()

class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True

class BrainHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"brain8099-{uuid.uuid4().hex[:12]}")
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        init_db()
        path = self.path.split("?")[0]
        conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
        cur = conn.cursor()

        if path in ("/", "/health", "/v1/telemetry"):
            ctx_count = cur.execute("SELECT COUNT(*) FROM persistent_context;").fetchone()[0]
            task_count = cur.execute("SELECT COUNT(*) FROM task_ledger;").fetchone()[0]
            conn.close()
            return self._send({
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_GENIUS_BRAIN_WAL",
                "wal_mode": True,
                "context_keys_count": ctx_count,
                "cumulative_tasks_executed": task_count,
                "timestamp": time.time()
            })

        if path == "/v1/context":
            rows = cur.execute("SELECT ctx_key, ctx_value, updated_at FROM persistent_context ORDER BY updated_at DESC;").fetchall()
            conn.close()
            items = {}
            for k, v, ts in rows:
                try:
                    items[k] = {"value": json.loads(v), "updated_at": ts}
                except Exception:
                    items[k] = {"value": v, "updated_at": ts}
            return self._send({"ok": True, "status": "ONLINE", "context": items})

        if path == "/v1/ledger":
            rows = cur.execute(
                "SELECT id, timestamp, objective, language, exit_code, stdout, stderr FROM task_ledger ORDER BY id DESC LIMIT 25;"
            ).fetchall()
            conn.close()
            ledger = [
                {
                    "id": r[0], "timestamp": r[1], "objective": r[2],
                    "language": r[3], "exit_code": r[4], "stdout": r[5], "stderr": r[6]
                }
                for r in rows
            ]
            return self._send({"ok": True, "status": "ONLINE", "ledger": ledger})

        conn.close()
        return self._send({"ok": False, "error": f"Unknown GET path: {path}"}, 404)

    def do_POST(self):
        init_db()
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
        cur = conn.cursor()

        if path == "/v1/context":
            key = str(body.get("key", "")).strip()
            if not key:
                conn.close()
                return self._send({"ok": False, "error": "Missing 'key'"}, 400)
            val_json = json.dumps(body.get("value"))
            now = time.time()
            cur.execute("""
                INSERT INTO persistent_context (ctx_key, ctx_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(ctx_key) DO UPDATE SET ctx_value=excluded.ctx_value, updated_at=excluded.updated_at;
            """, (key, val_json, now))
            conn.commit()
            conn.close()
            return self._send({"ok": True, "status": "PERSISTED", "key": key, "updated_at": now})

        if path == "/v1/execute":
            objective = str(body.get("objective", "AST-guarded execution"))
            language = str(body.get("language", "python")).lower()
            code = str(body.get("code", ""))
            if language == "python":
                try:
                    ast.parse(code)
                except SyntaxError as exc:
                    conn.close()
                    return self._send({"ok": False, "error": f"AST SyntaxError: {exc}"}, 400)
                cmd = ["python3", "-c", code]
            else:
                cmd = ["bash", "-c", code]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            now = time.time()
            cur.execute("""
                INSERT INTO task_ledger (timestamp, objective, language, code, exit_code, stdout, stderr)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, objective, language, code, proc.returncode, proc.stdout[:4000], proc.stderr[:4000]))
            conn.commit()
            conn.close()
            return self._send({
                "ok": proc.returncode == 0,
                "status": "EXECUTED",
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr
            })

        conn.close()
        return self._send({"ok": False, "error": f"Unknown POST path: {path}"}, 404)

if __name__ == "__main__":
    init_db()
    with ReuseTCP(("127.0.0.1", PORT), BrainHandler) as srv:
        print(f"[✔] Alstra Genius Brain (WAL) active on 127.0.0.1:{PORT}")
        srv.serve_forever()
