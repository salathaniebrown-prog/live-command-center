#!/usr/bin/env python3
"""
SalathanieAI — Uninterrupted Telemetry Emitters System (telemetry_emitters.py)
Emits continuous, HMAC-signed telemetry packets across:
  1. SQLite WAL table (emitter_frames in alstra_flight_ledger.db)
  2. Append-only JSONL stream (builds/astra_jet/telemetry_emitters.jsonl)
  3. Local UDP broadcast socket (127.0.0.1:14560)
  4. Zero-copy shared-memory ring (hdc_shm_bus.py)
Additive-only: never replaces existing modules or services.
"""
import hashlib
import hmac
import json
import os
import socket
import sqlite3
import time
from pathlib import Path

import astra_flight_ledger as ledger
from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv, sample_silicon_side_channel

REPO = Path("/data/data/com.termux/files/home/live-command-center")
SPINE_DB = REPO / "alstra_flight_ledger.db"
EMITTER_JSONL = REPO / "builds" / "astra_jet" / "telemetry_emitters.jsonl"
UDP_PORT = 14560
HOME = Path.home()

_STATE = {
    "seq": 0,
    "last_emit_ts": 0,
    "channels": ["WAL_SQLITE", "JSONL_STREAM", "UDP_14560", "HDC_SHM"],
    "last_frame": None,
    "errors": 0,
}


def _db() -> sqlite3.Connection:
    SPINE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SPINE_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emitter_frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seq INT NOT NULL,
            ts INT NOT NULL,
            emitter TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def _sign(msg: str) -> str:
    kp = HOME / ".salathanie_hmac.key"
    key = kp.read_bytes()[:32] if kp.exists() else b"salathanie-telemetry-emitter-key"
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()[:24].upper()


def _host_metrics() -> dict:
    tot_kb = avail_kb = 0
    try:
        for ln in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ln.startswith("MemTotal:"):
                tot_kb = int(ln.split()[1])
            elif ln.startswith("MemAvailable:"):
                avail_kb = int(ln.split()[1])
    except OSError:
        pass
    ram_pct = round(((tot_kb - avail_kb) / tot_kb) * 100.0, 2) if tot_kb else 0.0
    try:
        hw = sample_silicon_side_channel()
    except Exception:
        hw = {"max_temp_mc": 42000, "jitter_ns": 0}
    temp_c = round(hw["max_temp_mc"] / 1000.0, 1) if 0 < hw["max_temp_mc"] < 105000 else 42.0
    try:
        load1 = round(os.getloadavg()[0], 2)
    except OSError:
        load1 = 0.0
    return {
        "ram_pct": ram_pct,
        "mem_avail_mb": avail_kb // 1024,
        "temp_c": temp_c,
        "load1": load1,
        "jitter_ns": hw["jitter_ns"],
    }


def _emit_udp(raw_bytes: bytes) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.sendto(raw_bytes[:4096], ("127.0.0.1", UDP_PORT))
        return True
    except Exception:
        return False


def _append_jsonl(raw_bytes: bytes) -> bool:
    try:
        EMITTER_JSONL.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(EMITTER_JSONL), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, raw_bytes + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        return True
    except Exception:
        return False


def emit_once(emitter: str = "UNINTERRUPTED_CORE", extra: dict | None = None) -> dict:
    """Emit a single telemetry packet across WAL SQLite, JSONL, UDP 14560, and HDC SHM."""
    ts = int(time.time())
    with _db() as c:
        last_seq = c.execute("SELECT COALESCE(MAX(seq), 0) FROM emitter_frames").fetchone()[0]
    seq = int(last_seq) + 1

    st = ledger.read_state_safe()
    px4 = ledger.latest_px4()
    host = _host_metrics()
    payload = {
        "seq": seq,
        "ts": ts,
        "emitter": emitter,
        "model": st.get("model", "SalathanieAI"),
        "active_gen": st.get("active_gen", "GEN-000"),
        "mode": st.get("mode", "AUTONOMOUS-MUTATE"),
        "pods": st.get("pods", [True, True, True, True]),
        "hazard_score": ledger.external_hazard_score(),
        "px4": {"vehicle_id": px4.get("vehicle_id"), "lat": px4.get("lat"), "lon": px4.get("lon"), "alt_m": px4.get("alt_m")},
        "host": host,
    }
    if isinstance(extra, dict) and extra:
        payload["extra"] = extra

    sig = _sign(f"{seq}|{ts}|{emitter}|{host['ram_pct']}|{payload['active_gen']}")
    payload["hmac_sig"] = sig
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    wal_ok = False
    try:
        with _db() as c:
            c.execute(
                "INSERT INTO emitter_frames(seq,ts,emitter,payload_json,hmac_sig) VALUES (?,?,?,?,?)",
                (seq, ts, emitter, encoded.decode("utf-8"), sig),
            )
            c.commit()
        wal_ok = True
    except Exception:
        _STATE["errors"] += 1

    jsonl_ok = _append_jsonl(encoded)
    udp_ok = _emit_udp(encoded)

    shm_ok = False
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-emitter", 8125, 200, deterministic_hv(f"emit:{seq}:{sig}"))
        shm_ok = True
    except Exception:
        pass

    frame = {
        "ok": True,
        "seq": seq,
        "ts": ts,
        "emitter": emitter,
        "channels_ok": {"wal": wal_ok, "jsonl": jsonl_ok, "udp_14560": udp_ok, "shm": shm_ok},
        "hmac_sig": sig,
        "payload": payload,
    }
    _STATE["seq"] = seq
    _STATE["last_emit_ts"] = ts
    _STATE["last_frame"] = frame
    return frame


def emitter_status(limit: int = 12) -> dict:
    with _db() as c:
        total = c.execute("SELECT COUNT(*) FROM emitter_frames").fetchone()[0]
        rows = c.execute(
            "SELECT seq,ts,emitter,payload_json,hmac_sig FROM emitter_frames ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    recent = []
    for seq, ts, em, pj, sig in rows:
        try:
            pobj = json.loads(pj)
        except Exception:
            pobj = {}
        recent.append({"seq": seq, "ts": ts, "emitter": em, "hmac_sig": sig, "payload": pobj})
    return {
        "ok": True,
        "ts": int(time.time()),
        "udp_port": UDP_PORT,
        "jsonl_path": str(EMITTER_JSONL),
        "wal_db": str(SPINE_DB),
        "total_emitted": total,
        "errors": _STATE["errors"],
        "recent": recent,
    }


if __name__ == "__main__":
    print(json.dumps(emit_once("CLI_BURST"), indent=2))
