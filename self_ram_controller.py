#!/usr/bin/env python3
"""
SalathanieAI — Self-Control Coding & Memory Budget Governor (self_ram_controller.py)
Enforces per-process RSS self-caps, tracks RAM climb rate, and throttles non-core
workers when system RAM crosses the self-control ceiling (83.0%).
Additive-only: never modifies or removes existing files or core services.
"""
import hashlib
import json
import sqlite3
import subprocess
import time
from pathlib import Path

import ram_watchdog_telemetry as rwatch

REPO = Path("/data/data/com.termux/files/home/live-command-center")
WAL_DB = REPO / "alstra_flight_ledger.db"

SELF_CEILING_PCT = 83.0
WORKER_RSS_CAP_MB = 24.0
PROTECTED_NAMES = {
    "salathanie-pilot",
    "salathanie-guard",
    "salathanie-gw-8090",
    "astra-8088-dashboard_server",
    "salathanie-self-heal",
    "salathanie-ram-watch",
    "salathanie-wal-8125",
    "salathanie-tunnel",
    "astra-8088-main",
    "astra-8095-spine",
    "astra-8099-brain",
    "astra-8151-core",
}

_LAST_SAMPLE = {"ts": 0, "ram_pct": 0.0}


def _db() -> sqlite3.Connection:
    WAL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WAL_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS self_control_budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            ram_pct REAL NOT NULL,
            slope_pct_min REAL NOT NULL,
            policy TEXT NOT NULL,
            throttled_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def enforce_self_control() -> dict:
    global _LAST_SAMPLE
    mem = rwatch.read_meminfo()
    now = mem["ts"]
    pct = mem["ram_pct"]

    dt_min = max((now - _LAST_SAMPLE["ts"]) / 60.0, 0.05) if _LAST_SAMPLE["ts"] else 1.0
    slope = round((pct - _LAST_SAMPLE["ram_pct"]) / dt_min, 3) if _LAST_SAMPLE["ts"] else 0.0
    _LAST_SAMPLE = {"ts": now, "ram_pct": pct}

    procs = rwatch._pm2_procs()
    throttled = []

    if pct >= SELF_CEILING_PCT or slope > 2.5:
        policy = "SELF_THROTTLE_ACTIVE"
        for p in sorted(procs, key=lambda x: x["mem_mb"], reverse=True):
            nm = p["name"]
            if p["status"] == "online" and nm not in PROTECTED_NAMES and p["mem_mb"] >= WORKER_RSS_CAP_MB:
                rc = subprocess.run(["pm2", "stop", nm], capture_output=True, text=True, timeout=6)
                if rc.returncode == 0:
                    throttled.append({"name": nm, "freed_est_mb": p["mem_mb"], "reason": "rss_cap_or_ceiling"})
    else:
        policy = "SELF_GOVERNED_NOMINAL"

    sig = hashlib.sha256(f"sc|{now}|{pct}|{slope}|{len(throttled)}".encode("utf-8")).hexdigest()[:24].upper()
    with _db() as c:
        c.execute(
            "INSERT INTO self_control_budget(ts,ram_pct,slope_pct_min,policy,throttled_json,hmac_sig) VALUES (?,?,?,?,?,?)",
            (now, pct, slope, policy, json.dumps(throttled), sig),
        )
        c.commit()

    return {
        "ok": True,
        "ts": now,
        "policy": policy,
        "ceiling_pct": SELF_CEILING_PCT,
        "worker_rss_cap_mb": WORKER_RSS_CAP_MB,
        "mem": mem,
        "slope_pct_min": slope,
        "throttled": throttled,
        "hmac_sig": sig,
    }


if __name__ == "__main__":
    print(json.dumps(enforce_self_control(), indent=2))
