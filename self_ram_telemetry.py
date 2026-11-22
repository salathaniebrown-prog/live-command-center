#!/usr/bin/env python3
"""
SalathanieAI — Self-Healing RAM Telemetry & Pressure Controller (self_ram_telemetry.py)
Monitors /proc/meminfo + PM2 process footprints, logs WAL snapshots, and applies
non-destructive pressure relief when RAM exceeds guard thresholds.
Strictly additive: never deletes user files or stops core Salathanie/FlyingCar services.
"""
import hashlib
import json
import sqlite3
import subprocess
import time
from pathlib import Path

REPO = Path("/data/data/com.termux/files/home/live-command-center")
WAL_DB = REPO / "alstra_flight_ledger.db"
HOME = Path.home()

PROTECTED_PREFIXES = ("salathanie-", "astra-8088", "astra-8090", "astra-8095", "astra-8099", "astra-8151")


def _db() -> sqlite3.Connection:
    WAL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WAL_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ram_telemetry_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            ram_pct REAL NOT NULL,
            total_mb INT NOT NULL,
            avail_mb INT NOT NULL,
            band TEXT NOT NULL,
            actions_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def read_host_mem() -> dict:
    tot_kb = avail_kb = 0
    try:
        for ln in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ln.startswith("MemTotal:"):
                tot_kb = int(ln.split()[1])
            elif ln.startswith("MemAvailable:"):
                avail_kb = int(ln.split()[1])
    except OSError:
        pass
    total_mb = tot_kb // 1024 if tot_kb else 0
    avail_mb = avail_kb // 1024 if avail_kb else 0
    used_mb = max(0, total_mb - avail_mb)
    ram_pct = round((used_mb / total_mb) * 100.0, 2) if total_mb else 0.0
    band = "GUARD_TRIM" if ram_pct >= 85.0 else ("ELEVATED" if ram_pct >= 78.0 else "NORMAL")
    return {
        "ts": int(time.time()),
        "ram_pct": ram_pct,
        "total_mb": total_mb,
        "used_mb": used_mb,
        "avail_mb": avail_mb,
        "band": band,
    }


def pm2_mem_snapshot() -> list[dict]:
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        items = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip().startswith("[") else []
    except Exception:
        items = []
    out = []
    for p in items:
        env = p.get("pm2_env") or {}
        mem_bytes = int((p.get("monit") or {}).get("memory") or 0)
        out.append({
            "name": p.get("name", ""),
            "status": env.get("status", ""),
            "mem_mb": round(mem_bytes / 1048576.0, 2),
            "restarts": int(env.get("restart_time") or 0),
        })
    out.sort(key=lambda x: x["mem_mb"], reverse=True)
    return out


def sample_and_guard(auto_trim: bool = True, target_pct: float = 82.0) -> dict:
    mem = read_host_mem()
    procs = pm2_mem_snapshot()
    actions = []

    if auto_trim and mem["ram_pct"] >= 85.0:
        # Restart heavy non-core astra-* workers (> 60MB) once to clear heap fragmentation
        for pr in procs:
            nm = pr["name"]
            if pr["status"] == "online" and pr["mem_mb"] >= 60.0 and not nm.startswith(PROTECTED_PREFIXES):
                subprocess.run(["pm2", "restart", nm], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
                actions.append(f"restarted_heavy_worker:{nm}({pr['mem_mb']}MB)")
                mem_after = read_host_mem()
                if mem_after["ram_pct"] < target_pct:
                    mem = mem_after
                    break

    sig = hashlib.sha256(f"ram|{mem['ts']}|{mem['ram_pct']}|{len(actions)}".encode("utf-8")).hexdigest()[:24].upper()
    with _db() as c:
        c.execute(
            "INSERT INTO ram_telemetry_log(ts,ram_pct,total_mb,avail_mb,band,actions_json,hmac_sig) VALUES (?,?,?,?,?,?,?)",
            (mem["ts"], mem["ram_pct"], mem["total_mb"], mem["avail_mb"], mem["band"], json.dumps(actions), sig),
        )
        c.commit()

    return {
        "ok": True,
        "mem": mem,
        "actions_taken": actions,
        "top_processes": procs[:10],
        "hmac_sig": sig,
    }


def ram_history(limit: int = 12) -> dict:
    cur = sample_and_guard(auto_trim=False)
    with _db() as c:
        rows = c.execute(
            "SELECT ts,ram_pct,total_mb,avail_mb,band,actions_json,hmac_sig FROM ram_telemetry_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    hist = [
        {"ts": r[0], "ram_pct": r[1], "total_mb": r[2], "avail_mb": r[3], "band": r[4], "actions": json.loads(r[5] or "[]"), "hmac_sig": r[6]}
        for r in rows
    ]
    return {"ok": True, "current": cur, "history": hist}


if __name__ == "__main__":
    print(json.dumps(sample_and_guard(auto_trim=True), indent=2))
