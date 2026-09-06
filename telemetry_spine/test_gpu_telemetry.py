import json
import tempfile
import unittest
from pathlib import Path

from gpu_telemetry import (
    atomic_write_json,
    build_snapshot,
    parse_float,
    parse_mib_to_bytes,
    parse_nvidia_row,
)


class GpuTelemetryTests(unittest.TestCase):
    def test_parse_float_handles_unavailable_values(self):
        self.assertIsNone(parse_float("N/A"))
        self.assertIsNone(parse_float("[Not Supported]"))
        self.assertIsNone(parse_float(""))
        self.assertEqual(parse_float("42.5"), 42.5)

    def test_parse_mib_to_bytes(self):
        self.assertEqual(parse_mib_to_bytes("1"), 1024 * 1024)
        self.assertIsNone(parse_mib_to_bytes("N/A"))

    def test_parse_nvidia_row(self):
        row = "0, GPU-123, NVIDIA H100 80GB HBM3, 71, 2048, 81920, 63, 312.50"
        parsed = parse_nvidia_row(row)
        self.assertEqual(parsed["gpu_index"], 0)
        self.assertEqual(parsed["gpu_uuid"], "GPU-123")
        self.assertEqual(parsed["gpu_name"], "NVIDIA H100 80GB HBM3")
        self.assertEqual(parsed["utilization_percent"], 71.0)
        self.assertEqual(parsed["memory_used_bytes"], 2048 * 1024 * 1024)
        self.assertEqual(parsed["memory_total_bytes"], 81920 * 1024 * 1024)
        self.assertEqual(parsed["temperature_celsius"], 63.0)
        self.assertEqual(parsed["power_draw_watts"], 312.5)

    def test_snapshot_is_observation_only(self):
        snapshot = build_snapshot(
            ["0, GPU-123, NVIDIA H100, 50, 1024, 81920, 55, N/A"],
            7,
        )
        self.assertEqual(snapshot["status"], "LIVE")
        self.assertEqual(snapshot["sequence_id"], 7)
        self.assertEqual(snapshot["authority"], "observation")
        self.assertFalse(snapshot["commandEligible"])
        self.assertEqual(snapshot["source"], "nvidia-smi")
        self.assertIsNone(snapshot["gpus"][0]["power_draw_watts"])

    def test_atomic_write_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live-metrics.json"
            atomic_write_json(path, {"status": "LIVE", "gpu_count": 1})
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"status": "LIVE", "gpu_count": 1},
            )


if __name__ == "__main__":
    unittest.main()
