#!/usr/bin/env python3
"""
Alstra Zero-Copy 4KB mmap Spectral Phase-Lock & Blake2b Merkle-Anchored Spine (127.0.0.1:8135)
1. Microsecond Kernel Scheduler Jitter Radar (nanosecond monotonic_ns drift tracking)
2. Kuramoto Phase-Coherence Engine across core nodes (8088, 8090, 8133, 8134)
3. Zero-Copy 4096-byte (4 KB) mmap Ring Buffer + 32-byte BLAKE2b Merkle Ledger
"""
import hashlib
import http.server
import json
import math
import mmap
import os
import socket
import socketserver
import struct
import threading
import time
import uuid
from pathlib import Path

PORT = int(os.environ.get("ALSTRA_SHADOW_PORT", "8135"))
HOME = Path.home()
MMAP_PATH = HOME / ".alstra_phaselock_4kb.mmap"
MMAP_SIZE = 4096          # Exact 4 KB OS page boundary
HEADER_SIZE = 64
SLOT_SIZE = 64
SLOT_COUNT = (MMAP_SIZE - HEADER_SIZE) // SLOT_SIZE  # 63 binary slots

CORE_NODES = [8088, 8090, 8133, 8134]

LOCK = threading.Lock()
STATE = {
    "jitter_radar": {
        "target_sleep_us": 10000.0,
        "last_jitter_us": 0.0,
        "mean_jitter_us": 0.0,
        "max_jitter_us": 0.0,
        "samples": 0,
    },
    "kuramoto": {
        "nodes": CORE_NODES,
        "coupling_k": 2.4,
        "phases_rad": [0.0, 0.05, 0.10, 0.15],
        "order_parameter_r": 0.996,
        "mean_phase_psi": 0.075,
        "active_node_mask": 0b1111,
        "coherence_state": "PHASE_LOCKED_COHERENT",
    },
    "mmap_merkle": {
        "file_path": str(MMAP_PATH),
        "file_bytes": MMAP_SIZE,
        "slot_capacity": SLOT_COUNT,
        "frames_written": 0,
        "blake2b_merkle_root": hashlib.blake2b(b"ALSTRA_8135_GENESIS", digest_size=32).hexdigest(),
        "last_leaf_blake2b": "",
    },
    "updated_at": time.time(),
}


class Mmap4KBRing:
    def __init__(self, path: Path):
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
        os.ftruncate(fd, MMAP_SIZE)
        self.mm = mmap.mmap(fd, MMAP_SIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        os.close(fd)
        if self.mm[0:4] != b"APHL":
            genesis = hashlib.blake2b(b"ALSTRA_8135_GENESIS", digest_size=32).digest()
            hdr = struct.pack("!4sIfff12s32s", b"APHL", 0, 1.0, 0.0, 0.0, b"\x00" * 12, genesis)
            self.mm[0:HEADER_SIZE] = hdr
            self.mm.flush()

    def write_frame(self, seq: int, ts_ns: int, jitter_us: float, r_val: float, psi_val: float, mask: int, prev_root_hex: str) -> tuple[str, str]:
        # Pack 32-byte telemetry payload and hash with BLAKE2b-256
        core_bytes = struct.pack("!QQfffI", seq, ts_ns, jitter_us, r_val, psi_val, mask)
        leaf_digest = hashlib.blake2b(core_bytes, digest_size=32).digest()
        new_root_digest = hashlib.blake2b(bytes.fromhex(prev_root_hex) + leaf_digest, digest_size=32).digest()

        # 64-byte binary slot: 32 bytes telemetry + 32 bytes BLAKE2b leaf hash
        slot_bytes = core_bytes + leaf_digest
        slot_idx = (seq - 1) % SLOT_COUNT
        offset = HEADER_SIZE + slot_idx * SLOT_SIZE
        self.mm[offset : offset + SLOT_SIZE] = slot_bytes

        # Update 64-byte page header in-place
        hdr = struct.pack("!4sIfff12s32s", b"APHL", seq, r_val, psi_val, jitter_us, b"\x00" * 12, new_root_digest)
        self.mm[0:HEADER_SIZE] = hdr
        return new_root_digest.hex(), leaf_digest.hex()

    def close(self):
        try:
            self.mm.flush()
            self.mm.close()
        except Exception:
            pass


MMAP_RING: Mmap4KBRing | None = None


def _probe_port_rtt_ms(port: int) -> tuple[bool, float]:
    t0 = time.perf_counter_ns()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.12)
    try:
        rc = s.connect_ex(("127.0.0.1", port))
        rtt_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        return (rc == 0), rtt_ms
    except Exception:
        return False, 120.0
    finally:
        s.close()


