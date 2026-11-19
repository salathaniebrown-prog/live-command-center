#!/usr/bin/env python3
"""
Alstra Automated Telemetry Circuit-Breaker & Pre-Panic Reboot Prevention Daemon (127.0.0.1:8134)
- Pre-Panic Thermal & RAM Throttling (trips breaker before Android LMK / kernel panic)
- Surgical Runaway Worker Isolation (scans Python, Node, and C daemons bound to cluster ports)
- Automatic SQLite WAL Checkpoint Flush & Cache Bounding
- Persistent Reboot-Prevention Ledger in ~/.astra_local_brain.db
"""
import http.server
import json
import os
import signal
import socketserver
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path

PORT = int(os.environ.get("ALSTRA_SHADOW_PORT", "8134"))
HOME = Path.home()
DB_PATH = HOME / ".astra_local_brain.db"

# Hard safety thresholds to prevent Android LMK / thermal hardware reboots
RAM_TRIP_PCT = 86.5
RAM_CRITICAL_PCT = 91.0
TEMP_TRIP_C = 43.0
WORKER_RSS_LIMIT_MB = 48.0

LOCK = threading.Lock()
STATE = {
    "breaker_state": "CLOSED_NOMINAL",
    "ram_used_pct": 0.0,
    "ram_avail_mb": 0.0,
    "soc_temp_c": 37.5,
    "wal_flushes": 0,
    "runaway_isolations": 0,
    "throttle_level": 0,
    "watched_daemons": [],
    "last_action": "ARMED_MONITORING_CLUSTER",
    "updated_at": time.time(),
}


def init_breaker_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-4000;")        # Cap SQLite page cache at 4 MB
    conn.execute("PRAGMA wal_autocheckpoint=100;")  # Flush WAL every 100 pages (~400 KB)
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reboot_prevention_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            breaker_state TEXT,
            ram_used_pct REAL,
            soc_temp_c REAL,
            action_taken TEXT,
            target_proc TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def flush_sqlite_wal() -> str:
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=3.0)
        conn.execute("PRAGMA cache_size=-4000;")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.commit()
        conn.close()
        return "WAL_TRUNCATED_OK"
    except Exception as exc:
        return f"WAL_FLUSH_ERR:{exc}"


def read_memory_and_thermal() -> tuple[float, float, float]:
    mem_tot, mem_avail = 3416.0, 600.0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                mem_tot = float(line.split()[1]) / 1024.0
            elif line.startswith("MemAvailable:"):
                mem_avail = float(line.split()[1]) / 1024.0
    except Exception:
        pass
    used_pct = round(max(0.0, min(100.0, ((mem_tot - mem_avail) / max(1.0, mem_tot)) * 100.0)), 1)

    temp_c = 37.5
    try:
        temps = []
        for tz in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))[:6]:
            raw = tz.read_text().strip()
            if raw.isdigit():
                val = float(raw) / (1000.0 if float(raw) > 1000 else 1.0)
                if 15.0 <= val <= 105.0:
                    temps.append(val)
        if temps:
            temp_c = round(sum(temps) / len(temps), 1)
    except Exception:
        pass
    return used_pct, round(mem_avail, 1), temp_c


