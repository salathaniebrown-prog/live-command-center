#!/usr/bin/env python3
"""
SalathanieAI — Atomic State & SQLite WAL Flight-Recorder Ledger
- Database: ~/live-command-center/astra_flight_ledger.db (PRAGMA journal_mode=WAL)
- Atomic state persistence (temp file + os.replace) preserving manual pilot/pod/mode overrides
- Live external telemetry ingest: USGS Earthquakes, NWS Alerts (Triad NC), NASA EONET, PX4 Coordinates
"""
import hashlib
import hmac
import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "astra_flight_ledger.db"
JET_DIR = REPO / "builds" / "astra_jet"
STATE_FILE = JET_DIR / "alstra_jet_state.json"
TELEM_FILE = JET_DIR / "alstra_jet_telemetry.jsonl"
PX4_STREAM_FILE = Path.home() / "drone_telemetry_stream.json"
HOME = Path.home()

JET_DIR.mkdir(parents=True, exist_ok=True)


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS flight_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            gen_id TEXT NOT NULL,
            parent_gen TEXT,
            mode TEXT,
            pods_mask TEXT,
            pods_active INT,
            pilot_pitch REAL,
            pilot_roll REAL,
            pilot_thrust REAL,
            fitness REAL,
            prev_fitness REAL,
            promoted INT,
            ram_pct REAL,
            mem_avail_mb INT,
            temp_c REAL,
            ext_hazard_score REAL,
            px4_lat REAL,
            px4_lon REAL,
            px4_alt_m REAL,
            reason TEXT,
            genome_json TEXT,
            code_path TEXT,
            hmac_sig TEXT
        );
        CREATE TABLE IF NOT EXISTS external_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            source TEXT NOT NULL,
            event_id TEXT NOT NULL,
            title TEXT,
            severity TEXT,
            lat REAL,
            lon REAL,
            raw_json TEXT,
            UNIQUE(source, event_id)
        );
        CREATE TABLE IF NOT EXISTS px4_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            vehicle_id TEXT,
            lat REAL,
            lon REAL,
            alt_m REAL,
            rel_alt_m REAL,
            heading REAL,
            groundspeed REAL,
            battery_pct REAL,
            flight_mode TEXT,
            armed INT,
            source TEXT
        );
    """)
    return conn


def hmac_sign(payload: str) -> str:
    kp = HOME / ".salathanie_hmac.key"
    key = kp.read_bytes()[:32] if kp.exists() else b"salathanie-flight-ledger-key"
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24].upper()


def read_state_safe() -> dict:
    try:
        if STATE_FILE.exists():
            raw = STATE_FILE.read_text(encoding="utf-8").strip()
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return {}


def atomic_write_state(updates: dict, preserve_overrides: bool = True) -> dict:
    """Atomically merge state onto disk via temp+fsync+os.replace without clobbering manual overrides."""
    cur = read_state_safe()
    merged = dict(cur)
    for k, v in updates.items():
        if preserve_overrides and k in ("mode", "pods", "pilot_input") and k in cur:
            continue
        if k == "genome" and isinstance(v, dict) and isinstance(cur.get("genome"), dict):
            g = dict(v)
            # Preserve manual thrust_trim override if pilot recently moved stick/slider
            p_ts = int(cur.get("pilot_input", {}).get("ts", 0)) if isinstance(cur.get("pilot_input"), dict) else 0
            if preserve_overrides and (time.time() - p_ts) < 90 and "thrust_trim" in cur["genome"]:
                g["thrust_trim"] = cur["genome"]["thrust_trim"]
            merged["genome"] = g
        else:
            merged[k] = v
    merged["updated_ts"] = int(time.time())
    tmp = STATE_FILE.with_suffix(".json.tmp")
    data = json.dumps(merged, indent=2).encode("utf-8")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(STATE_FILE))
    return merged


def append_jsonl_atomic(rec: dict):
    line = (json.dumps(rec) + "\n").encode("utf-8")
    fd = os.open(str(TELEM_FILE), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)


def record_generation(entry: dict) -> str:
    ts = int(entry.get("ts", time.time()))
    sig = hmac_sign(
        f"{ts}|{entry.get('gen_id')}|{entry.get('fitness')}|{entry.get('pods_mask')}|"
        f"{entry.get('pilot_pitch')}|{entry.get('pilot_roll')}|{entry.get('promoted')}"
    )
    with db_conn() as c:
        c.execute(
            """INSERT INTO flight_generations (
                ts, gen_id, parent_gen, mode, pods_mask, pods_active,
                pilot_pitch, pilot_roll, pilot_thrust, fitness, prev_fitness, promoted,
                ram_pct, mem_avail_mb, temp_c, ext_hazard_score,
                px4_lat, px4_lon, px4_alt_m, reason, genome_json, code_path, hmac_sig
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts,
                entry.get("gen_id", "GEN-000"),
                entry.get("parent_gen", "ROOT"),
                entry.get("mode", "AUTONOMOUS-MUTATE"),
                entry.get("pods_mask", "1111"),
                int(entry.get("pods_active", 4)),
                float(entry.get("pilot_pitch", 0.0)),
                float(entry.get("pilot_roll", 0.0)),
                float(entry.get("pilot_thrust", 0.72)),
                float(entry.get("fitness", 0.0)),
                float(entry.get("prev_fitness", 0.0)),
                1 if entry.get("promoted") else 0,
                float(entry.get("ram_pct", 0.0)),
                int(entry.get("mem_avail_mb", 0)),
                float(entry.get("temp_c", 0.0)),
                float(entry.get("ext_hazard_score", 0.0)),
                float(entry.get("px4_lat", 36.0999)),
                float(entry.get("px4_lon", -80.2442)),
                float(entry.get("px4_alt_m", 0.0)),
                str(entry.get("reason", ""))[:240],
                json.dumps(entry.get("genome", {})),
                str(entry.get("code_path", "")),
                sig,
            ),
        )
    return sig


