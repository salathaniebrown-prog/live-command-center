import os
import struct
import time
from psi_mmap_shield import PsiMmapShield, SHM_RING_PATH, FRAME_STRUCT, RING_SLOTS


class GatewayShmTelemetry:
    def __init__(self):
        self.shield = PsiMmapShield(SHM_RING_PATH)

    def emit_tick(self, merkle_root: str) -> dict:
        """Zero-copy telemetry write + kernel PSI eviction protection."""
        return self.shield.write_zero_copy_frame(merkle_root)

    def read_latest_frame(self) -> dict:
        """Reads the newest 64-byte binary frame directly from mmap without JSON overhead."""
        latest_seq = -1
        latest_data = None
        for slot in range(RING_SLOTS):
            offset = slot * FRAME_STRUCT.size
            seq, ts_ns, psi_val, oom_val, merkle_bytes = FRAME_STRUCT.unpack_from(self.shield.mm, offset)
            if ts_ns > 0 and seq >= latest_seq:
                latest_seq = seq
                latest_data = {
                    "seq": seq,
                    "monotonic_ns": ts_ns,
                    "psi_mem_avg10": round(psi_val, 4),
                    "android_oom_score": oom_val,
                    "merkle_prefix": merkle_bytes.decode("ascii", errors="ignore").rstrip("0"),
                }
        return latest_data or {"status": "RING_EMPTY"}


def _verify_gateway_shm():
    bus = GatewayShmTelemetry()
    probe = bus.emit_tick("8090gatewaysync000000000000000000")
    assert "psi_mem_avg10" in probe, "SHM bus write failed"


if __name__ == "__main__":
    _verify_gateway_shm()
    print("[SHM HOOK OK] Gateway zero-copy bus verified.")
