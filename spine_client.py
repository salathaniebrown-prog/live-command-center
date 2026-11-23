#!/usr/bin/env python3
"""Zero-dependency non-blocking telemetry spine client for :8159."""
import http.client
import json
import threading
import time


def _post_worker(payload: dict) -> None:
    try:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", 8159, timeout=0.8)
        conn.request("POST", "/api/telemetry/spine", body=body, headers={"Content-Type": "application/json"})
        conn.getresponse().read()
        conn.close()
    except Exception:
        pass


def push_spine_frame(craft_id: str = "S-ZERO-PLUS-01", altitude_ft: float = 0.0, airspeed_kts: float = 0.0, battery_pct: float = 100.0, rotor_rpm: int = 0, extra: dict | None = None) -> None:
    frame = {
        "ts": time.time(),
        "craft_id": craft_id,
        "altitude_ft": altitude_ft,
        "airspeed_kts": airspeed_kts,
        "battery_pct": battery_pct,
        "rotor_rpm": rotor_rpm,
    }
    if extra:
        frame.update(extra)
    threading.Thread(target=_post_worker, args=(frame,), daemon=True).start()
