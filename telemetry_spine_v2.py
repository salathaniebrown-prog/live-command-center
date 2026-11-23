#!/usr/bin/env python3
"""
Bounded-RAM Flying Car & S-Zero Plus eVTOL Telemetry Data Spine (:8159)
Uses SQLite WAL + 500-row rolling ring buffer to keep RSS under 12 MB.
"""
import gc
import http.server
import json
import os
import sqlite3
import time

PORT = int(os.environ.get("TELEMETRY_SPINE_PORT", "8159"))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "astra_flight_ledger.db")
MAX_ROWS = 500


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-2000;")
    conn.execute("PRAGMA mmap_size=4194304;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            craft_id TEXT NOT NULL,
            altitude_ft REAL NOT NULL,
            airspeed_kts REAL NOT NULL,
            battery_pct REAL NOT NULL,
            rotor_rpm INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


CONN = init_db()


def ingest_frame(data: dict) -> dict:
    ts = float(data.get("ts") or time.time())
    craft_id = str(data.get("craft_id") or "S-ZERO-PLUS-01")
    alt = float(data.get("altitude_ft", 0.0))
    spd = float(data.get("airspeed_kts", 0.0))
    bat = float(data.get("battery_pct", 100.0))
    rpm = int(data.get("rotor_rpm", 0))
    raw = json.dumps(data, separators=(",", ":"))[:1024]

    cur = CONN.cursor()
    cur.execute(
        "INSERT INTO telemetry_frames (ts, craft_id, altitude_ft, airspeed_kts, battery_pct, rotor_rpm, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, craft_id, alt, spd, bat, rpm, raw),
    )
    row_id = cur.lastrowid
    if row_id and row_id % 25 == 0:
        cur.execute(
            "DELETE FROM telemetry_frames WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM telemetry_frames)",
            (MAX_ROWS,),
        )
        gc.collect()
    CONN.commit()
    return {"ok": True, "frame_id": row_id, "craft_id": craft_id, "ring_cap": MAX_ROWS}


class SpineHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p in ("/", "/health", "/api/telemetry/spine", "/api/evtol/spine"):
            row = CONN.execute(
                "SELECT id, ts, craft_id, altitude_ft, airspeed_kts, battery_pct, rotor_rpm FROM telemetry_frames ORDER BY id DESC LIMIT 1"
            ).fetchone()
            count = CONN.execute("SELECT COUNT(*) FROM telemetry_frames").fetchone()[0]
            latest = (
                {
                    "frame_id": row[0],
                    "ts": row[1],
                    "craft_id": row[2],
                    "altitude_ft": row[3],
                    "airspeed_kts": row[4],
                    "battery_pct": row[5],
                    "rotor_rpm": row[6],
                }
                if row
                else None
            )
            return self._send(200, {"ok": True, "service": "telemetry-spine-v2", "port": PORT, "stored_frames": count, "ring_cap": MAX_ROWS, "latest": latest})
        return self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        p = (self.path or "/").split("?", 1)[0]
        if p in ("/api/telemetry/spine", "/api/telemetry/ingest", "/api/evtol/spine"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 4096)) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                data = {}
            return self._send(200, ingest_frame(data))
        return self._send(404, {"ok": False, "error": "not_found"})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), SpineHandler).serve_forever()
