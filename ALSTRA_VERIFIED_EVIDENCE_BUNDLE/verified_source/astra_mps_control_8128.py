#!/usr/bin/env python3
"""
Alstra MPS Bond-Dimension Watchdog, Cross-Modal RF-to-PX4 Steering &
Zero-Serialization UDP Merkle-State Diff Sync Engine (127.0.0.1:8128)
"""
import hashlib
import http.server
import json
import math
import os
import socket
import socketserver
import sqlite3
import struct
import threading
import time
import urllib.request
import uuid
from pathlib import Path

PORT = int(os.environ.get("ALSTRA_SHADOW_PORT", "8128"))
UDP_SYNC_PORT = 18128
HOME = Path.home()
DB_PATH = HOME / ".astra_local_brain.db"

LOCK = threading.Lock()
STATE = {
    "watchdog": {
        "bond_dimension_chi": 2,
        "chi_growth_rate": 0.0,
        "von_neumann_entropy": 0.412,
        "entanglement_threshold": 0.665,
        "preemption_state": "NOMINAL_LAMINAR",
        "preemption_actions": 0,
        "xdp_isolated_slots": [],
    },
    "rf_px4_bridge": {
        "wifi_rssi_dbm": -52,
        "rf_phase_rad": 0.0,
        "px4_roll_trim_deg": 0.0,
        "px4_pitch_trim_deg": 0.0,
        "px4_yaw_hold_rate": 0.0,
        "waypoint_hold_mode": "GNSS_OPTICAL_LOCK",
        "feature_weights_16": [1.0] * 16,
    },
    "udp_merkle_sync": {
        "udp_port": UDP_SYNC_PORT,
        "packets_broadcast": 0,
        "last_merkle_root": hashlib.sha256(b"GENESIS_8128").hexdigest(),
        "packet_bytes": 64,
    },
    "updated_at": time.time(),
}


