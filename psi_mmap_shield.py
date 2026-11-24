import mmap
import os
import struct
import sys
import time
from ram_reclaimer_daemon import force_kernel_ram_release

SHM_RING_PATH = os.path.expanduser("~/live-command-center/.astra_ring.shm")
FREE_RAM_FLOOR_MB = 550.0
# Fixed 64-byte binary frame: seq(Q), timestamp_ns(Q), psi_some_avg10(f), oom_score(i), merkle_prefix(32s), pad(4x)
FRAME_STRUCT = struct.Struct("<QQfi32s4x")
RING_SLOTS = 256
RING_BYTES = FRAME_STRUCT.size * RING_SLOTS


class PsiMmapShield:
    __slots__ = ("ring_path", "seq", "_fd", "mm")

    def __init__(self, ring_path: str = SHM_RING_PATH):
        self.ring_path = sys.intern(ring_path)
        self.seq = 0
        os.makedirs(os.path.dirname(self.ring_path) or ".", exist_ok=True)
        if not os.path.exists(self.ring_path) or os.path.getsize(self.ring_path) != RING_BYTES:
            with open(self.ring_path, "wb") as f:
                f.write(b"\x00" * RING_BYTES)
        self._fd = os.open(self.ring_path, os.O_RDWR)
        self.mm = mmap.mmap(self._fd, RING_BYTES)

    @staticmethod
    def read_available_ram_mb() -> float:
        """Reads exact kernel MemAvailable in MB from /proc/meminfo."""
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        kb = int(line.split()[1])
                        return round(kb / 1024.0, 2)
        except Exception:
            pass
        return 9999.0

    @staticmethod
    def read_kernel_mem_psi() -> float:
        psi_file = "/proc/pressure/memory"
        if not os.path.exists(psi_file):
            return 0.0
        try:
            with open(psi_file, "r", encoding="utf-8") as f:
                for token in f.readline().strip().split():
                    if token.startswith("avg10="):
                        return float(token.split("=")[1])
        except Exception:
            return 0.0
        return 0.0

    @staticmethod
    def read_oom_score() -> int:
        try:
            with open("/proc/self/oom_score", "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            return -1

    def enforce_memory_shield(self, psi_avg10: float, avail_mb: float) -> str:
        """Fires native libc malloc_trim + WAL truncation if free RAM < 550 MB or PSI >= 1.50."""
        if avail_mb < FREE_RAM_FLOOR_MB or psi_avg10 >= 1.50:
            reclaim_stats = force_kernel_ram_release()
            return sys.intern(f"SHIELD_RECLAIMED_{reclaim_stats['reclaimed_mb']}MB")
        return sys.intern("NOMINAL")

    def write_zero_copy_frame(self, merkle_hex: str) -> dict:
        psi_val = self.read_kernel_mem_psi()
        oom_val = self.read_oom_score()
        avail_mb = self.read_available_ram_mb()
        shield_status = self.enforce_memory_shield(psi_val, avail_mb)

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
            "avail_ram_mb": avail_mb,
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
    _verify_ring_integrity()
    shield = PsiMmapShield()
    print(shield.write_zero_copy_frame("550mbfloorverified00000000000000"))