def record_px4(payload: dict, source: str = "px4_rest_api") -> dict:
    ts = int(payload.get("ts") or time.time())
    rec = {
        "ts": ts,
        "vehicle_id": str(payload.get("vehicle_id", "PX4-EAGLE-01"))[:32],
        "lat": round(float(payload.get("lat", 36.0999)), 6),
        "lon": round(float(payload.get("lon", -80.2442)), 6),
        "alt_m": round(float(payload.get("alt_m", payload.get("alt", 0.0))), 2),
        "rel_alt_m": round(float(payload.get("rel_alt_m", payload.get("rel_alt", 0.0))), 2),
        "heading": round(float(payload.get("heading", payload.get("hdg", 0.0))), 1),
        "groundspeed": round(float(payload.get("groundspeed", payload.get("speed", 0.0))), 2),
        "battery_pct": round(float(payload.get("battery_pct", payload.get("battery", 100.0))), 1),
        "flight_mode": str(payload.get("flight_mode", payload.get("mode", "POSCTL")))[:24],
        "armed": 1 if payload.get("armed") else 0,
        "source": source,
    }
    with db_conn() as c:
        c.execute(
            "INSERT INTO px4_telemetry (ts,vehicle_id,lat,lon,alt_m,rel_alt_m,heading,groundspeed,battery_pct,flight_mode,armed,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec["ts"], rec["vehicle_id"], rec["lat"], rec["lon"], rec["alt_m"],
                rec["rel_alt_m"], rec["heading"], rec["groundspeed"], rec["battery_pct"],
                rec["flight_mode"], rec["armed"], rec["source"],
            ),
        )
    return rec


def ingest_px4_file_if_present() -> dict | None:
    if PX4_STREAM_FILE.exists():
        try:
            raw = PX4_STREAM_FILE.read_text(encoding="utf-8").strip()
            if raw:
                data = json.loads(raw.splitlines()[-1])
                if isinstance(data, dict) and ("lat" in data or "latitude" in data):
                    if "latitude" in data and "lat" not in data:
                        data["lat"] = data["latitude"]
                    if "longitude" in data and "lon" not in data:
                        data["lon"] = data["longitude"]
                    return record_px4(data, source="drone_telemetry_stream")
        except Exception:
            pass
    return None


def _http_json(url: str, timeout: float = 5.0) -> dict | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "SalathanieAI-FlightLedger/1.0 (PiedmontTriadNC)",
                "Accept": "application/geo+json, application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None


