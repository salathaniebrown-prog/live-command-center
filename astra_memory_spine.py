#!/usr/bin/env python3
"""
SalathanieAI — Cross-Session Persistent Memory Spine
SQLite WAL Database: ~/live-command-center/alstra_flight_ledger.db
Persists & restores:
  1. PM2 service topology & process args
  2. 3D Jet state, pods, pilot stick & latest telemetry frame
  3. Full flight ledger mirror (generations, USGS/NWS/EONET feeds, PX4 coordinates)
  4. Deduplicated zlib-compressed code snapshots with instant per-file rollback
  5. HMAC-SHA256 attested session/boot recovery log
"""
import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import time
import zlib
from pathlib import Path

REPO = Path("/data/data/com.termux/files/home/live-command-center")
SPINE_DB = REPO / "alstra_flight_ledger.db"
LEGACY_LEDGER_DB = REPO / "astra_flight_ledger.db"
JET_DIR = REPO / "builds" / "astra_jet"
STATE_FILE = JET_DIR / "alstra_jet_state.json"
TELEM_FILE = JET_DIR / "alstra_jet_telemetry.jsonl"
PM2_DUMP = Path.home() / ".pm2" / "dump.pm2"
HOME = Path.home()

CODE_EXTS = (".py", ".js", ".sh")
SKIP_FILES = {"package-lock.json"}


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SPINE_DB), timeout=8.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=FULL;")
    conn.execute("PRAGMA busy_timeout=6000;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT,
            git_head TEXT,
            hmac_sig TEXT
        );
        CREATE TABLE IF NOT EXISTS service_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            service_count INT,
            online_count INT,
            pm2_jlist_json TEXT,
            dump_sha256 TEXT
        );
        CREATE TABLE IF NOT EXISTS jet_state_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            active_gen TEXT,
            mode TEXT,
            pods_json TEXT,
            state_json TEXT,
            latest_telem_json TEXT,
            state_sha256 TEXT
        );
        CREATE TABLE IF NOT EXISTS code_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            rel_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INT NOT NULL,
            git_head TEXT,
            content_zlib BLOB NOT NULL,
            UNIQUE(rel_path, sha256)
        );
        CREATE TABLE IF NOT EXISTS flight_generations (
            src_id INTEGER PRIMARY KEY,
            ts INT, gen_id TEXT, parent_gen TEXT, mode TEXT,
            pods_mask TEXT, pods_active INT,
            pilot_pitch REAL, pilot_roll REAL, pilot_thrust REAL,
            fitness REAL, prev_fitness REAL, promoted INT,
            ram_pct REAL, mem_avail_mb INT, temp_c REAL,
            ext_hazard_score REAL, px4_lat REAL, px4_lon REAL, px4_alt_m REAL,
            reason TEXT, genome_json TEXT, code_path TEXT, hmac_sig TEXT
        );
        CREATE TABLE IF NOT EXISTS external_feeds (
            source TEXT NOT NULL,
            event_id TEXT NOT NULL,
            ts INT, title TEXT, severity TEXT, lat REAL, lon REAL, raw_json TEXT,
            PRIMARY KEY (source, event_id)
        );
        CREATE TABLE IF NOT EXISTS px4_telemetry (
            src_id INTEGER PRIMARY KEY,
            ts INT, vehicle_id TEXT, lat REAL, lon REAL, alt_m REAL,
            rel_alt_m REAL, heading REAL, groundspeed REAL, battery_pct REAL,
            flight_mode TEXT, armed INT, source TEXT
        );
    """)
    return conn


def _hmac_sign(payload: str) -> str:
    kp = HOME / ".salathanie_hmac.key"
    key = kp.read_bytes()[:32] if kp.exists() else b"salathanie-memory-spine-key"
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24].upper()


def _git_head() -> str:
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _pub_ring(tag: str):
    try:
        from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-memory-spine", 8125, 200, deterministic_hv(f"spine:{tag}"))
    except Exception:
        pass


def _atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))


def _capture_pm2() -> tuple[list[dict], str]:
    procs = []
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=6)
        if r.returncode == 0 and r.stdout.strip().startswith("["):
            for p in json.loads(r.stdout):
                env = p.get("pm2_env", {})
                procs.append({
                    "name": p.get("name", ""),
                    "status": env.get("status", ""),
                    "script": env.get("pm_exec_path", ""),
                    "args": env.get("args", []),
                    "interpreter": env.get("exec_interpreter", ""),
                    "restarts": int(env.get("restart_time", 0)),
                    "mem_mb": round((p.get("monit", {}).get("memory", 0) or 0) / (1024 * 1024), 1),
                })
    except Exception:
        pass
    dump_sha = ""
    if PM2_DUMP.exists():
        try:
            dump_sha = hashlib.sha256(PM2_DUMP.read_bytes()).hexdigest()[:16]
        except OSError:
            pass
    return procs, dump_sha


def _sync_legacy_ledger(conn: sqlite3.Connection) -> dict:
    """Mirror all rows from astra_flight_ledger.db into alstra_flight_ledger.db."""
    synced = {"generations": 0, "external_feeds": 0, "px4": 0}
    if not LEGACY_LEDGER_DB.exists():
        return synced
    try:
        src = sqlite3.connect(str(LEGACY_LEDGER_DB), timeout=4.0)
        tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "flight_generations" in tables:
            rows = src.execute(
                """SELECT id,ts,gen_id,parent_gen,mode,pods_mask,pods_active,
                          pilot_pitch,pilot_roll,pilot_thrust,fitness,prev_fitness,promoted,
                          ram_pct,mem_avail_mb,temp_c,ext_hazard_score,px4_lat,px4_lon,px4_alt_m,
                          reason,genome_json,code_path,hmac_sig FROM flight_generations"""
            ).fetchall()
            conn.executemany(
                "INSERT OR REPLACE INTO flight_generations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            synced["generations"] = len(rows)
        if "external_feeds" in tables:
            rows = src.execute("SELECT source,event_id,ts,title,severity,lat,lon,raw_json FROM external_feeds").fetchall()
            conn.executemany("INSERT OR REPLACE INTO external_feeds VALUES (?,?,?,?,?,?,?,?)", rows)
            synced["external_feeds"] = len(rows)
        if "px4_telemetry" in tables:
            rows = src.execute(
                "SELECT id,ts,vehicle_id,lat,lon,alt_m,rel_alt_m,heading,groundspeed,battery_pct,flight_mode,armed,source FROM px4_telemetry"
            ).fetchall()
            conn.executemany("INSERT OR REPLACE INTO px4_telemetry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            synced["px4"] = len(rows)
        src.close()
    except Exception:
        pass
    return synced


def _snapshot_code(conn: sqlite3.Connection, ts: int, head: str) -> dict:
    """Store deduplicated zlib-compressed snapshots of top-level core workflow code."""
    scanned = 0
    new_versions = 0
    for fp in sorted(REPO.iterdir()):
        if not fp.is_file() or fp.suffix.lower() not in CODE_EXTS or fp.name in SKIP_FILES:
            continue
        try:
            raw = fp.read_bytes()
        except OSError:
            continue
        if len(raw) > 512_000:
            continue
        scanned += 1
        sha = hashlib.sha256(raw).hexdigest()
        cur = conn.execute("INSERT OR IGNORE INTO code_snapshots(ts,rel_path,sha256,size_bytes,git_head,content_zlib) VALUES (?,?,?,?,?,?)",
                           (ts, fp.name, sha, len(raw), head, zlib.compress(raw, level=6)))
        if cur.rowcount > 0:
            new_versions += 1
    return {"files_scanned": scanned, "new_versions_saved": new_versions}


def take_snapshot(reason: str = "manual", save_pm2_dump: bool = True) -> dict:
    ts = int(time.time())
    head = _git_head()
    if save_pm2_dump:
        subprocess.run(["pm2", "save", "--force"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
    procs, dump_sha = _capture_pm2()
    online_cnt = sum(1 for p in procs if p["status"] == "online")

    state_txt = STATE_FILE.read_text(encoding="utf-8").strip() if STATE_FILE.exists() else "{}"
    try:
        st_obj = json.loads(state_txt) if state_txt else {}
    except Exception:
        st_obj = {}
    telem_last = "{}"
    if TELEM_FILE.exists():
        try:
            lines = [ln for ln in TELEM_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if lines:
                telem_last = lines[-1]
        except OSError:
            pass
    state_sha = hashlib.sha256(state_txt.encode("utf-8")).hexdigest()[:16]

    with db_conn() as conn:
        conn.execute(
            "INSERT INTO service_snapshots(ts,service_count,online_count,pm2_jlist_json,dump_sha256) VALUES (?,?,?,?,?)",
            (ts, len(procs), online_cnt, json.dumps(procs), dump_sha),
        )
        # Only store new jet state snapshot if hash changed or table empty
        prev = conn.execute("SELECT state_sha256 FROM jet_state_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        jet_saved = False
        if not prev or prev[0] != state_sha:
            conn.execute(
                "INSERT INTO jet_state_snapshots(ts,active_gen,mode,pods_json,state_json,latest_telem_json,state_sha256) VALUES (?,?,?,?,?,?,?)",
                (ts, st_obj.get("active_gen", "GEN-000"), st_obj.get("mode", "AUTONOMOUS-MUTATE"),
                 json.dumps(st_obj.get("pods", [True, True, True, True])), state_txt, telem_last, state_sha),
            )
            jet_saved = True

        mirrored = _sync_legacy_ledger(conn)
        code_stats = _snapshot_code(conn, ts, head)
        sig = _hmac_sign(f"snap|{ts}|{head}|{online_cnt}|{state_sha}|{code_stats['new_versions_saved']}")
        conn.execute(
            "INSERT INTO session_events(ts,event_type,detail,git_head,hmac_sig) VALUES (?,?,?,?,?)",
            (ts, f"SNAPSHOT:{reason}", json.dumps({"online": online_cnt, "total": len(procs), "code": code_stats, "mirrored": mirrored}), head, sig),
        )
        conn.commit()
        try:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except sqlite3.OperationalError:
            pass

    _pub_ring(f"snap:{reason}:{online_cnt}/{len(procs)}")
    return {
        "ok": True,
        "ts": ts,
        "db": str(SPINE_DB),
        "git_head": head,
        "services": {"online": online_cnt, "total": len(procs), "dump_sha256": dump_sha},
        "jet_state_changed": jet_saved,
        "mirrored_ledger": mirrored,
        "code_snapshots": code_stats,
        "hmac_sig": sig,
    }


def restore_session(revive_pm2: bool = True, dry_run: bool = False) -> dict:
    """Restore 3D jet state, check code integrity, and revive PM2 stack after reboot or crash."""
    ts = int(time.time())
    head = _git_head()
    actions = []

    with db_conn() as conn:
        jet_row = conn.execute(
            "SELECT active_gen, mode, state_json, latest_telem_json FROM jet_state_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        svc_row = conn.execute(
            "SELECT online_count, service_count, pm2_jlist_json FROM service_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()

    # 1. Restore missing or corrupted alstra_jet_state.json
    state_ok = False
    if STATE_FILE.exists():
        try:
            json.loads(STATE_FILE.read_text(encoding="utf-8"))
            state_ok = True
        except Exception:
            state_ok = False

    if not state_ok and jet_row and jet_row[2]:
        if not dry_run:
            _atomic_write_text(STATE_FILE, jet_row[2])
        actions.append(f"restored_jet_state:{jet_row[0]}")
    else:
        actions.append("jet_state_intact")

    # 2. Restore missing telemetry file if wiped
    if (not TELEM_FILE.exists() or TELEM_FILE.stat().st_size == 0) and jet_row and jet_row[3] and jet_row[3] != "{}":
        if not dry_run:
            _atomic_write_text(TELEM_FILE, jet_row[3] + "\n")
        actions.append("restored_telem_jsonl")

    # 3. Revive PM2 services if down
    if revive_pm2 and not dry_run:
        procs, _ = _capture_pm2()
        online_names = {p["name"] for p in procs if p["status"] == "online"}
        if "salathanie-pilot" not in online_names:
            subprocess.run(["pm2", "resurrect"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            time.sleep(2)
            procs, _ = _capture_pm2()
            online_names = {p["name"] for p in procs if p["status"] == "online"}
            actions.append(f"pm2_resurrected:{len(online_names)}")
            if "salathanie-pilot" not in online_names and (REPO / "ecosystem.config.js").exists():
                subprocess.run(["pm2", "start", str(REPO / "ecosystem.config.js")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                actions.append("pm2_started_ecosystem")
        else:
            actions.append(f"pm2_already_online:{len(online_names)}")

    sig = _hmac_sign(f"restore|{ts}|{head}|{','.join(actions)}")
    if not dry_run:
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO session_events(ts,event_type,detail,git_head,hmac_sig) VALUES (?,?,?,?,?)",
                (ts, "RESTORE", json.dumps({"actions": actions}), head, sig),
            )
    _pub_ring(f"restore:{len(actions)}")
    return {
        "ok": True,
        "ts": ts,
        "dry_run": dry_run,
        "actions": actions,
        "last_saved_services": {"online": svc_row[0], "total": svc_row[1]} if svc_row else {},
        "hmac_sig": sig,
    }


def rollback_code_file(rel_path: str, version_id: int | None = None) -> dict:
    """Restore a tracked workflow file from zlib-compressed SQLite WAL snapshot."""
    name = Path(rel_path).name
    with db_conn() as conn:
        if version_id:
            row = conn.execute("SELECT id, ts, sha256, content_zlib FROM code_snapshots WHERE rel_path=? AND id=?", (name, version_id)).fetchone()
        else:
            row = conn.execute("SELECT id, ts, sha256, content_zlib FROM code_snapshots WHERE rel_path=? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
    if not row:
        return {"ok": False, "error": f"No snapshot found for {name}"}
    content = zlib.decompress(row[3]).decode("utf-8", errors="replace")
    target = REPO / name
    _atomic_write_text(target, content)
    return {"ok": True, "restored": name, "snapshot_id": row[0], "sha256": row[2][:16], "bytes": len(content)}


def spine_status() -> dict:
    with db_conn() as conn:
        totals = {
            "session_events": conn.execute("SELECT COUNT(*) FROM session_events").fetchone()[0],
            "service_snapshots": conn.execute("SELECT COUNT(*) FROM service_snapshots").fetchone()[0],
            "jet_snapshots": conn.execute("SELECT COUNT(*) FROM jet_state_snapshots").fetchone()[0],
            "code_snapshots": conn.execute("SELECT COUNT(*) FROM code_snapshots").fetchone()[0],
            "flight_generations": conn.execute("SELECT COUNT(*) FROM flight_generations").fetchone()[0],
            "external_feeds": conn.execute("SELECT COUNT(*) FROM external_feeds").fetchone()[0],
            "px4_points": conn.execute("SELECT COUNT(*) FROM px4_telemetry").fetchone()[0],
        }
        events = [
            {"id": r[0], "ts": r[1], "type": r[2], "detail": r[3], "git_head": r[4], "hmac_sig": r[5]}
            for r in conn.execute("SELECT id,ts,event_type,detail,git_head,hmac_sig FROM session_events ORDER BY id DESC LIMIT 12").fetchall()
        ]
        files = [
            {"id": r[0], "ts": r[1], "file": r[2], "sha256": r[3][:12], "bytes": r[4], "git_head": r[5]}
            for r in conn.execute(
                "SELECT id,ts,rel_path,sha256,size_bytes,git_head FROM code_snapshots WHERE id IN (SELECT MAX(id) FROM code_snapshots GROUP BY rel_path) ORDER BY rel_path ASC"
            ).fetchall()
        ]
        last_svc = conn.execute("SELECT ts, online_count, service_count, dump_sha256 FROM service_snapshots ORDER BY id DESC LIMIT 1").fetchone()
    db_kb = round(SPINE_DB.stat().st_size / 1024, 1) if SPINE_DB.exists() else 0.0
    wal_p = Path(str(SPINE_DB) + "-wal")
    wal_kb = round(wal_p.stat().st_size / 1024, 1) if wal_p.exists() else 0.0
    return {
        "ok": True,
        "db_path": str(SPINE_DB),
        "db_kb": db_kb,
        "wal_kb": wal_kb,
        "boot_hook_installed": (HOME / ".termux" / "boot" / "01-salathanie-restore.sh").exists(),
        "last_service_snapshot": {"ts": last_svc[0], "online": last_svc[1], "total": last_svc[2], "dump_sha256": last_svc[3]} if last_svc else {},
        "totals": totals,
        "recent_events": events,
        "tracked_code": files,
    }


MEMORY_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SalathanieAI — Persistent Memory Spine (alstra_flight_ledger.db)</title>
<style>
body{font-family:monospace;background:#050912;color:#e6edf3;margin:10px}
.card{background:#0f172a;border:1px solid #243652;border-radius:10px;padding:12px;margin-bottom:10px}
.nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.nav a{background:#1f6feb;color:#fff;padding:6px 9px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:bold}
button{background:#238636;color:#fff;border:none;padding:7px 10px;border-radius:6px;cursor:pointer;font-family:monospace;font-weight:bold;margin:3px 2px}
button.alt{background:#0ea5e9;color:#050912}button.amb{background:#f59e0b;color:#050912}button.pur{background:#8957e5}
pre{background:#070d18;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:220px;white-space:pre-wrap}
.row{border-bottom:1px solid #1e2d45;padding:5px 0;font-size:11px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.badge{background:#10b981;color:#050912;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:bold}
</style></head><body>
<h2 style="color:#38bdf8;margin:2px 0">PERSISTENT MEMORY SPINE // alstra_flight_ledger.db (SQLite WAL)</h2>
<div class="nav">
  <a href="/">Pilot</a>
  <a href="/jet-3d" style="background:#39ff14;color:#050912">3D Jet HUD</a>
  <a href="/creative" style="background:#f97316;color:#050912">Creative Studio</a>
  <a href="/mesh-hub" style="background:#10b981;color:#050912">Mesh &amp; Wiki</a>
  <a href="/broadcast" style="background:#ec4899">iPad Studio</a>
  <a href="/scrintal" style="background:#a855f7">AI Scrintal</a>
  <a href="/eagle-eyes" style="background:#0891b2">Eagle Eyes</a>
</div>

<div class="card">
  <div id="meta" style="margin-bottom:8px;color:#39ff14">Loading cross-session WAL spine...</div>
  <button onclick="snapNow()">Take Full Cross-Session Snapshot Now</button>
  <button class="alt" onclick="restoreDry()">Verify Recovery (Dry-Run)</button>
  <button class="amb" onclick="restoreNow()">Run Live Restore Check</button>
  <pre id="actionOut" style="margin-top:8px">Ready. Automatic snapshots run via Autopilot Guard and Termux Boot/Session Restore hooks.</pre>
</div>

<div class="card">
  <b>Deduplicated Code Snapshots (1-Tap File Recovery)</b>
  <div id="codeList" style="max-height:240px;overflow:auto;margin-top:6px"></div>
</div>

<div class="card">
  <b>Cross-Session Audit Trail (HMAC-SHA256 Signed)</b>
  <div id="evList" style="max-height:220px;overflow:auto;margin-top:6px"></div>
</div>

<script>
async function refresh(){
  const d=await(await fetch('/api/memory/status')).json();
  const t=d.totals||{};
  document.getElementById('meta').innerHTML=
    `<span class="badge">WAL ACTIVE</span> DB: <b>${d.db_kb}KB</b> (WAL ${d.wal_kb}KB) | Boot Hook: <b>${d.boot_hook_installed?'INSTALLED':'MISSING'}</b><br>`+
    `Tracked Code Versions: <b>${t.code_snapshots}</b> | Jet Snapshots: <b>${t.jet_snapshots}</b> | Flight Gens: <b>${t.flight_generations}</b> | External Feeds: <b>${t.external_feeds}</b> | PX4: <b>${t.px4_points}</b>`;
  document.getElementById('codeList').innerHTML=(d.tracked_code||[]).map(f=>
    `<div class="row"><span><b>${f.file}</b> <small style="color:#94a3b8">${f.bytes}B • sha ${f.sha256} • ${f.git_head}</small></span>`+
    `<button class="pur" style="padding:3px 7px;font-size:10px" onclick="rollbackFile('${f.file}')">Restore File</button></div>`
  ).join('');
  document.getElementById('evList').innerHTML=(d.recent_events||[]).map(e=>
    `<div class="row"><span><b>${e.type}</b> <small style="color:#7dd3fc">${new Date(e.ts*1000).toLocaleString()} • ${e.git_head}</small><br><small style="color:#cbd5e1">${e.detail}</small></span><span class="badge">${e.hmac_sig}</span></div>`
  ).join('');
}
async function snapNow(){
  document.getElementById('actionOut').textContent='Taking full WAL snapshot (PM2 + 3D Jet + Flight Ledger + Code)...';
  const d=await(await fetch('/api/memory/snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"reason":"ui_manual"}'})).json();
  document.getElementById('actionOut').textContent=JSON.stringify(d,null,2);
  refresh();
}
async function restoreDry(){
  const d=await(await fetch('/api/memory/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"dry_run":true}'})).json();
  document.getElementById('actionOut').textContent=JSON.stringify(d,null,2);
}
async function restoreNow(){
  const d=await(await fetch('/api/memory/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"dry_run":false}'})).json();
  document.getElementById('actionOut').textContent=JSON.stringify(d,null,2);
  refresh();
}
async function rollbackFile(file){
  if(!confirm('Restore '+file+' from latest WAL snapshot?'))return;
  const d=await(await fetch('/api/memory/rollback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file})})).json();
  document.getElementById('actionOut').textContent=JSON.stringify(d,null,2);
}
refresh();
</script></body></html>"""


def main():
    p = argparse.ArgumentParser(description="SalathanieAI Persistent Memory Spine (alstra_flight_ledger.db)")
    p.add_argument("--snapshot", action="store_true", help="Take full cross-session snapshot now")
    p.add_argument("--reason", default="cli", help="Snapshot label")
    p.add_argument("--restore", action="store_true", help="Restore state & revive PM2 after boot/crash")
    p.add_argument("--dry-run", action="store_true", help="Verify restore without mutating files/PM2")
    p.add_argument("--rollback-file", help="Restore a specific code file from WAL snapshot")
    p.add_argument("--status", action="store_true", help="Print WAL spine status")
    args = p.parse_args()

    if args.snapshot:
        print(json.dumps(take_snapshot(reason=args.reason), indent=2))
    elif args.restore:
        print(json.dumps(restore_session(revive_pm2=not args.dry_run, dry_run=args.dry_run), indent=2))
    elif args.rollback_file:
        print(json.dumps(rollback_code_file(args.rollback_file), indent=2))
    else:
        print(json.dumps(spine_status(), indent=2))


if __name__ == "__main__":
    main()
