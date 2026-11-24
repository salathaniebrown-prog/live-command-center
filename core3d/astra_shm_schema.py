import ctypes, mmap, os, pathlib

SHM_DIR = pathlib.Path(os.environ.get("TMPDIR", str(pathlib.Path.home())))
SHM_PATH = SHM_DIR / "astra_shm_bus.bin"
RING_PATH = SHM_DIR / "astra_shm_ring.bin"
MAGIC = 0x41535452  # 'ASTR'
RING_SLOTS = 512

class AstraBusFrame(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("magic",        ctypes.c_uint32),  # 4B  - Signature
        ("version",      ctypes.c_uint32),  # 4B  - Schema v2
        ("seq",          ctypes.c_uint64),  # 8B  - Seqlock counter
        ("ts_ns",        ctypes.c_uint64),  # 8B  - Monotonic ns
        ("ptp_ns",       ctypes.c_uint64),  # 8B  - Realtime PTP ns
        ("cpu_pct_x10",  ctypes.c_uint32),  # 4B  - CPU % * 10
        ("ram_pct_x10",  ctypes.c_uint32),  # 4B  - RAM % * 10
        ("ram_avail_kb", ctypes.c_uint64),  # 8B  - Available RAM KB
        ("net_rx_bytes", ctypes.c_uint64),  # 8B  - Socket RX
        ("net_tx_bytes", ctypes.c_uint64),  # 8B  - Socket TX
        ("ingress_pkts", ctypes.c_uint64),  # 8B  - Raw :8088 packets
        ("ingress_val",  ctypes.c_double),  # 8B  - Last sensor float64
        ("write_ns",     ctypes.c_uint32),  # 4B  - Write latency ns
        ("jitter_ns",    ctypes.c_uint32),  # 4B  - Inter-frame jitter ns
        ("actuations",   ctypes.c_uint32),  # 4B  - Closed-loop kernel/core actions
        ("pinned_core",  ctypes.c_uint32),  # 4B  - Active CPU core ID
        ("reserved",     ctypes.c_uint8 * 40),  # 128-byte aligned frame
    ]

FRAME_SIZE = ctypes.sizeof(AstraBusFrame)
RING_BYTES = FRAME_SIZE * RING_SLOTS

def open_shm(create=False):
    flags = os.O_RDWR | (os.O_CREAT if create else 0)
    fd = os.open(str(SHM_PATH), flags, 0o600)
    if create or os.fstat(fd).st_size < FRAME_SIZE:
        os.ftruncate(fd, FRAME_SIZE)
    mm = mmap.mmap(fd, FRAME_SIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
    os.close(fd)
    return mm

def open_ring(create=False):
    flags = os.O_RDWR | (os.O_CREAT if create else 0)
    fd = os.open(str(RING_PATH), flags, 0o600)
    if create or os.fstat(fd).st_size < RING_BYTES:
        os.ftruncate(fd, RING_BYTES)
    mm = mmap.mmap(fd, RING_BYTES, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
    os.close(fd)
    return mm

def read_frame_lockfree(mm, max_spins=64):
    view = AstraBusFrame.from_buffer(mm)
    for _ in range(max_spins):
        s1 = view.seq
        if s1 & 1:
            continue
        snap = AstraBusFrame.from_buffer_copy(mm, 0)
        s2 = view.seq
        if s1 == s2 and snap.magic == MAGIC:
            return snap
    return AstraBusFrame.from_buffer_copy(mm, 0)

def read_ring_snapshot(limit=128):
    if not RING_PATH.exists():
        return []
    mm = open_ring(create=False)
    frames = []
    try:
        for i in range(RING_SLOTS):
            f = AstraBusFrame.from_buffer_copy(mm, i * FRAME_SIZE)
            if f.magic == MAGIC and f.seq > 0:
                frames.append({
                    "seq": f.seq, "ptp_ns": f.ptp_ns, "ram_pct": f.ram_pct_x10 / 10.0,
                    "write_us": round(f.write_ns / 1000.0, 2),
                    "jitter_us": round(f.jitter_ns / 1000.0, 2),
                    "pkts": f.ingress_pkts, "val": f.ingress_val,
                    "core": f.pinned_core, "actuations": f.actuations
                })
    finally:
        mm.close()
    frames.sort(key=lambda x: x["seq"])
    return frames[-limit:]
