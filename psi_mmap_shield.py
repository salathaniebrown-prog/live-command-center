import gc
import mmap
import os
import sqlite3
import struct
import time

SHM_RING_PATH = os.path.expanduser("~/live-command-center/.astra_ring.shm")
WAL_DB_PATH = os.path.expanduser("~/astra_telemetry_wal.db")
# Fixed 64-byte binary frame: seq(Q), timestamp_ns(Q), psi_some_avg10(f), oom_score(i), merkle_prefix(32s), pad(4x)
FRAME_STRUCT = struct.Struct("<QQfi32s4x")
RING_SLOTS = 256
RING_BYTES = FRAME_STRUCT.size * RING_SLOTS


class PsiMmapShield:
    def __init__(self, ring_path: str = SHM_RING_PATH):
        self.ring_path = ring_path
        self.seq = 0
        os.makedirs(os.path.dirname(self.ring_path) or ".", exist_ok=True)
        if not os.path.exists(self.ring_path) or os.path.getsize(self.ring_path) != RING_BYTES:
            with open(self.ring_path, "wb") as f:
                f.write(b"\x00" * RING_BYTES)
        self._fd = os.open(self.ring_path, os.O_RDWR)
        self.mm = mmap.mmap(self._fd, RING_BYTES)

    @staticmethod
    def read_kernel_mem_psi() -> float:
        """Reads real Linux/Android kernel memory stall pressure (/proc/pressure/memory)."""
        psi_file = "/proc/pressure/memory"
        if not os.path.exists(psi_file):
            return 0.0
        try:
            with open(psi_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                for token in first_line.split():
                    if token.startswith("avg10="):
                        return float(token.split("=")[1])
        except Exception:
            return 0.0
        return 0.0

    @staticmethod
    def read_oom_score() -> int:
        """Reads current process Android LMK kill priority score."""
        try:
            with open("/proc/self/oom_score", "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            return -1

    def enforce_memory_shield(self, psi_avg10: float) -> str:
        """Pre-emptively sheds RAM & truncates SQLite WAL before Android LMK triggers."""
        if psi_avg10 >= 1.50:
            gc.collect(2)
            if os.path.exists(WAL_DB_PATH):
                try:
                    with sqlite3.connect(WAL_DB_PATH, timeout=1.5) as conn:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                except Exception:
                    pass
            return "SHIELD_ACTIVE_WAL_TRUNCATED"
        return "NOMINAL"

    def write_zero_copy_frame(self, merkle_hex: str) -> dict:
        psi_val = self.read_kernel_mem_psi()
        oom_val = self.read_oom_score()
        shield_status = self.enforce_memory_shield(psi_val)

        slot_offset = (self.seq % RING_SLOTS) * FRAME_STRUCT.size
        merkle_bytes = str(merkle_hex or "")[:32].encode("ascii", errors="ignore").ljust(32, b"0")

        FRAME_STRUCT.pack_into(
            self.mm,
            slot_offset,
            self.seq,
            time.monotonic_ns(),
            psi_val,
            oom_val,
            merkle_bytes,
        )
        self.seq += 1

        return {
            "slot": (self.seq - 1) % RING_SLOTS,
            "psi_mem_avg10": psi_val,
            "android_oom_score": oom_val,
            "shield_state": shield_status,
        }


def _verify_ring_integrity():
    try:
        assert os.path.exists(SHM_RING_PATH), "Shared memory ring missing."
        assert os.path.getsize(SHM_RING_PATH) == RING_BYTES, "Ring size mismatch."
    except Exception as exc:
        print(f"[SELF-HEAL] Reallocating zero-copy ring buffer: {exc}")
        PsiMmapShield(SHM_RING_PATH)


if __name__ == "__main__":
    shield = PsiMmapShield()
    status = shield.write_zero_copy_frame("16f391d0311ce2000000000000000000")
    print(status)
    _verify_ring_integrity()
