#!/usr/bin/env python3
import gc
import hashlib
import http.server
import json
import math
import mmap
import os
import signal
import socket
import socketserver
import struct
import sys
import threading
import time
from collections import deque

LISTEN_PORT = 8170
TARGET_PORTS = (8088, 8090, 8110, 8125)
RING_SLOTS = 256
FRAME_FMT = "<Qddddd"  # 48 bytes * 256 = 12,288 bytes (12 KB mmap ring)
FRAME_SIZE = struct.calcsize(FRAME_FMT)
SHM_PATH = os.path.expanduser("~/local_shm_monitor/local_metrics_ring.shm")
STATE_SAVE_PATH = os.path.expanduser("~/local_shm_monitor/last_state.json")

STATE_LOCK = threading.Lock()
LATEST_STATE = {"status": "STARTING"}


class SharedMemoryMonitor:
    def __init__(self):
        self.seq = 0
        self.history = deque(maxlen=32)
        self.chain_hash = b"\x00" * 16
        with open(SHM_PATH, "wb") as f:
            f.write(b"\x00" * (RING_SLOTS * FRAME_SIZE))
        self.shm_fd = open(SHM_PATH, "r+b")
        self.ring = mmap.mmap(self.shm_fd.fileno(), RING_SLOTS * FRAME_SIZE)

    def read_host_metrics(self):
        try:
            load1, _, _ = os.getloadavg()
            cores = os.cpu_count() or 1
            cpu_norm = min(load1 / cores, 2.0)
        except OSError:
            cpu_norm = 0.10

        mem_ratio = 0.50
        free_mib = 0.0
        if os.path.exists("/proc/meminfo"):
            info = {}
            with open("/proc/meminfo", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    key, sep, rest = line.partition(":")
                    if sep:
                        val_str = next(iter(rest.split()), "")
                        if val_str.isdigit():
                            info[key.strip()] = int(val_str)
            total_kb = info.get("MemTotal", 1)
            avail_kb = info.get("MemAvailable", info.get("MemFree", total_kb // 2))
            free_mib = round(avail_kb / 1024.0, 1)
            mem_ratio = 1.0 - (avail_kb / max(total_kb, 1))

        sock_pressure = 0.05
        if os.path.exists("/proc/net/sockstat"):
            with open("/proc/net/sockstat", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("TCP:"):
                        it = iter(line.split())
                        for tok in it:
                            if tok == "inuse":
                                nxt = next(it, "0")
                                if nxt.isdigit():
                                    sock_pressure = min(int(nxt) / 1024.0, 2.0)
                                break

        return cpu_norm, mem_ratio, sock_pressure, free_mib

    def check_ports(self):
        port_map = {}
        for p in TARGET_PORTS:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.08)
            try:
                port_map[str(p)] = (s.connect_ex(("127.0.0.1", p)) == 0)
            except OSError:
                port_map[str(p)] = False
            finally:
                s.close()
        return port_map

    def compute_slope(self, vec):
        self.history.append(vec)
        if len(self.history) < 4:
            return 0.0, vec, "STABLE"

        it = reversed(self.history)
        v_now = next(it)
        v_prev = next(it)
        _ = next(it)
        v_old = next(it)

        d_now = math.sqrt(sum((a - b) ** 2 for a, b in zip(v_now, v_prev))) + 1e-9
        d_old = math.sqrt(sum((a - b) ** 2 for a, b in zip(v_prev, v_old))) + 1e-9
        drift_rate = math.log(d_now / d_old)

        velocity = tuple((a - b) for a, b in zip(v_now, v_prev))
        proj_5s = tuple(round(max(0.0, a + vel * 5.0), 4) for a, vel in zip(v_now, velocity))

        if drift_rate > 0.40 or max(proj_5s) > 0.90:
            gc.collect()
            status = "GC_RELIEF_TRIGGERED"
        elif drift_rate > 0.15:
            status = "LOAD_RISING"
        else:
            status = "STABLE"

        return round(drift_rate, 4), proj_5s, status

    def step(self):
        self.seq += 1
        now = time.time()
        cpu, mem, sock, free_mib = self.read_host_metrics()
        drift, proj, status = self.compute_slope((cpu, mem, sock))
        p_cpu, p_mem, p_sock = proj
        ports_up = self.check_ports()

        slot = (self.seq % RING_SLOTS) * FRAME_SIZE
        packed = struct.pack(FRAME_FMT, self.seq, now, cpu, mem, sock, drift)
        self.ring.seek(slot)
        self.ring.write(packed)

        h = hashlib.blake2b(digest_size=16)
        h.update(self.chain_hash + packed)
        self.chain_hash = h.digest()

        return {
            "seq": self.seq,
            "free_ram_mib": free_mib,
            "metrics": {
                "cpu_norm": round(cpu, 4),
                "mem_used_ratio": round(mem, 4),
                "tcp_sock_ratio": round(sock, 4),
            },
            "projected_5s": {
                "cpu": p_cpu,
                "mem": p_mem,
                "sock": p_sock,
            },
            "drift_log_ratio": drift,
            "status": status,
            "ports_online": ports_up,
            "blake2b_head": self.chain_hash.hex(),
        }


MONITOR = SharedMemoryMonitor()


def persist_state():
    try:
        with STATE_LOCK:
            snap = dict(LATEST_STATE)
        tmp = STATE_SAVE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        os.replace(tmp, STATE_SAVE_PATH)
    except OSError:
        pass


def worker_loop():
    global LATEST_STATE
    while True:
        snap = MONITOR.step()
        with STATE_LOCK:
            LATEST_STATE = snap
        if snap.get("seq", 0) % 20 == 0:
            persist_state()
        time.sleep(0.5)


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        with STATE_LOCK:
            payload = dict(LATEST_STATE)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def handle_exit(signum, frame):
    persist_state()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    threading.Thread(target=worker_loop, daemon=True).start()
    time.sleep(0.2)
    with ReusableTCPServer(("127.0.0.1", LISTEN_PORT), MetricsHandler) as httpd:
        print(f"[READY] Local SHM Monitor active on http://127.0.0.1:{LISTEN_PORT}")
        httpd.serve_forever()
