#!/usr/bin/env python3
import math
import os
import time

import requests

INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8000/api/v1/telemetry/ingest")
POLL_SECONDS = float(os.getenv("SIMULATION_INTERVAL_SECONDS", "0.5"))
SPEED_OF_SOUND_MPS = 340.29

SIMULATED_ASSETS = [
    {"target": "SIM_MACH_5", "base_lat": 34.05, "base_lng": -118.24, "mach": 5.0, "alt": 21000},
    {"target": "SIM_MACH_20", "base_lat": 9.36, "base_lng": 167.48, "mach": 20.0, "alt": 45000},
    {"target": "SIM_REENTRY", "base_lat": 28.57, "base_lng": -80.64, "mach": 25.0, "alt": 122000},
]


def build_payload(asset: dict, tick: int) -> dict:
    velocity_mps = asset["mach"] * SPEED_OF_SOUND_MPS
    phase = tick * 0.05
    lat_stride = (velocity_mps / 111_320.0) * math.sin(phase)
    cos_lat = max(abs(math.cos(math.radians(asset["base_lat"]))), 0.01)
    lng_stride = (velocity_mps / (111_320.0 * cos_lat)) * math.cos(phase)

    return {
        "target": asset["target"],
        "lat": asset["base_lat"] + lat_stride,
        "lng": asset["base_lng"] + lng_stride,
        "alt": asset["alt"],
        "dataClass": "simulation",
        "synthetic": True,
        "network_mode": "SIMULATION_ONLY",
        "telemetry_metrics": {
            "mach_rating": asset["mach"],
            "velocity_mps": round(velocity_mps, 2),
        },
        "provenance": {
            "source": "eagle-eyes-hyper-velocity-simulator",
            "method": "deterministic-generated-track",
        },
        "timestamp": time.time(),
    }


def main() -> None:
    tick = 0
    print("Eagle Eyes hyper-velocity simulator: SYNTHETIC DATA ONLY")
    while True:
        for asset in SIMULATED_ASSETS:
            payload = build_payload(asset, tick)
            try:
                response = requests.post(INGEST_URL, json=payload, timeout=2)
                response.raise_for_status()
                print(f"SIMULATION {asset['target']} -> {response.status_code}")
            except requests.RequestException as exc:
                print(f"SIMULATION ingest unavailable: {exc}")
        tick += 1
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