def sync_external_feeds() -> dict:
    """Ingest real live USGS Earthquakes, NWS Alerts (Triad NC), NASA EONET, and local PX4 file into WAL DB."""
    ts = int(time.time())
    counts = {"USGS": 0, "NWS": 0, "EONET": 0, "PX4_FILE": 0}
    rows = []

    # 1. USGS Live Earthquakes (M2.5+ past 24h)
    usgs = _http_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson")
    if usgs and isinstance(usgs.get("features"), list):
        for f in usgs["features"][:6]:
            props = f.get("properties") or {}
            coords = (f.get("geometry") or {}).get("coordinates") or [0.0, 0.0]
            mag = props.get("mag", 0)
            sev = "HIGH" if (mag or 0) >= 5.0 else ("MODERATE" if (mag or 0) >= 3.5 else "LOW")
            rows.append((
                ts, "USGS", str(f.get("id", ts)),
                f"M{mag} {props.get('place', 'Earthquake')}",
                sev, float(coords[1] or 0.0), float(coords[0] or 0.0),
                json.dumps({"mag": mag, "place": props.get("place"), "time": props.get("time")}),
            ))
            counts["USGS"] += 1

    # 2. NWS Active Weather Alerts (Greensboro / Winston-Salem Triad NC)
    nws = _http_json("https://api.weather.gov/alerts/active?point=36.0726,-79.7920")
    if nws and isinstance(nws.get("features"), list):
        if nws["features"]:
            for f in nws["features"][:5]:
                props = f.get("properties") or {}
                rows.append((
                    ts, "NWS", str(f.get("id", f"nws-{ts}")),
                    str(props.get("headline") or props.get("event") or "NWS Alert")[:140],
                    str(props.get("severity", "INFO")).upper(),
                    36.0726, -79.7920,
                    json.dumps({"event": props.get("event"), "area": props.get("areaDesc")}),
                ))
                counts["NWS"] += 1
        else:
            rows.append((
                ts, "NWS", f"triad-clear-{ts // 300}",
                "NWS Triad NC: No active severe weather advisories",
                "NOMINAL", 36.0726, -79.7920, json.dumps({"status": "clear"}),
            ))
            counts["NWS"] += 1

    # 3. NASA EONET v3 Open Natural Events
    eonet = _http_json("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=5")
    if eonet and isinstance(eonet.get("events"), list):
        for ev in eonet["events"][:5]:
            geoms = ev.get("geometry") or []
            g0 = geoms[-1] if geoms else {}
            coords = g0.get("coordinates") if isinstance(g0.get("coordinates"), list) else [0.0, 0.0]
            lon = float(coords[0]) if len(coords) >= 2 and isinstance(coords[0], (int, float)) else 0.0
            lat = float(coords[1]) if len(coords) >= 2 and isinstance(coords[1], (int, float)) else 0.0
            cats = [c.get("title", "") for c in (ev.get("categories") or [])]
            rows.append((
                ts, "EONET", str(ev.get("id", ts)),
                f"{ev.get('title', 'Event')} [{', '.join(cats)}]",
                "ALERT", lat, lon,
                json.dumps({"categories": cats, "date": g0.get("date")}),
            ))
            counts["EONET"] += 1

    with db_conn() as c:
        for r in rows:
            c.execute(
                "INSERT OR REPLACE INTO external_feeds (ts,source,event_id,title,severity,lat,lon,raw_json) VALUES (?,?,?,?,?,?,?,?)",
                r,
            )

    if ingest_px4_file_if_present():
        counts["PX4_FILE"] = 1

    return {"ok": True, "ts": ts, "ingested": counts}


