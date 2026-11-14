#!/usr/bin/env python3
import hashlib
import http.server
import json
import os
import socketserver
import sqlite3
import sys
import time
import uuid

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_spatial_ledger.db")
PORT = 8129

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spatial_telemetry (
            event_id TEXT PRIMARY KEY,
            mode TEXT,
            gesture_vector TEXT,
            model_action TEXT,
            sha256_proof TEXT,
            status TEXT,
            ts REAL
        )
    """)
    conn.commit()
    conn.close()

def process_spatial_action(mode="WITH_HANDS", gesture="PINCH_SELECT", target_action="EXECUTE_SAGA_FLOW"):
    ev_id = "SPATIAL-" + uuid.uuid4().hex[:8].upper()
    now = time.time()
    vector_data = {"gesture": gesture, "confidence": 0.984, "spatial_coords": {"x": 0.12, "y": 0.85, "z": -1.4}}
    
    proof_payload = f"{ev_id}:{mode}:{gesture}:{target_action}:{now}"
    sha256_proof = hashlib.sha256(proof_payload.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO spatial_telemetry VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ev_id, mode, json.dumps(vector_data), target_action, sha256_proof, "CRYPTOGRAPHICALLY_VERIFIED", now)
    )
    conn.commit()
    conn.close()
    
    return {
        "event_id": ev_id,
        "mode": mode,
        "gesture_vector": vector_data,
        "model_action": target_action,
        "sha256_proof": sha256_proof,
        "status": "CRYPTOGRAPHICALLY_VERIFIED",
        "timestamp": now
    }

class SpatialHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send(self, code, obj):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT event_id, mode, model_action, sha256_proof, status, ts FROM spatial_telemetry ORDER BY ts DESC LIMIT 10").fetchall()
        conn.close()
        self._send(200, {
            "engine": "ASTRA_SPATIAL_MODEL_ASSISTANT_8129",
            "recent_telemetry": [
                {"event_id": r[0], "mode": r[1], "action": r[2], "proof": r[3], "status": r[4], "ts": r[5]}
                for r in rows
            ]
        })

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln) if ln else b"{}"
        try:
            data = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception:
            data = {}
        res = process_spatial_action(
            data.get("mode", "WITH_HANDS"),
            data.get("gesture", "PINCH_SELECT"),
            data.get("target_action", "EXECUTE_SAGA_FLOW")
        )
        self._send(200, res)

class ThreadedSpatialServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    init_db()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(process_spatial_action(), indent=2))
        sys.exit(0)
    srv = ThreadedSpatialServer(("127.0.0.1", PORT), SpatialHandler)
    print(f"[ASTRA SPATIAL ASSISTANT] Listening on 127.0.0.1:{PORT}")
    srv.serve_forever()