def scan_and_isolate_runaways(critical_ram: bool) -> tuple[list[dict], list[str]]:
    """Scans Python, Node, and C daemons in /proc for RSS memory bloat or zombie loops."""
    daemons = []
    isolated = []
    my_pid = os.getpid()
    try:
        for proc_dir in Path("/proc").iterdir():
            if not proc_dir.name.isdigit():
                continue
            pid = int(proc_dir.name)
            if pid == my_pid:
                continue
            try:
                cmd = (proc_dir / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
                if not any(tag in cmd for tag in ("astra", "alstra", "dashboard_server", "server.py", "neuro")):
                    continue
                status_txt = (proc_dir / "status").read_text(errors="ignore")
                rss_kb = 0
                for line in status_txt.splitlines():
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                        break
                rss_mb = round(rss_kb / 1024.0, 2)
                short_name = Path(cmd.split()[-1]).name if cmd else f"pid-{pid}"
                daemons.append({"pid": pid, "name": short_name, "rss_mb": rss_mb})

                # Surgical isolation if a single worker exceeds cap or system RAM hits critical ceiling
                if rss_mb > WORKER_RSS_LIMIT_MB or (critical_ram and rss_mb > 34.0 and "8088" not in cmd and "8090" not in cmd):
                    os.kill(pid, signal.SIGTERM)
                    isolated.append(f"{short_name}(pid={pid},rss={rss_mb}MB)")
            except Exception:
                continue
    except Exception:
        pass
    daemons.sort(key=lambda d: d["rss_mb"], reverse=True)
    return daemons[:20], isolated


def evaluate_circuit_breaker() -> dict:
    used_pct, avail_mb, temp_c = read_memory_and_thermal()
    critical_ram = used_pct >= RAM_CRITICAL_PCT
    trip = used_pct >= RAM_TRIP_PCT or temp_c >= TEMP_TRIP_C

    daemons, isolated = scan_and_isolate_runaways(critical_ram)
    action = "NOMINAL_WITHIN_ENVELOPE"
    wal_did_flush = False

    if trip or isolated:
        wal_res = flush_sqlite_wal()
        wal_did_flush = True
        action = f"BREAKER_OPEN: RAM={used_pct}% TEMP={temp_c}C | {wal_res}"
        if isolated:
            action += f" | ISOLATED={','.join(isolated)}"

        # Lower process priority (nice +10) on non-critical background workers during thermal/RAM spike
        for d in daemons[4:]:
            try:
                os.setpriority(os.PRIO_PROCESS, d["pid"], 10)
            except Exception:
                pass

        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=3.0)
            conn.execute(
                "INSERT INTO reboot_prevention_ledger (ts, breaker_state, ram_used_pct, soc_temp_c, action_taken, target_proc) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), "OPEN_THROTTLED", used_pct, temp_c, action, ",".join(isolated) or "WAL_FLUSH"),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    with LOCK:
        STATE["breaker_state"] = "OPEN_THROTTLED" if trip else "CLOSED_NOMINAL"
        STATE["ram_used_pct"] = used_pct
        STATE["ram_avail_mb"] = avail_mb
        STATE["soc_temp_c"] = temp_c
        if wal_did_flush:
            STATE["wal_flushes"] += 1
        STATE["runaway_isolations"] += len(isolated)
        STATE["throttle_level"] = 2 if critical_ram else (1 if trip else 0)
        STATE["watched_daemons"] = daemons
        STATE["last_action"] = action
        STATE["updated_at"] = time.time()
        return json.loads(json.dumps(STATE))


def _bg_breaker_loop():
    while True:
        try:
            evaluate_circuit_breaker()
        except Exception:
            pass
        time.sleep(2.5)


class ThreadingReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class CircuitBreakerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _send_json(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"cb8134-{uuid.uuid4().hex[:12]}")
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        with LOCK:
            snap = json.loads(json.dumps(STATE))
        return self._send_json(
            {
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_CIRCUIT_BREAKER_8134",
                "circuit_breaker": snap,
                "timestamp": time.time(),
            }
        )

    def do_POST(self):
        flush_sqlite_wal()
        snap = evaluate_circuit_breaker()
        return self._send_json(
            {
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_CIRCUIT_BREAKER_8134",
                "circuit_breaker": snap,
            }
        )


if __name__ == "__main__":
    init_breaker_db()
    threading.Thread(target=_bg_breaker_loop, daemon=True).start()
    with ThreadingReuseTCP(("0.0.0.0", PORT), CircuitBreakerHandler) as srv:
        print(f"[✔] Alstra Telemetry Circuit-Breaker & Pre-Panic Reboot Prevention Daemon active on 0.0.0.0:{PORT}")
        srv.serve_forever()
