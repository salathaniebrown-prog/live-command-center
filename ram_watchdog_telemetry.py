#!/usr/bin/env python3
"""
SalathanieAI — Continuous Self-RAM Telemetry & Reboot-Prevention Watchdog
Monitors /proc/meminfo and PM2 RSS footprints continuously, writes WAL telemetry,
emits frames via telemetry_emitters.py, and trims non-core workers under RAM pressure.
Strictly additive: never replaces existing modules.
"""
import hashlib
import json
import signal
import sqlite3
import subprocess
import time
from pathlib import Path

REPO = Path("/data/data/com.termux/files/home/live-command-center")
WAL_DB = REPO / "alstra_flight_ledger.db"

WARN_PCT = 82.0
CRIT_PCT = 87.0
PROTECTED_EXACT = {
    "salathanie-pilot",
    "salathanie-guard",
    "salathanie-gw-8090",
    "salathanie-self-heal",
    "salathanie-ram-watch",
    "salathanie-wal-8125",
    "salathanie-tunnel",
}
PROTECTED_PREFIXES = ("salathanie-",)

_STOP = False


def _handle_sig(signum, frame):
    global _STOP
    _STOP = True


def _db() -> sqlite3.Connection:
    WAL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WAL_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ram_watchdog_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            ram_pct REAL NOT NULL,
            used_mb INT NOT NULL,
            avail_mb INT NOT NULL,
            total_mb INT NOT NULL,
            severity TEXT NOT NULL,
            reclaimed_mb REAL NOT NULL,
            actions_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def read_meminfo() -> dict:
    tot_kb = avail_kb = free_kb = buffers_kb = cached_kb = 0
    try:
        for ln in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            if len(parts) < 2:
                continue
            key, val = parts[0].rstrip(":"), int(parts[1])
            if key == "MemTotal":
                tot_kb = val
            elif key == "MemAvailable":
                avail_kb = val
            elif key == "MemFree":
                free_kb = val
            elif key == "Buffers":
                buffers_kb = val
            elif key == "Cached":
                cached_kb = val
    except OSError:
        pass

    eff_avail_kb = avail_kb if avail_kb > 0 else (free_kb + buffers_kb + cached_kb)
    total_mb = tot_kb // 1024 if tot_kb else 0
    avail_mb = eff_avail_kb // 1024 if eff_avail_kb else 0
    used_mb = max(0, total_mb - avail_mb)
    ram_pct = round((used_mb / total_mb) * 100.0, 2) if total_mb else 0.0

    if ram_pct >= CRIT_PCT:
        sev = "CRITICAL"
    elif ram_pct >= WARN_PCT:
        sev = "ELEVATED"
    else:
        sev = "SAFE"

    return {
        "ts": int(time.time()),
        "ram_pct": ram_pct,
        "total_mb": total_mb,
        "used_mb": used_mb,
        "avail_mb": avail_mb,
        "severity": sev,
    }


def _pm2_procs() -> list[dict]:
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        raw = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip().startswith("[") else []
    except Exception:
        return []
    out = []
    for p in raw:
        env = p.get("pm2_env") or {}
        mem_b = int((p.get("monit") or {}).get("memory") or 0)
        out.append({
            "name": p.get("name", ""),
            "status": env.get("status", ""),
            "mem_mb": round(mem_b / 1048576.0, 2),
        })
    return out


def tick_watchdog(enforce: bool = True) -> dict:
    mem = read_meminfo()
    procs = _pm2_procs()
    actions = []
    reclaimed_mb = 0.0

    if enforce and mem["severity"] in ("ELEVATED", "CRITICAL"):
        # Sort non-protected online processes from largest RSS to smallest
        candidates = [
            p for p in procs
            if p["status"] == "online"
            and p["name"] not in PROTECTED_EXACT
            and not p["name"].startswith(PROTECTED_PREFIXES)
        ]
        candidates.sort(key=lambda x: x["mem_mb"], reverse=True)

        for cand in candidates:
            if mem["severity"] == "SAFE":
                break
            # In ELEVATED, stop heavy workers (> 25MB); in CRITICAL, stop any non-core worker (> 10MB)
            min_rss = 10.0 if mem["severity"] == "CRITICAL" else 25.0
            if cand["mem_mb"] >= min_rss:
                rc = subprocess.run(["pm2", "stop", cand["name"]], capture_output=True, text=True, timeout=6)
                if rc.returncode == 0:
                    actions.append(f"stopped:{cand['name']}({cand['mem_mb']}MB)")
                    reclaimed_mb = round(reclaimed_mb + cand["mem_mb"], 2)
                    mem = read_meminfo()

    sig = hashlib.sha256(f"wd|{mem['ts']}|{mem['ram_pct']}|{mem['severity']}|{len(actions)}".encode("utf-8")).hexdigest()[:24].upper()

    with _db() as c:
        c.execute(
            """INSERT INTO ram_watchdog_events(
                ts,ram_pct,used_mb,avail_mb,total_mb,severity,reclaimed_mb,actions_json,hmac_sig
            ) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                mem["ts"], mem["ram_pct"], mem["used_mb"], mem["avail_mb"], mem["total_mb"],
                mem["severity"], reclaimed_mb, json.dumps(actions), sig,
            ),
        )
        c.commit()

    try:
        import telemetry_emitters as temit
        temit.emit_once("RAM_WATCHDOG", {
            "ram_pct": mem["ram_pct"],
            "avail_mb": mem["avail_mb"],
            "severity": mem["severity"],
            "reclaimed_mb": reclaimed_mb,
            "actions": actions,
        })
    except Exception:
        pass

    top_rss = sorted(procs, key=lambda x: x["mem_mb"], reverse=True)[:8]
    return {
        "ok": True,
        "mem": mem,
        "severity": mem["severity"],
        "reclaimed_mb": reclaimed_mb,
        "actions": actions,
        "top_rss": top_rss,
        "hmac_sig": sig,
    }


def watchdog_status(limit: int = 12) -> dict:
    snap = tick_watchdog(enforce=False)
    with _db() as c:
        rows = c.execute(
            "SELECT ts,ram_pct,used_mb,avail_mb,severity,reclaimed_mb,actions_json,hmac_sig FROM ram_watchdog_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    events = [
        {
            "ts": r[0], "ram_pct": r[1], "used_mb": r[2], "avail_mb": r[3],
            "severity": r[4], "reclaimed_mb": r[5], "actions": json.loads(r[6] or "[]"), "hmac_sig": r[7],
        }
        for r in rows
    ]
    return {"ok": True, "current": snap, "events": events}


def run_loop(interval_s: float = 6.0):
    signal.signal(signal.SIGTERM, _handle_sig)
    signal.signal(signal.SIGINT, _handle_sig)
    while not _STOP:
        try:
            tick_watchdog(enforce=True)
        except Exception:
            pass
        time.sleep(interval_s)


if __name__ == "__main__":
    run_loop(6.0)