def step_phaselock_cycle() -> dict:
    # 1. Microsecond Kernel Scheduler Jitter Radar (10 ms monotonic target)
    target_ns = 10_000_000
    t_start = time.monotonic_ns()
    time.sleep(0.01)
    t_actual = time.monotonic_ns() - t_start
    jitter_us = round(abs(t_actual - target_ns) / 1000.0, 2)

    # 2. Kuramoto Coupled Oscillator Step across (8088, 8090, 8133, 8134)
    rtts = []
    mask = 0
    for idx, p in enumerate(CORE_NODES):
        alive, rtt = _probe_port_rtt_ms(p)
        if alive:
            mask |= (1 << idx)
        rtts.append(rtt)

    with LOCK:
        phases = list(STATE["kuramoto"]["phases_rad"])
        K = STATE["kuramoto"]["coupling_k"]
        N = len(CORE_NODES)
        dt = 0.08
        next_phases = []
        for i in range(N):
            # Natural frequency perturbed by microsecond port RTT
            omega_i = 1.0 + min(1.5, rtts[i] * 0.02)
            coupling = sum(math.sin(phases[j] - phases[i]) for j in range(N)) * (K / N)
            next_phases.append((phases[i] + (omega_i + coupling) * dt) % (2.0 * math.pi))

        sum_cos = sum(math.cos(th) for th in next_phases) / N
        sum_sin = sum(math.sin(th) for th in next_phases) / N
        order_r = round(math.hypot(sum_cos, sum_sin), 5)
        mean_psi = round(math.atan2(sum_sin, sum_cos), 5)
        coh_state = "PHASE_LOCKED_COHERENT" if order_r >= 0.88 else "PHASE_DRIFT_REALIGNING"

        # Update Jitter Radar stats
        jr = STATE["jitter_radar"]
        n_samp = jr["samples"] + 1
        jr["last_jitter_us"] = jitter_us
        jr["mean_jitter_us"] = round(((jr["mean_jitter_us"] * jr["samples"]) + jitter_us) / n_samp, 2)
        jr["max_jitter_us"] = round(max(jr["max_jitter_us"], jitter_us), 2)
        jr["samples"] = n_samp

        STATE["kuramoto"]["phases_rad"] = [round(x, 4) for x in next_phases]
        STATE["kuramoto"]["order_parameter_r"] = order_r
        STATE["kuramoto"]["mean_phase_psi"] = mean_psi
        STATE["kuramoto"]["active_node_mask"] = mask
        STATE["kuramoto"]["coherence_state"] = coh_state

        seq = STATE["mmap_merkle"]["frames_written"] + 1
        prev_root = STATE["mmap_merkle"]["blake2b_merkle_root"]
        if MMAP_RING is not None:
            new_root, leaf_hex = MMAP_RING.write_frame(seq, time.time_ns(), jitter_us, order_r, mean_psi, mask, prev_root)
            STATE["mmap_merkle"]["frames_written"] = seq
            STATE["mmap_merkle"]["blake2b_merkle_root"] = new_root
            STATE["mmap_merkle"]["last_leaf_blake2b"] = leaf_hex

        STATE["updated_at"] = time.time()
        return json.loads(json.dumps(STATE))


def _bg_phaselock_loop():
    while True:
        try:
            step_phaselock_cycle()
        except Exception:
            pass
        time.sleep(1.5)


class ThreadingReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class PhaseLock8135Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _send_json(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"phl8135-{uuid.uuid4().hex[:12]}")
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
                "service": "ALSTRA_MMAP_SPECTRAL_PHASELOCK_8135",
                "phaselock_spine": snap,
                "timestamp": time.time(),
            }
        )

    def do_POST(self):
        snap = step_phaselock_cycle()
        return self._send_json(
            {
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_MMAP_SPECTRAL_PHASELOCK_8135",
                "phaselock_spine": snap,
            }
        )


if __name__ == "__main__":
    MMAP_RING = Mmap4KBRing(MMAP_PATH)
    threading.Thread(target=_bg_phaselock_loop, daemon=True).start()
    try:
        with ThreadingReuseTCP(("0.0.0.0", PORT), PhaseLock8135Handler) as srv:
            print(f"[✔] Alstra Zero-Copy 4KB mmap Spectral Phase-Lock & Blake2b Merkle Spine active on 0.0.0.0:{PORT}")
            srv.serve_forever()
    finally:
        MMAP_RING.close()
