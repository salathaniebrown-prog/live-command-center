"""LIVE NVIDIA GPU telemetry collector for Eagle Eyes.

Observation-only: reads hardware state with nvidia-smi and writes the latest
snapshot atomically to EAGLE_EYES_METRICS_FILE. No simulated values are emitted.
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("EagleEyesGpuTelemetry")

METRICS_FILE_PATH = Path(
    os.getenv("EAGLE_EYES_METRICS_FILE", "/app/live-metrics.json")
)
POLL_SECONDS = max(0.5, float(os.getenv("EAGLE_EYES_GPU_POLL_SECONDS", "2")))
COMMAND_TIMEOUT_SECONDS = max(
    0.5, float(os.getenv("EAGLE_EYES_GPU_TIMEOUT_SECONDS", "2"))
)

NVIDIA_QUERY = (
    "index,uuid,name,utilization.gpu,memory.used,memory.total,"
    "temperature.gpu,power.draw"
)


def parse_float(value: str):
    value = (value or "").strip()
    lowered = value.lower()
    if not value or lowered == "n/a" or "not supported" in lowered:
        return None
    return float(value)


def parse_int(value: str):
    parsed = parse_float(value)
    return None if parsed is None else int(parsed)


def parse_mib_to_bytes(value: str):
    parsed = parse_float(value)
    return None if parsed is None else int(parsed * 1024 * 1024)


def parse_nvidia_row(line: str) -> dict:
    fields = [value.strip() for value in line.split(",")]
    if len(fields) != 8:
        raise ValueError(f"unexpected NVIDIA row with {len(fields)} fields: {line!r}")

    (
        gpu_index,
        gpu_uuid,
        gpu_name,
        utilization,
        memory_used,
        memory_total,
        temperature,
        power,
    ) = fields

    return {
        "gpu_index": parse_int(gpu_index),
        "gpu_uuid": gpu_uuid or None,
        "gpu_name": gpu_name or None,
        "utilization_percent": parse_float(utilization),
        "memory_used_bytes": parse_mib_to_bytes(memory_used),
        "memory_total_bytes": parse_mib_to_bytes(memory_total),
        "temperature_celsius": parse_float(temperature),
        "power_draw_watts": parse_float(power),
    }


def build_snapshot(rows, sequence_id: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    gpus = [parse_nvidia_row(row) for row in rows if row.strip()]
    return {
        "action_bundle": "gpu_hardware_telemetry",
        "authority": "observation",
        "commandEligible": False,
        "status": "LIVE" if gpus else "UNAVAILABLE",
        "sequence_id": sequence_id,
        "timestamp": now,
        "source": "nvidia-smi",
        "gpu_count": len(gpus),
        "gpus": gpus,
    }


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, separators=(",", ":"), allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp_name = handle.name
    os.replace(tmp_name, path)


async def query_nvidia_smi() -> list[str]:
    proc = await asyncio.create_subprocess_exec(
        "nvidia-smi",
        f"--query-gpu={NVIDIA_QUERY}",
        "--format=csv,noheader,nounits",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=COMMAND_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        if proc.returncode is None:
            proc.kill()
            await proc.communicate()
        raise

    if proc.returncode != 0:
        message = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"nvidia-smi failed with rc={proc.returncode}: {message}")

    return stdout.decode(errors="replace").splitlines()


async def run_gpu_telemetry_loop() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger.info(
        "Initializing LIVE NVIDIA telemetry metrics_file=%s poll=%.1fs",
        METRICS_FILE_PATH,
        POLL_SECONDS,
    )

    sequence_id = 0
    while True:
        try:
            rows = await query_nvidia_smi()
            sequence_id += 1
            snapshot = build_snapshot(rows, sequence_id)
            atomic_write_json(METRICS_FILE_PATH, snapshot)
            logger.info(
                "GPU telemetry LIVE sequence=%d gpu_count=%d",
                sequence_id,
                snapshot["gpu_count"],
            )
        except FileNotFoundError:
            logger.error("nvidia-smi is missing inside the GPU telemetry container")
        except asyncio.TimeoutError:
            logger.error("nvidia-smi telemetry timeout after %.1fs", COMMAND_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("GPU telemetry ingestion failed")

        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(run_gpu_telemetry_loop())
    except KeyboardInterrupt:
        logger.info("GPU telemetry stopped")
