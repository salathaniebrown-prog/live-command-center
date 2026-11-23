#!/usr/bin/env python3
"""
Astra + Alstra = SalathanieAI
Predictive Memory Telemetry & OOM Prevention Shield (:8158)
Prevents Android lmkd / Phantom Process Killer restarts by shedding non-core workers before 83% RAM.
"""
import gc
import http.server
import json
import os
import sqlite3
import subprocess
import threading
import time

PORT = 8158
HOME = os.path.expanduser("~")
SHIELD_DB = os.path.join(HOME, "live-command-center", "memory_shield_telemetry.db")

WARN_PCT = float(os.environ.get("MEM_WARN_PCT", "78.0"))
SHED_PCT = float(os.environ.get("MEM_SHED_PCT", "82.0"))
RESTORE_PCT = float(os.environ.get("MEM_RESTORE_PCT", "74.0"))
HARD_CEILING_PCT = 83.0
POLL_SEC = 4

# Non-core / on-demand PM2 workers safe to pause temporarily during RAM spikes
SHEDDABLE_WORKERS = [
    "salathanie-game-8150",
    "salathanie-twin-flight-8152",
    "astra-8108-studio",
    "astra-8121-studio",
]

STATE = {
    "ok": True,
    "system": "SALATHANIE_MEMORY_PRESSURE_SHIELD",
    "port": PORT,
    "tier": "NOMINAL",
    "ram_used_pct": 0.0,
    "ram_free_mb": 0.0,
    "ram_total_mb": 0.0,
    "psi_some_avg10": 0.0,
    "shed_events": 0,
    "paused_workers": [],
    "last_action": "INITIALIZED",
}


def get_db():
    conn = sqlite3.connect(SHIELD_DB, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS memory_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tier TEXT,
        ram_used_pct REAL,
        ram_free_mb REAL,
        psi_some_avg10 REAL,
        action TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()


init_db()


def read_memory_telemetry() -> dict:
    total_kb = 0
    avail_kb = 0
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for ln in f:
                if ln.startswith("MemTotal:"):
                    total_kb = int(ln.split()[1])
                elif ln.startswith("MemAvailable:"):
                    avail_kb = int(ln.split()[1])
    except Exception:
        pass

    psi_some = 0.0
    try:
        with open("/proc/pressure/memory", "r", encoding="utf-8") as f:
            for ln in f:
                if ln.startswith("some "):
                    for tok in ln.split():
                        if tok.startswith("avg10="):
                            psi_some = float(tok.split("=", 1)[1])
    except Exception:
        pass

    used_pct = round(((total_kb - avail_kb) / total_kb) * 100.0, 1) if total_kb > 0 else 0.0
    free_mb = round(avail_kb / 1024.0, 1)
    total_mb = round(total_kb / 1024.0, 1)
    return {
        "ram_used_pct": used_pct,
        "ram_free_mb": free_mb,
        "ram_total_mb": total_mb,
        "psi_some_avg10": psi_some,
    }


def _record_event(tier: str, metrics: dict, action: str):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO memory_events (tier, ram_used_pct, ram_free_mb, psi_some_avg10, action, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (tier, metrics["ram_used_pct"], metrics["ram_free_mb"], metrics["psi_some_avg10"], action, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def shed_non_core_workers(reason: str) -> list[str]:
    gc.collect()
    paused_now = []
    try:
        raw = subprocess.check_output(["pm2", "jlist"], stderr=subprocess.DEVNULL, text=True, timeout=4)
        apps = json.loads(raw)
        online_names = {
            a.get("name")
            for a in apps
            if (a.get("pm2_env") or {}).get("status") == "online"
        }
    except Exception:
        online_names = set()

    for worker in SHEDDABLE_WORKERS:
        if worker in online_names:
            try:
                subprocess.run(["pm2", "stop", worker], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                paused_now.append(worker)
                if worker not in STATE["paused_workers"]:
                    STATE["paused_workers"].append(worker)
            except Exception:
                pass

    if paused_now:
        STATE["shed_events"] += 1
        STATE["last_action"] = f"SHED({','.join(paused_now)}) reason={reason}"
    return paused_now


def restore_paused_workers() -> list[str]:
    restored = []
    for worker in list(STATE["paused_workers"]):
        try:
            subprocess.run(["pm2", "start", worker], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            STATE["paused_workers"].remove(worker)
            restored.append(worker)
        except Exception:
            pass
    if restored:
        STATE["last_action"] = f"RESTORED({','.join(restored)})"
    return restored


def monitor_loop():
    while True:
        metrics = read_memory_telemetry()
        STATE.update(metrics)
        pct = metrics["ram_used_pct"]
        psi = metrics["psi_some_avg10"]

        if pct >= SHED_PCT or psi >= 25.0:
            STATE["tier"] = "CRITICAL_SHED"
            shed = shed_non_core_workers(f"ram={pct}% psi={psi}")
            if shed:
                _record_event("CRITICAL_SHED", metrics, STATE["last_action"])
        elif pct >= WARN_PCT:
            STATE["tier"] = "ELEVATED_GUARD"
            gc.collect()
        else:
            STATE["tier"] = "NOMINAL"
            if STATE["paused_workers"] and pct <= RESTORE_PCT:
                restored = restore_paused_workers()
                if restored:
                    _record_event("NOMINAL", metrics, STATE["last_action"])

        time.sleep(POLL_SEC)


class ShieldHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p in ("/", "/health", "/api/memory/telemetry"):
            metrics = read_memory_telemetry()
            STATE.update(metrics)
            return self._send(200, {
                **STATE,
                "warn_threshold_pct": WARN_PCT,
                "shed_threshold_pct": SHED_PCT,
                "hard_ceiling_pct": HARD_CEILING_PCT,
                "headroom_to_ceiling_pct": round(HARD_CEILING_PCT - metrics["ram_used_pct"], 1),
                "ts": int(time.time()),
            })
        if p == "/api/memory/events":
            conn = get_db()
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute("SELECT * FROM memory_events ORDER BY id DESC LIMIT 15").fetchall()]
            conn.close()
            return self._send(200, {"ok": True, "events": rows})
        return self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        p = (self.path or "/").split("?", 1)[0]
        if p == "/api/memory/shed":
            metrics = read_memory_telemetry()
            shed = shed_non_core_workers("manual_or_telemetry_trigger")
            _record_event("MANUAL_SHED", metrics, STATE["last_action"])
            return self._send(200, {"ok": True, "shed_workers": shed, "state": STATE})
        if p == "/api/memory/restore":
            restored = restore_paused_workers()
            return self._send(200, {"ok": True, "restored_workers": restored, "state": STATE})
        return self._send(404, {"ok": False, "error": "not_found"})


if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), ShieldHandler).serve_forever()
