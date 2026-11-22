import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ctypes, gc, os, socketserver, struct, subprocess, threading, time
from astra_shm_schema import AstraBusFrame, FRAME_SIZE, MAGIC, RING_SLOTS, open_shm, open_ring

PORT = 8088
MM = open_shm(create=True)
RING = open_ring(create=True)
FRAME = AstraBusFrame.from_buffer(MM)
FRAME.magic = MAGIC
FRAME.version = 2

INGRESS_PKTS = 0
INGRESS_VAL = 0.0
CORES = os.cpu_count() or 4
ACTIVE_CORE = max(0, CORES - 1)
ACTUATIONS = 0
LAST_ACTUATE = 0.0

def pin_core(core_id):
    try:
        os.sched_setaffinity(0, {core_id})
        return True
    except Exception:
        return False

def read_mem():
    total, avail = 1, 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
                    break
    except OSError:
        pass
    return int(((total - avail) / max(total, 1)) * 1000), avail

def closed_loop_actuate(jitter_us, ram_pct):
    global ACTIVE_CORE, ACTUATIONS, LAST_ACTUATE
    now = time.monotonic()
    if now - LAST_ACTUATE < 5.0:
        return
    if jitter_us > 15000.0 or ram_pct >= 88.0:
        LAST_ACTUATE = now
        ACTUATIONS += 1
        # Rotate ingress core away from noisy neighbor
        ACTIVE_CORE = (ACTIVE_CORE - 1) % max(1, CORES)
        pin_core(ACTIVE_CORE)
        gc.collect()
        if os.geteuid() == 0:
            subprocess.Popen(
                ["sysctl", "-w", "net.core.netdev_max_backlog=4096"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

def hw_producer_loop():
    pin_core(ACTIVE_CORE)
    expected_dt_ns = 50_000_000  # 20 Hz (50ms)
    prev_ts = time.monotonic_ns()
    slot = 0
    while True:
        t0 = time.monotonic_ns()
        jitter_ns = abs((t0 - prev_ts) - expected_dt_ns)
        prev_ts = t0
        ram_x10, ram_avail = read_mem()

        closed_loop_actuate(jitter_ns / 1000.0, ram_x10 / 10.0)

        FRAME.seq += 1
        FRAME.ts_ns = t0
        FRAME.ptp_ns = time.time_ns()
        FRAME.cpu_pct_x10 = 0
        FRAME.ram_pct_x10 = ram_x10
        FRAME.ram_avail_kb = ram_avail
        FRAME.ingress_pkts = INGRESS_PKTS
        FRAME.ingress_val = INGRESS_VAL
        FRAME.jitter_ns = min(jitter_ns, 0xFFFFFFFF)
        FRAME.actuations = ACTUATIONS
        FRAME.pinned_core = ACTIVE_CORE
        FRAME.write_ns = time.monotonic_ns() - t0
        FRAME.seq += 1

        # Copy clean frame into lock-free persistent ring slot
        offset = (slot % RING_SLOTS) * FRAME_SIZE
        RING[offset:offset + FRAME_SIZE] = bytes(FRAME)
        slot += 1

        time.sleep(0.05)

class RawIngressHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global INGRESS_PKTS, INGRESS_VAL
        self.request.settimeout(1.0)
        try:
            data = self.request.recv(64)
            if len(data) == 8:
                INGRESS_VAL = struct.unpack("<d", data)[0]
                INGRESS_PKTS += 1
            self.request.sendall(bytes(MM[:FRAME_SIZE]))
        except OSError:
            pass

if __name__ == "__main__":
    threading.Thread(target=hw_producer_loop, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("127.0.0.1", PORT), RawIngressHandler).serve_forever()
