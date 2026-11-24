import hashlib
import json
import math
import os
import socket
import sqlite3
import sys
import threading
import time
from collections import Counter, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from psi_mmap_shield import PsiMmapShield
from ram_reclaimer_daemon import force_kernel_ram_release, get_rss_mb, prune_zombie_python_workers

DB_PATH = os.path.expanduser("~/astra_telemetry_wal.db")
SUPERVISOR_PORT = int(os.environ.get("SUPERVISOR_PORT", "8099"))
TARGET_PORTS = (8088, 8090, 8119)


class UnifiedSingleLoopCore:
    __slots__ = ("shield", "prev_hash", "baseline_drift", "socket_hist", "last_frame", "lock")

    def __init__(self):
        self.shield = PsiMmapShield()
        self.prev_hash = sys.intern("0" * 64)
        self.baseline_drift = self._measure_clock_drift()
        self.socket_hist = deque(maxlen=8)
        self.last_frame = {}
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(DB_PATH, timeout=1.5) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA cache_size=-1024;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS causal_telemetry (
                        seq_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        shannon_entropy REAL NOT NULL,
                        thermal_drift_ppm REAL NOT NULL,
                        avail_ram_mb REAL NOT NULL,
                        merkle_root TEXT NOT NULL,
                        frame_json TEXT NOT NULL
                    )
                """)
                row = conn.execute(
                    "SELECT merkle_root FROM causal_telemetry ORDER BY seq_id DESC LIMIT 1"
                ).fetchone()
                if row and row[0]:
                    self.prev_hash = sys.intern(row[0])
                conn.commit()
        except Exception:
            pass

    @staticmethod
    def _measure_clock_drift() -> float:
        t0_m = time.monotonic_ns()
        t0_p = time.perf_counter_ns()
        _ = sum(i * i for i in range(2500))
        d_m = max(time.monotonic_ns() - t0_m, 1)
        d_p = time.perf_counter_ns() - t0_p
        return abs(d_p - d_m) / d_m * 1e6

    @staticmethod
    def _probe_local_ports(ports: tuple) -> dict:
        res = {}
        for p in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            online = s.connect_ex(("127.0.0.1", p)) == 0
            s.close()
            res[sys.intern(f"port_{p}")] = online
        return res

    @staticmethod
    def _shannon_entropy(raw: bytes) -> float:
        if not raw:
            return 0.0
        counts = Counter(raw)
        n = len(raw)
        return -sum((c / n) * math.log2(c / n) for c in counts.values())

    def tick(self) -> dict:
        with self.lock:
            ports_state = self._probe_local_ports(TARGET_PORTS)
            thermal_ppm = round(self._measure_clock_drift() - self.baseline_drift, 3)
            shm_status = self.shield.write_zero_copy_frame(self.prev_hash)

            payload = {
                "ports": ports_state,
                "avail_ram_mb": shm_status["avail_ram_mb"],
                "psi_mem_avg10": shm_status["psi_mem_avg10"],
                "shield_state": shm_status["shield_state"],
                "process_rss_mb": get_rss_mb(),
                "thermal_drift_ppm": thermal_ppm,
            }

            raw_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            entropy = round(self._shannon_entropy(raw_bytes), 4)
            merkle_root = hashlib.blake2b(
                f"{self.prev_hash}:{entropy}:{raw_bytes.decode('utf-8')}".encode("utf-8"),
                digest_size=32,
            ).hexdigest()
            self.prev_hash = sys.intern(merkle_root)

            frame = {
                "seq_hash": merkle_root[:16],
                "merkle_root": merkle_root,
                "entropy": entropy,
                "telemetry": payload,
            }
            self.last_frame = frame

            if entropy >= 1.6 or shm_status["shield_state"] != "NOMINAL":
                try:
                    with sqlite3.connect(DB_PATH, timeout=1.5) as conn:
                        conn.execute(
                            """
                            INSERT INTO causal_telemetry
                            (shannon_entropy, thermal_drift_ppm, avail_ram_mb, merkle_root, frame_json)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                entropy,
                                thermal_ppm,
                                shm_status["avail_ram_mb"],
                                merkle_root,
                                json.dumps(frame, separators=(",", ":")),
                            ),
                        )
                        conn.commit()
                except Exception:
                    pass

            return frame


_CORE = UnifiedSingleLoopCore()


class _SupervisorServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class _SupervisorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send_json(self, code: int, obj: dict):
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "status": "SINGLE_LOOP_ACTIVE",
                    "rss_mb": get_rss_mb(),
                    "avail_ram_mb": _CORE.shield.read_available_ram_mb(),
                    "head_merkle": _CORE.prev_hash,
                },
            )
            return
        self._send_json(200, {"ok": True, "frame": _CORE.last_frame or _CORE.tick()})

    def do_POST(self):
        p = (self.path or "/").split("?", 1)[0]
        if p == "/trim":
            self._send_json(200, {"ok": True, "trim_result": force_kernel_ram_release()})
            return
        self._send_json(200, {"ok": True, "frame": _CORE.tick()})


def _loop_worker():
    while True:
        _CORE.tick()
        time.sleep(1.0)


def _verify_supervisor_boot():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", SUPERVISOR_PORT))
        sock.close()
    except Exception:
        pass


if __name__ == "__main__":
    prune_zombie_python_workers()
    force_kernel_ram_release()
    _verify_supervisor_boot()
    threading.Thread(target=_loop_worker, name="single-loop-tick", daemon=True).start()
    _SupervisorServer(("127.0.0.1", SUPERVISOR_PORT), _SupervisorHandler).serve_forever()
