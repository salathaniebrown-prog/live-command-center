#!/usr/bin/env python3
"""
Zero-Extra-Process Causal DAG + Shannon Entropy + Clock-Drift + Blake2b Merkle Spine.
Uses Python stdlib + SQLite WAL only (no FastAPI/Uvicorn/psutil overhead in Termux).
"""
import hashlib
import json
import math
import os
import socket
import sqlite3
import threading
import time
from collections import Counter, deque
from gateway_shm_hook import GatewayShmTelemetry
_SHM_BUS = GatewayShmTelemetry()

DB_PATH = os.path.expanduser("~/astra_telemetry_wal.db")
TARGET_PORTS = (8088, 8090, 8119)


def _measure_clock_drift_ppm() -> float:
    t0_mono = time.monotonic_ns()
    t0_perf = time.perf_counter_ns()
    _ = sum(i * i for i in range(4000))
    d_mono = max(time.monotonic_ns() - t0_mono, 1)
    d_perf = time.perf_counter_ns() - t0_perf
    return abs(d_perf - d_mono) / d_mono * 1e6


def _shannon_entropy(raw_bytes: bytes) -> float:
    if not raw_bytes:
        return 0.0
    counts = Counter(raw_bytes)
    n = len(raw_bytes)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _probe_ports(ports=TARGET_PORTS) -> dict:
    out = {}
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.12)
        try:
            ok = s.connect_ex(("127.0.0.1", p)) == 0
        except Exception:
            ok = False
        finally:
            s.close()
        out[f"port_{p}"] = {"online": ok}
    return out


class CausalDAGSpine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.prev_hash = "0" * 64
        self.baseline_drift = _measure_clock_drift_ppm()
        self.port_vel_hist = deque(maxlen=16)
        self.io_vel_hist = deque(maxlen=16)
        self._prev_online = None
        self._prev_loadavg = None
        self._init_and_heal_db()

    def _init_and_heal_db(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        for attempt in range(2):
            try:
                with sqlite3.connect(self.db_path, timeout=2.0) as conn:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                    chk = conn.execute("PRAGMA integrity_check;").fetchone()
                    if not chk or chk[0] != "ok":
                        raise RuntimeError(f"WAL integrity fault: {chk}")
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS causal_telemetry (
                            seq_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            subsystem TEXT NOT NULL,
                            shannon_entropy REAL NOT NULL,
                            thermal_drift_ppm REAL NOT NULL,
                            causal_resonance REAL NOT NULL,
                            alert_state TEXT NOT NULL,
                            merkle_root TEXT NOT NULL,
                            frame_json TEXT NOT NULL
                        )
                    """)
                    row = conn.execute(
                        "SELECT merkle_root FROM causal_telemetry ORDER BY seq_id DESC LIMIT 1"
                    ).fetchone()
                    if row and row[0]:
                        self.prev_hash = row[0]
                    conn.commit()
                return
            except Exception:
                if attempt == 0:
                    for suffix in ("", "-wal", "-shm"):
                        p = self.db_path + suffix
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except OSError:
                                pass

    def _mem_used_pct(self) -> float:
        try:
            vals = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] in ("MemTotal:", "MemAvailable:"):
                        vals[parts[0][:-1]] = float(parts[1])
            tot = vals.get("MemTotal", 0.0)
            avail = vals.get("MemAvailable", 0.0)
            if tot > 0:
                return round(((tot - avail) / tot) * 100.0, 2)
        except Exception:
            pass
        return 0.0

    def sample_frame(self) -> dict:
        with self.lock:
            ports_st = _probe_ports(TARGET_PORTS)
            online_cnt = sum(1 for v in ports_st.values() if v.get("online"))
            try:
                load1 = round(os.getloadavg()[0], 3)
            except Exception:
                load1 = 0.0
            mem_pct = self._mem_used_pct()
            thermal_ppm = round(_measure_clock_drift_ppm() - self.baseline_drift, 3)

            cur_p_score = online_cnt * 10.0 + mem_pct
            cur_io_score = load1 * 100.0
            if self._prev_online is None:
                p_vel = 0.0
                io_vel = 0.0
            else:
                p_vel = round(cur_p_score - self._prev_online, 4)
                io_vel = round(cur_io_score - self._prev_loadavg, 4)
            self._prev_online = cur_p_score
            self._prev_loadavg = cur_io_score

            self.port_vel_hist.append(p_vel)
            self.io_vel_hist.append(io_vel)
            resonance = round((p_vel * io_vel) / 10.0, 4)
            alert_state = (
                "CAUSAL_RESONANCE_WARNING"
                if (abs(resonance) > 1.5 or thermal_ppm > 450.0 or mem_pct > 83.0)
                else "NOMINAL"
            )

            dag_edges = [
                {"from": "DAG_PORTS_8088_8090_8119", "to": "CAUSAL_COVARIANCE", "phase_vel": p_vel},
                {"from": "COMPUTE_LOAD_AND_MEM", "to": "CAUSAL_COVARIANCE", "phase_vel": io_vel},
                {"from": "CLOCK_DRIFT_THERMAL_PPM", "to": "MERKLE_WAL_LEDGER", "ppm": thermal_ppm},
            ]
            payload = {
                "ts": time.time(),
                "ports": ports_st,
                "online_target_ports": online_cnt,
                "load_1m": load1,
                "mem_used_pct": mem_pct,
                "thermal_drift_ppm": thermal_ppm,
                "phase_velocity": {"port_mem": p_vel, "load": io_vel},
                "causal_resonance": resonance,
                "alert_state": alert_state,
                "psi_shield": _shm_st,
                "dag_edges": dag_edges,
            }
            raw_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            entropy = round(_shannon_entropy(raw_bytes), 4)

            chain_blob = f"{self.prev_hash}:{entropy}:{raw_bytes.decode('utf-8')}".encode("utf-8")
            merkle_root = hashlib.blake2b(chain_blob, digest_size=32).hexdigest()
            self.prev_hash = merkle_root

            _shm_st = _SHM_BUS.emit_tick(merkle_root)
            if _shm_st.get("shield_state") == "SHIELD_ACTIVE_WAL_TRUNCATED" and alert_state == "NOMINAL":
                alert_state = "PSI_EVICTION_SHIELD"
            frame = {
                "ok": True,
                "service": "astra-causal-dag-spine",
                "seq_hash": merkle_root[:16],
                "merkle_root": merkle_root,
                "shannon_entropy": entropy,
                "wal_compressed": entropy < 1.2 and alert_state == "NOMINAL",
                "telemetry": payload,
            }

            if not frame["wal_compressed"]:
                try:
                    with sqlite3.connect(self.db_path, timeout=2.0) as conn:
                        conn.execute(
                            """
                            INSERT INTO causal_telemetry
                            (subsystem, shannon_entropy, thermal_drift_ppm, causal_resonance, alert_state, merkle_root, frame_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                "ECOSYSTEM_DAG_CORE",
                                entropy,
                                thermal_ppm,
                                resonance,
                                alert_state,
                                merkle_root,
                                json.dumps(frame, separators=(",", ":")),
                            ),
                        )
                        conn.commit()
                except Exception:
                    pass

            return frame


_SPINE = CausalDAGSpine()


def get_causal_dag_frame() -> dict:
    return _SPINE.sample_frame()


def handle_causal_dag_route(handler, req_path: str) -> bool:
    if req_path != "/api/causal-dag":
        return False
    body = json.dumps(get_causal_dag_frame(), separators=(",", ":")).encode("utf-8")
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass
    return True


if __name__ == "__main__":
    print(json.dumps(get_causal_dag_frame(), indent=2))