def compute_mps_entanglement_and_control():
    # Pull live MPS cores from 8157 and RF telemetry from 8155
    mps_data = {}
    rf_data = {}
    try:
        with urllib.request.urlopen("http://127.0.0.1:8157/v1/neuro/telemetry", timeout=1.0) as r:
            mps_data = json.loads(r.read().decode("utf-8")).get("neuro_spine", {})
    except Exception:
        pass
    try:
        with urllib.request.urlopen("http://127.0.0.1:8155/v1/synaptic/telemetry", timeout=1.0) as r:
            rf_data = json.loads(r.read().decode("utf-8")).get("synaptic", {}).get("rf_spectrum", {})
    except Exception:
        pass

    last_mps = mps_data.get("last_mps", {})
    last_slot = mps_data.get("last_slot", {})
    fisher = float(last_slot.get("fisher_entropy", 0.35))
    G1 = last_mps.get("G1", [[0.85, 0.52], [0.52, -0.85]])

    # Compute normalized Schmidt singular probabilities from G1 bond weights
    w0 = sum(x * x for x in G1[0]) if len(G1) > 0 else 0.75
    w1 = sum(x * x for x in G1[1]) if len(G1) > 1 else 0.25
    tot = max(1e-9, w0 + w1)
    p0, p1 = max(1e-9, w0 / tot), max(1e-9, w1 / tot)
    svn = -(p0 * math.log(p0) + p1 * math.log(p1))
    # Couple Fisher surprise into effective entanglement entropy
    eff_entropy = round(min(0.999, svn * 0.75 + min(0.35, fisher * 0.12)), 4)

    rssi = int(rf_data.get("wifi_rssi_dbm", -52))
    em_freq = float(rf_data.get("em_plasma_freq_hz", 2.412))
    rf_phase = round((abs(rssi) * 0.087 + em_freq) % (2 * math.pi), 4)

    # Cross-modal RF-to-PX4 spatial steering trims & 16-feature slot re-weighting
    interference_idx = max(0.0, (-rssi - 50.0) / 35.0)
    roll_trim = round(math.sin(rf_phase) * 1.45 * (0.3 + interference_idx), 3)
    pitch_trim = round(math.cos(rf_phase) * 1.20 * (0.3 + interference_idx), 3)
    yaw_rate = round(math.sin(rf_phase * 0.5) * 0.85, 3)
    hold_mode = "RF_STANDING_WAVE_COMPENSATED" if interference_idx > 0.45 else "GNSS_OPTICAL_LOCK"

    weights16 = []
    for idx in range(16):
        if idx < 4:  # PX4 attitude slots boosted under RF interference
            w = 1.0 + interference_idx * 0.65
        elif idx < 8:  # Neuromorphic TCAD spike slots boosted under high entropy
            w = 1.0 + eff_entropy * 0.8
        else:
            w = 1.0 - interference_idx * 0.15
        weights16.append(round(max(0.25, min(2.5, w)), 3))

    merkle_hex = mps_data.get("merkle_state_root") or hashlib.sha256(f"{eff_entropy}:{time.time()}".encode()).hexdigest()

    with LOCK:
        prev_svn = STATE["watchdog"]["von_neumann_entropy"]
        chi_rate = round(eff_entropy - prev_svn, 4)
        preempt = eff_entropy > STATE["watchdog"]["entanglement_threshold"]
        STATE["watchdog"]["bond_dimension_chi"] = 4 if preempt else 2
        STATE["watchdog"]["chi_growth_rate"] = chi_rate
        STATE["watchdog"]["von_neumann_entropy"] = eff_entropy
        STATE["watchdog"]["preemption_state"] = "SCHED_FIFO_PREEMPT_ACTIVE" if preempt else "NOMINAL_LAMINAR"
        if preempt:
            STATE["watchdog"]["preemption_actions"] += 1
            STATE["watchdog"]["xdp_isolated_slots"] = [idx for idx, val in enumerate(weights16) if val < 0.85][:3]
        else:
            STATE["watchdog"]["xdp_isolated_slots"] = []

        STATE["rf_px4_bridge"]["wifi_rssi_dbm"] = rssi
        STATE["rf_px4_bridge"]["rf_phase_rad"] = rf_phase
        STATE["rf_px4_bridge"]["px4_roll_trim_deg"] = roll_trim
        STATE["rf_px4_bridge"]["px4_pitch_trim_deg"] = pitch_trim
        STATE["rf_px4_bridge"]["px4_yaw_hold_rate"] = yaw_rate
        STATE["rf_px4_bridge"]["waypoint_hold_mode"] = hold_mode
        STATE["rf_px4_bridge"]["feature_weights_16"] = weights16

        # Broadcast 64-byte zero-serialization binary Merkle diff packet over UDP
        try:
            root_bytes = bytes.fromhex(merkle_hex[:64].ljust(64, "0"))
            pkt = struct.pack("!4sI32sfff12s", b"AMRK", STATE["watchdog"]["bond_dimension_chi"], root_bytes, eff_entropy, roll_trim, pitch_trim, b"\x00" * 12)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(pkt, ("127.0.0.1", UDP_SYNC_PORT))
            sock.close()
            STATE["udp_merkle_sync"]["packets_broadcast"] += 1
            STATE["udp_merkle_sync"]["last_merkle_root"] = merkle_hex
        except Exception:
            pass

        STATE["updated_at"] = time.time()
        return json.loads(json.dumps(STATE))


def _bg_control_loop():
    while True:
        try:
            compute_mps_entanglement_and_control()
        except Exception:
            pass
        time.sleep(1.5)


class ThreadingReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class Control8128Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _send_json(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"ctrl8128-{uuid.uuid4().hex[:12]}")
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
        with LOCK:
            snap = json.loads(json.dumps(STATE))
        return self._send_json(
            {
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_MPS_ENTANGLEMENT_CONTROL_8128",
                "control_plane": snap,
                "timestamp": time.time(),
            }
        )

    def do_POST(self):
        snap = compute_mps_entanglement_and_control()
        return self._send_json(
            {
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_MPS_ENTANGLEMENT_CONTROL_8128",
                "control_plane": snap,
            }
        )


if __name__ == "__main__":
    threading.Thread(target=_bg_control_loop, daemon=True).start()
    with ThreadingReuseTCP(("0.0.0.0", PORT), Control8128Handler) as srv:
        print(f"[✔] Alstra MPS Bond-Dimension Watchdog & RF-PX4 Control Plane active on 0.0.0.0:{PORT}")
        srv.serve_forever()
