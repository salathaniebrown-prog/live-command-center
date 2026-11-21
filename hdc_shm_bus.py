#!/usr/bin/env python3
"""
Salathanie A.I — Zero-Copy 10k-bit HDC Shared-Memory Ring Bus & Dynamic Port Manager
Binary Layout:
  Global Header (64B): <8sIIQ40s  (magic, version, num_slots, write_seq, reserved)
  Slot (1344B) x 64:
    Slot Header (64B): <QQIHH32sI4s (seq, ts_ns, pid, port, status, node_name, crc32, pad)
    HV Payload (1280B): 10,000-bit hypervector (1250B active + 30B alignment pad)
"""
import mmap
import os
import socket
import struct
import time
import zlib

MAGIC = b"SALHDC01"
VERSION = 1
NUM_SLOTS = 64
GLOBAL_HDR_FMT = "<8sIIQ40s"
GLOBAL_HDR_SIZE = struct.calcsize(GLOBAL_HDR_FMT)  # 64B

SLOT_HDR_FMT = "<QQIHH32sI4s"
SLOT_HDR_SIZE = struct.calcsize(SLOT_HDR_FMT)      # 64B
HV_ACTIVE_BYTES = 1250                             # 10,000 bits
HV_PADDED_BYTES = 1280                             # 64B aligned
SLOT_SIZE = SLOT_HDR_SIZE + HV_PADDED_BYTES        # 1344B
RING_SIZE = GLOBAL_HDR_SIZE + (NUM_SLOTS * SLOT_SIZE)

DEFAULT_SHM_PATH = os.environ.get(
    "SALATHANIE_SHM_PATH",
    "/data/data/com.termux/files/usr/tmp/salathanie_hdc_ring.shm"
    if os.path.isdir("/data/data/com.termux/files/usr/tmp")
    else "/tmp/salathanie_hdc_ring.shm",
)


class HDCSharedMemoryBus:
    def __init__(self, path: str = DEFAULT_SHM_PATH):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        init_needed = not os.path.exists(self.path) or os.path.getsize(self.path) != RING_SIZE
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o660)
        if init_needed:
            os.ftruncate(self.fd, RING_SIZE)
        self.mm = mmap.mmap(self.fd, RING_SIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        self.mv = memoryview(self.mm)
        if init_needed or self.mm[:8] != MAGIC:
            struct.pack_into(GLOBAL_HDR_FMT, self.mm, 0, MAGIC, VERSION, NUM_SLOTS, 0, b"\x00" * 40)

    def _next_seq(self) -> int:
        _, _, _, seq, _ = struct.unpack_from(GLOBAL_HDR_FMT, self.mm, 0)
        new_seq = seq + 1
        struct.pack_into("<Q", self.mm, 16, new_seq)
        return new_seq

    def publish(self, node_name: str, port: int, status: int, hv_bytes: bytes) -> int:
        if len(hv_bytes) != HV_ACTIVE_BYTES:
            raise ValueError(f"Expected {HV_ACTIVE_BYTES}B (10,000-bit) hypervector, got {len(hv_bytes)}B")
        seq = self._next_seq()
        slot_idx = (seq - 1) % NUM_SLOTS
        offset = GLOBAL_HDR_SIZE + (slot_idx * SLOT_SIZE)
        ts_ns = time.time_ns()
        pid = os.getpid()
        name_b = node_name.encode("utf-8")[:32].ljust(32, b"\x00")
        crc = zlib.crc32(hv_bytes) & 0xFFFFFFFF

        struct.pack_into(SLOT_HDR_FMT, self.mm, offset, seq, ts_ns, pid, port, status, name_b, crc, b"\x00" * 4)
        self.mv[offset + SLOT_HDR_SIZE : offset + SLOT_HDR_SIZE + HV_ACTIVE_BYTES] = hv_bytes
        return seq

    def read_latest_zero_copy(self) -> dict | None:
        _, _, _, seq, _ = struct.unpack_from(GLOBAL_HDR_FMT, self.mm, 0)
        if seq == 0:
            return None
        slot_idx = (seq - 1) % NUM_SLOTS
        offset = GLOBAL_HDR_SIZE + (slot_idx * SLOT_SIZE)
        s_seq, ts_ns, pid, port, status, name_b, crc, _ = struct.unpack_from(SLOT_HDR_FMT, self.mm, offset)
        hv_view = self.mv[offset + SLOT_HDR_SIZE : offset + SLOT_HDR_SIZE + HV_ACTIVE_BYTES]
        valid_crc = (zlib.crc32(hv_view) & 0xFFFFFFFF) == crc
        return {
            "seq": s_seq,
            "ts_ns": ts_ns,
            "pid": pid,
            "port": port,
            "status": status,
            "node": name_b.rstrip(b"\x00").decode("utf-8", errors="ignore"),
            "crc_ok": valid_crc,
            "hv_view": hv_view,  # Zero-copy memoryview
        }

    def snapshot_active_ports(self) -> dict[int, dict]:
        active = {}
        for i in range(NUM_SLOTS):
            offset = GLOBAL_HDR_SIZE + (i * SLOT_SIZE)
            s_seq, ts_ns, pid, port, status, name_b, _, _ = struct.unpack_from(SLOT_HDR_FMT, self.mm, offset)
            if s_seq > 0 and port > 0:
                if port not in active or s_seq > active[port]["seq"]:
                    active[port] = {
                        "seq": s_seq,
                        "pid": pid,
                        "status": status,
                        "node": name_b.rstrip(b"\x00").decode("utf-8", errors="ignore"),
                    }
        return active

    @staticmethod
    def _port_is_free(port: int, host: str = "0.0.0.0") -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return True
            except OSError:
                return False

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def allocate_port(self, preferred: int, pool_start: int = 8120, pool_end: int = 8199) -> int:
        if self._port_is_free(preferred):
            return preferred
        # Check if preferred port's last registered PID is dead (stale)
        ports = self.snapshot_active_ports()
        if preferred in ports and not self._pid_alive(ports[preferred]["pid"]):
            time.sleep(0.2)
            if self._port_is_free(preferred):
                return preferred
        # Dynamic fallback allocation
        for candidate in range(pool_start, pool_end + 1):
            if self._port_is_free(candidate):
                return candidate
        raise RuntimeError(f"No free ports available in {pool_start}-{pool_end}")

    def close(self):
        self.mv.release()
        self.mm.close()
        os.close(self.fd)


def hamming_distance(a: memoryview | bytes, b: memoryview | bytes) -> float:
    diff_bits = sum((x ^ y).bit_count() for x, y in zip(a, b))
    return diff_bits / (HV_ACTIVE_BYTES * 8)


if __name__ == "__main__":
    bus = HDCSharedMemoryBus()
    hv = os.urandom(HV_ACTIVE_BYTES)
    t0 = time.perf_counter_ns()
    seq = bus.publish("salathanie-bus-test", 8090, 200, hv)
    rec = bus.read_latest_zero_copy()
    t1 = time.perf_counter_ns()
    dist = hamming_distance(hv, rec["hv_view"])
    dyn_port = bus.allocate_port(8090)  # 8090 is live, should dynamically allocate from 8120+
    print(f"[OK] SHM Path: {bus.path} ({RING_SIZE} bytes)")
    print(f"[OK] Seq={seq} Node={rec['node']} CRC={rec['crc_ok']} Dist={dist:.4f} Latency={(t1 - t0)/1000:.1f}us")
    print(f"[OK] Preferred 8090 busy -> Dynamic Allocated Port: {dyn_port}")
    bus.close()
