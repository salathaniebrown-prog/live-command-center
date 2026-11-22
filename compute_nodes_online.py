#!/usr/bin/env python3
"""
SalathanieAI — Online Compute Nodes Telemetry & Registry (compute_nodes_online.py)
Tracks active compute nodes, ports, avatar engines, and live RAM state in SQLite WAL.
Strictly additive: never overwrites existing scripts or PM2 services.
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path

import ram_watchdog_telemetry as rwatch

REPO = Path("/data/data/com.termux/files/home/live-command-center")
WAL_DB = REPO / "alstra_flight_ledger.db"

COMPUTE_NODES = [
    {"node_id": "node-salathanie-ai", "label": "SalathanieAI Supercomputer", "port": 8125, "role": "Primary Orchestrator & Flying Car Bus"},
    {"node_id": "node-astra-core-v10", "label": "ASTRA CORE v10", "port": 8099, "role": "Cockpit Neural Avatar & Brain Core"},
    {"node_id": "node-simli-trinity-2", "label": "SIMLI TRINITY-2", "port": 8095, "role": "Live Motion & Cabin Screen Feed"},
    {"node_id": "node-gw-8090", "label": "Unified Gateway :8090", "port": 8090, "role": "Spatial & Telemetry Gateway"},
    {"node_id": "node-ingress-8088", "label": "Ingress Bus :8088", "port": 8088, "role": "Telemetry & Event Ingress"},
    {"node_id": "node-twin-8151", "label": "Spatial Twin :8151", "port": 8151, "role": "3D Twin & GIS Projection"},
    {"node_id": "node-ram-guard", "label": "Self-RAM Watchdog", "port": 0, "role": "Memory Telemetry & Auto-Throttle"},
]


def _db() -> sqlite3.Connection:
    WAL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WAL_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compute_node_heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            online_count INT NOT NULL,
            ram_pct REAL NOT NULL,
            nodes_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def sync_compute_nodes() -> dict:
    ts = int(time.time())
    mem = rwatch.read_meminfo()
    pm2_map = {p["name"]: p for p in rwatch._pm2_procs()}

    active_nodes = []
    for n in COMPUTE_NODES:
        status = "ONLINE"
        if n["node_id"] == "node-ram-guard":
            w = pm2_map.get("salathanie-ram-watch")
            status = "ONLINE" if (w and w["status"] == "online") else "STANDBY"
        elif n["port"] == 8125:
            p = pm2_map.get("salathanie-pilot")
            status = "ONLINE" if (p and p["status"] == "online") else "STANDBY"
        elif n["port"] == 8090:
            p = pm2_map.get("salathanie-gw-8090")
            status = "ONLINE" if (p and p["status"] == "online") else "STANDBY"
        active_nodes.append({**n, "status": status})

    online_count = sum(1 for x in active_nodes if x["status"] == "ONLINE")
    sig = hashlib.sha256(f"cnode|{ts}|{online_count}|{mem['ram_pct']}".encode("utf-8")).hexdigest()[:24].upper()

    with _db() as c:
        c.execute(
            "INSERT INTO compute_node_heartbeats(ts,online_count,ram_pct,nodes_json,hmac_sig) VALUES (?,?,?,?,?)",
            (ts, online_count, mem["ram_pct"], json.dumps(active_nodes), sig),
        )
        c.commit()

    return {
        "ok": True,
        "ts": ts,
        "online_count": online_count,
        "total_nodes": len(active_nodes),
        "ram_pct": mem["ram_pct"],
        "severity": mem["severity"],
        "nodes": active_nodes,
        "hmac_sig": sig,
    }


if __name__ == "__main__":
    print(json.dumps(sync_compute_nodes(), indent=2))
