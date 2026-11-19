#!/usr/bin/env python3
"""
Alstra Optical Acoustic Telemetry (AOT) & Photonic Resonance Engine (127.0.0.1:8153)
- Closed-loop Camera-to-Prism optical reflection calibration (ambient lux, prism luma, contrast ratio)
- Acoustic room-noise resonance coupling (dBFS noise floor + dominant modal Hz)
- Hands-free auto-luminance & auto-sonar volume feedback loop for 4-Way Pepper's Ghost rendering
- Predictive Genius Brain (8099) pre-triggering on optical washout or acoustic spikes
- Persists AOT frames to SQLite WAL (~/.astra_local_brain.db)
"""
import http.server
import json
import os
import socketserver
import sqlite3
import threading
import time
import urllib.request
import uuid
from pathlib import Path

PORT = int(os.environ.get("ALSTRA_SHADOW_PORT", "8153"))
HOME = Path.home()
DB_PATH = HOME / ".astra_local_brain.db"

STATE_LOCK = threading.Lock()
AOT_STATE = {
    "ambient_lux": 120.0,
    "prism_reflection_luma": 185.0,
    "prism_contrast_ratio": 2.45,
    "room_noise_dbfs": -42.0,
    "acoustic_resonance_hz": 118.5,
    "auto_luminance_gain": 1.15,
    "auto_sonar_volume": 0.22,
    "calibration_mode": "CLOSED_LOOP_AUTO",
    "brain_pretriggers_sent": 0,
    "last_pretrigger_reason": "NOMINAL_PHOTONIC_RESONANCE",
    "samples_ingested": 0,
    "updated_at": time.time(),
}


def init_aot_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS aot_photonic_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            ambient_lux REAL,
            prism_luma REAL,
            contrast_ratio REAL,
            room_dbfs REAL,
            resonance_hz REAL,
            auto_luma_gain REAL,
            auto_sonar_vol REAL,
            pretriggered INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def trigger_genius_brain_ahead(reason: str, snapshot: dict):
    def _post():
        payload = json.dumps(
            {
                "event": "AOT_PREDICTIVE_PRETRIGGER",
                "source": "PHOTONIC_ACOUSTIC_ENGINE_8153",
                "reason": reason,
                "telemetry": snapshot,
                "timestamp": time.time(),
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8099/",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0) as r:
                r.read()
        except Exception:
            pass

    threading.Thread(target=_post, daemon=True).start()


def compute_closed_loop_gains(ambient_lux: float, prism_luma: float, room_dbfs: float) -> tuple[float, float, float]:
    # Contrast ratio between reflected prism core and ambient room light
    contrast = round(max(0.25, min(12.0, (prism_luma + 18.0) / max(15.0, ambient_lux * 0.55))), 3)

    # Higher room lux -> boost hologram luminance up to 2.4x so acrylic reflection stays vivid
    norm_lux = max(0.0, min(1.0, ambient_lux / 450.0))
    auto_luma = round(0.85 + norm_lux * 1.55 + (0.25 if contrast < 1.5 else 0.0), 3)

    # Higher ambient room noise or brighter room -> auto-scale sonar volume smoothly (0.14 to 0.55)
    norm_noise = max(0.0, min(1.0, (room_dbfs + 65.0) / 55.0))
    auto_vol = round(max(0.14, min(0.55, 0.16 + norm_noise * 0.24 + norm_lux * 0.14)), 3)
    return contrast, auto_luma, auto_vol


def ingest_sensor_frame(data: dict) -> dict:
    ambient_lux = float(data.get("ambient_lux", AOT_STATE["ambient_lux"]))
    prism_luma = float(data.get("prism_reflection_luma", AOT_STATE["prism_reflection_luma"]))
    room_dbfs = float(data.get("room_noise_dbfs", AOT_STATE["room_noise_dbfs"]))
    res_hz = float(data.get("acoustic_resonance_hz", AOT_STATE["acoustic_resonance_hz"]))

    contrast, auto_luma, auto_vol = compute_closed_loop_gains(ambient_lux, prism_luma, room_dbfs)

    pretriggered = 0
    reason = "NOMINAL_PHOTONIC_RESONANCE"
    if contrast < 1.45:
        pretriggered = 1
        reason = f"OPTICAL_WASHOUT_PREEMPT (contrast={contrast} < 1.45, lux={ambient_lux})"
    elif room_dbfs > -18.0:
        pretriggered = 1
        reason = f"ACOUSTIC_RESONANCE_SURGE (dBFS={room_dbfs} > -18.0, hz={res_hz})"

    with STATE_LOCK:
        AOT_STATE["ambient_lux"] = round(ambient_lux, 2)
        AOT_STATE["prism_reflection_luma"] = round(prism_luma, 2)
        AOT_STATE["prism_contrast_ratio"] = contrast
        AOT_STATE["room_noise_dbfs"] = round(room_dbfs, 2)
        AOT_STATE["acoustic_resonance_hz"] = round(res_hz, 2)
        AOT_STATE["auto_luminance_gain"] = auto_luma
        AOT_STATE["auto_sonar_volume"] = auto_vol
        AOT_STATE["samples_ingested"] += 1
        AOT_STATE["updated_at"] = time.time()
        if pretriggered:
            AOT_STATE["brain_pretriggers_sent"] += 1
            AOT_STATE["last_pretrigger_reason"] = reason
        snap = dict(AOT_STATE)

    if pretriggered:
        trigger_genius_brain_ahead(reason, snap)

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=3.0)
        conn.execute(
            """
            INSERT INTO aot_photonic_telemetry
            (ts, ambient_lux, prism_luma, contrast_ratio, room_dbfs, resonance_hz, auto_luma_gain, auto_sonar_vol, pretriggered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (time.time(), ambient_lux, prism_luma, contrast, room_dbfs, res_hz, auto_luma, auto_vol, pretriggered),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return snap


class ThreadingReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class AotHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _send_json(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"aot8153-{uuid.uuid4().hex[:12]}")
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
        self._send_json({"ok": True})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/health", "/v1/telemetry", "/v1/aot/telemetry"):
            with STATE_LOCK:
                snap = dict(AOT_STATE)
            return self._send_json(
                {
                    "ok": True,
                    "status": "ONLINE",
                    "port": PORT,
                    "service": "ALSTRA_OPTICAL_ACOUSTIC_TELEMETRY_8153",
                    "aot": snap,
                    "timestamp": time.time(),
                }
            )
        return self._send_json({"ok": False, "error": f"Unknown GET path: {path}"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
        try:
            data = json.loads(body) if body.strip() else {}
        except Exception:
            data = {}
        snap = ingest_sensor_frame(data)
        return self._send_json(
            {
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_OPTICAL_ACOUSTIC_TELEMETRY_8153",
                "aot": snap,
            }
        )


if __name__ == "__main__":
    init_aot_db()
    with ThreadingReuseTCP(("0.0.0.0", PORT), AotHandler) as srv:
        print(f"[✔] Alstra Optical Acoustic Telemetry (AOT) & Photonic Resonance Engine active on 0.0.0.0:{PORT}")
        srv.serve_forever()