def latest_px4() -> dict:
    with db_conn() as c:
        r = c.execute(
            "SELECT ts,vehicle_id,lat,lon,alt_m,rel_alt_m,heading,groundspeed,battery_pct,flight_mode,armed,source FROM px4_telemetry ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if r:
        return {
            "ts": r[0], "vehicle_id": r[1], "lat": r[2], "lon": r[3], "alt_m": r[4],
            "rel_alt_m": r[5], "heading": r[6], "groundspeed": r[7], "battery_pct": r[8],
            "flight_mode": r[9], "armed": bool(r[10]), "source": r[11],
        }
    return {
        "ts": int(time.time()), "vehicle_id": "PX4-EAGLE-01", "lat": 36.0999, "lon": -80.2442,
        "alt_m": 274.0, "rel_alt_m": 0.0, "heading": 0.0, "groundspeed": 0.0,
        "battery_pct": 100.0, "flight_mode": "FRIA_STANDBY", "armed": False, "source": "fria_home_standby",
    }


def external_hazard_score() -> float:
    """Compute a 0.0-1.0 real environmental hazard score from recent USGS/NWS/EONET rows in WAL DB."""
    cutoff = int(time.time()) - 3600
    score = 0.0
    with db_conn() as c:
        rows = c.execute("SELECT source, severity FROM external_feeds WHERE ts >= ? ORDER BY id DESC LIMIT 20", (cutoff,)).fetchall()
    for src, sev in rows:
        s = (sev or "").upper()
        if src == "NWS" and s not in ("NOMINAL", "INFO", ""):
            score += 0.35
        elif src == "USGS" and s == "HIGH":
            score += 0.20
        elif src == "EONET":
            score += 0.05
    return round(min(1.0, score), 3)


def wal_checkpoint() -> dict:
    with db_conn() as c:
        row = c.execute("PRAGMA wal_checkpoint(PASSIVE);").fetchone()
    wal_file = Path(str(DB_PATH) + "-wal")
    return {
        "ok": True,
        "busy": row[0] if row else 0,
        "log_pages": row[1] if row else 0,
        "checkpointed_pages": row[2] if row else 0,
        "db_kb": round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0.0,
        "wal_kb": round(wal_file.stat().st_size / 1024, 1) if wal_file.exists() else 0.0,
    }


def get_ledger_snapshot(limit: int = 20) -> dict:
    with db_conn() as c:
        gens = [
            {
                "id": r[0], "ts": r[1], "gen_id": r[2], "parent_gen": r[3], "mode": r[4],
                "pods_mask": r[5], "pods_active": r[6], "pilot_pitch": r[7], "pilot_roll": r[8],
                "pilot_thrust": r[9], "fitness": r[10], "prev_fitness": r[11], "promoted": bool(r[12]),
                "ram_pct": r[13], "mem_avail_mb": r[14], "temp_c": r[15], "ext_hazard_score": r[16],
                "px4_lat": r[17], "px4_lon": r[18], "px4_alt_m": r[19], "reason": r[20], "hmac_sig": r[21],
            }
            for r in c.execute(
                """SELECT id,ts,gen_id,parent_gen,mode,pods_mask,pods_active,pilot_pitch,pilot_roll,
                          pilot_thrust,fitness,prev_fitness,promoted,ram_pct,mem_avail_mb,temp_c,
                          ext_hazard_score,px4_lat,px4_lon,px4_alt_m,reason,hmac_sig
                   FROM flight_generations ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        ]
        feeds = [
            {"ts": r[0], "source": r[1], "event_id": r[2], "title": r[3], "severity": r[4], "lat": r[5], "lon": r[6]}
            for r in c.execute(
                "SELECT ts,source,event_id,title,severity,lat,lon FROM external_feeds ORDER BY ts DESC, id DESC LIMIT 15"
            ).fetchall()
        ]
        px4_hist = [
            {"ts": r[0], "vehicle_id": r[1], "lat": r[2], "lon": r[3], "alt_m": r[4], "heading": r[5], "groundspeed": r[6], "battery_pct": r[7], "flight_mode": r[8], "armed": bool(r[9]), "source": r[10]}
            for r in c.execute(
                "SELECT ts,vehicle_id,lat,lon,alt_m,heading,groundspeed,battery_pct,flight_mode,armed,source FROM px4_telemetry ORDER BY id DESC LIMIT 10"
            ).fetchall()
        ]
        totals = {
            "generations": c.execute("SELECT COUNT(*) FROM flight_generations").fetchone()[0],
            "external_events": c.execute("SELECT COUNT(*) FROM external_feeds").fetchone()[0],
            "px4_points": c.execute("SELECT COUNT(*) FROM px4_telemetry").fetchone()[0],
        }
    return {
        "ts": int(time.time()),
        "db_path": str(DB_PATH),
        "wal": wal_checkpoint(),
        "totals": totals,
        "px4_latest": latest_px4(),
        "hazard_score": external_hazard_score(),
        "generations": gens,
        "external_feeds": feeds,
        "px4_history": px4_hist,
    }


if __name__ == "__main__":
    print(json.dumps({"sync": sync_external_feeds(), "ledger": get_ledger_snapshot(5)}, indent=2))
