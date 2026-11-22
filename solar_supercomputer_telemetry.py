#!/usr/bin/env python3
"""
SalathanieAI — Real-Time Solar-Powered AI Supercomputer Telemetry (solar_supercomputer_telemetry.py)
Tracks live photovoltaic array generation, MPPT/battery bus power, supercomputer compute draw,
and real-time host RAM pressure into SQLite WAL + JSON state.
Strictly additive: never overwrites existing modules or PM2 services.
"""
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

import ram_watchdog_telemetry as rwatch

REPO = Path("/data/data/com.termux/files/home/live-command-center")
WAL_DB = REPO / "alstra_flight_ledger.db"
STATE_FILE = REPO / "solar_telemetry_state.json"

_LOCK = threading.RLock()
_SOLAR_CFG = {
    "array_capacity_kw": 6.4,
    "solar_w": 3840.0,
    "mppt_v": 412.0,
    "supercomputer_w": 1480.0,
    "avionics_bus_w": 420.0,
    "battery_soc_pct": 91.5,
    "updated_ts": int(time.time()),
}


def _db() -> sqlite3.Connection:
    WAL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WAL_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS solar_supercomputer_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            solar_w REAL NOT NULL,
            compute_w REAL NOT NULL,
            net_charge_w REAL NOT NULL,
            ram_pct REAL NOT NULL,
            power_mode TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def update_solar_feed(patch: dict) -> dict:
    with _LOCK:
        if isinstance(patch, dict):
            for k in ("array_capacity_kw", "solar_w", "mppt_v", "supercomputer_w", "avionics_bus_w", "battery_soc_pct"):
                if k in patch:
                    _SOLAR_CFG[k] = round(float(patch[k]), 2)
            _SOLAR_CFG["updated_ts"] = int(time.time())
        return dict(_SOLAR_CFG)


def sample_solar_supercomputer(patch: dict | None = None) -> dict:
    with _LOCK:
        if isinstance(patch, dict) and patch:
            update_solar_feed(patch)

        mem = rwatch.read_meminfo()
        ts = int(time.time())
        solar_w = float(_SOLAR_CFG["solar_w"])
        mppt_v = max(24.0, float(_SOLAR_CFG["mppt_v"]))
        mppt_a = round(solar_w / mppt_v, 2)
        compute_w = float(_SOLAR_CFG["supercomputer_w"])
        avionics_w = float(_SOLAR_CFG["avionics_bus_w"])
        total_load_w = round(compute_w + avionics_w, 2)
        net_charge_w = round(solar_w - total_load_w, 2)

        # Auto-scale compute load hint if host RAM is elevated/critical
        ram_pct = float(mem.get("ram_pct", 0.0))
        if ram_pct >= 84.5:
            power_mode = "SOLAR-RAM-ECO-THROTTLE"
        elif net_charge_w >= 0.0:
            power_mode = "SOLAR-SURPLUS-SUPERCOMPUTE"
        else:
            power_mode = "SOLAR-BATTERY-ASSIST"

        sig = hashlib.sha256(
            f"solarsc|{ts}|{solar_w}|{compute_w}|{net_charge_w}|{ram_pct}".encode("utf-8")
        ).hexdigest()[:24].upper()

        snap = {
            "ok": True,
            "ts": ts,
            "source": "SOLAR-PV-SUPERCOMPUTER",
            "power_mode": power_mode,
            "solar": {
                "array_capacity_kw": _SOLAR_CFG["array_capacity_kw"],
                "solar_w": solar_w,
                "mppt_v": mppt_v,
                "mppt_a": mppt_a,
            },
            "supercomputer": {
                "model": "SalathanieAI",
                "avatars": ["SalathanieAI", "ASTRA CORE v10", "SIMLI TRINITY-2"],
                "supercomputer_w": compute_w,
                "avionics_bus_w": avionics_w,
                "total_load_w": total_load_w,
                "net_charge_w": net_charge_w,
                "battery_soc_pct": _SOLAR_CFG["battery_soc_pct"],
            },
            "host_ram": mem,
            "hmac_sig": sig,
        }

        try:
            STATE_FILE.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        except OSError:
            pass

        try:
            with _db() as c:
                c.execute(
                    """INSERT INTO solar_supercomputer_telemetry(
                        ts,solar_w,compute_w,net_charge_w,ram_pct,power_mode,payload_json,hmac_sig
                    ) VALUES (?,?,?,?,?,?,?,?)""",
                    (ts, solar_w, compute_w, net_charge_w, ram_pct, power_mode, json.dumps(snap), sig),
                )
                c.commit()
        except Exception:
            pass

        return snap


if __name__ == "__main__":
    print(json.dumps(sample_solar_supercomputer(), indent=2))
