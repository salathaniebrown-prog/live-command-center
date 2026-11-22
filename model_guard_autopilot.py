#!/usr/bin/env python3
"""
Salathanie A.I — Termux Autopilot & Strong Model Guard
1. Model Gate: Overnight spend lock, per-minute loop breaker, daily LLM/Cloud caps.
2. Hardware Guard: Monitors MemAvailable (<420MB) & die temp (>68C), sheds heavy workers.
3. Process Guard: Stops crash-looping (>5 restarts) or rogue legacy astra-* processes.
4. Data Guard: Periodic SQLite WAL checkpoints + HMAC-attested HDC ring heartbeats.
"""
import argparse
import json
import os
import signal
import sqlite3
import subprocess
import time
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv, sample_silicon_side_channel

REPO = Path("/data/data/com.termux/files/home/live-command-center")
POLICY_PATH = Path.home() / ".salathanie_model_guard.json"
STATE_PATH = Path("/data/data/com.termux/files/usr/tmp/salathanie_guard_state.json")
LOG_PATH = REPO / "autopilot_guard.log"

DEFAULT_POLICY = {
    "overnight_lock": True,
    "allow_offline_fallback": True,
    "max_llm_calls_per_day": 100,
    "max_calls_per_minute": 8,
    "max_creative_usd_per_day": 5.0,
    "min_mem_avail_mb": 420,
    "max_temp_c": 68.0,
    "max_pm2_restarts": 5,
    "shed_order": ["salathanie-pulsar-10k", "salathanie-gw-8090", "salathanie-ingress-8088"],
}

RUNNING = True


def _log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_policy() -> dict:
    pol = dict(DEFAULT_POLICY)
    if POLICY_PATH.exists():
        try:
            pol.update(json.loads(POLICY_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return pol


def save_policy(updates: dict) -> dict:
    pol = load_policy()
    pol.update(updates)
    fd = os.open(str(POLICY_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(pol, indent=2).encode("utf-8"))
    finally:
        os.close(fd)
    return pol


def _load_state() -> dict:
    today = time.strftime("%Y-%m-%d")
    st = {"date": today, "llm_calls": 0, "creative_usd": 0.0, "recent_ts": []}
    if STATE_PATH.exists():
        try:
            raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if raw.get("date") == today:
                st.update(raw)
        except Exception:
            pass
    return st


def _save_state(st: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, indent=2), encoding="utf-8")


def check_model_gate(kind: str = "llm", est_cost_usd: float = 0.0) -> tuple[bool, str]:
    """Gate every outbound LLM or live creative API call against policy limits."""
    pol = load_policy()
    st = _load_state()
    now = time.time()

    if pol.get("overnight_lock"):
        return False, "MODEL_GUARD: overnight_lock active (run ./morning_resume.sh tomorrow to unlock live APIs)"

    # Per-minute runaway loop breaker
    recent = [t for t in st.get("recent_ts", []) if now - t < 60.0]
    if len(recent) >= int(pol["max_calls_per_minute"]):
        return False, f"MODEL_GUARD: rate limit hit ({pol['max_calls_per_minute']}/min loop protection)"

    if kind == "llm":
        if st["llm_calls"] >= int(pol["max_llm_calls_per_day"]):
            return False, f"MODEL_GUARD: daily LLM cap reached ({pol['max_llm_calls_per_day']}/day)"
        st["llm_calls"] += 1
    elif kind == "creative":
        projected = round(float(st["creative_usd"]) + float(est_cost_usd), 3)
        if projected > float(pol["max_creative_usd_per_day"]):
            return False, f"MODEL_GUARD: daily creative spend cap exceeded (${projected} > ${pol['max_creative_usd_per_day']})"
        st["creative_usd"] = projected

    recent.append(now)
    st["recent_ts"] = recent[-30:]
    _save_state(st)
    return True, "ALLOWED"


def checkpoint_all_sqlite():
    """Flush SQLite WAL files cleanly so overnight state is crash-safe."""
    flushed = []
    for db in sorted(REPO.glob("*.db")):
        try:
            conn = sqlite3.connect(str(db), timeout=3.0)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.close()
            flushed.append(db.name)
        except Exception as e:
            _log(f"[WARN] WAL checkpoint skipped for {db.name}: {e}")
    return flushed


def _pm2_jlist() -> list[dict]:
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=8)
        if r.returncode == 0 and r.stdout.strip().startswith("["):
            return json.loads(r.stdout)
    except Exception:
        pass
    return []


def guard_cycle(tick: int):
    pol = load_policy()
    metrics = sample_silicon_side_channel()
    mem_mb = metrics["mem_avail_kb"] // 1024
    temp_c = round(metrics["max_temp_mc"] / 1000.0, 1) if metrics["max_temp_mc"] > 0 else 0.0

    procs = _pm2_jlist()
    online_names = set()
    actions = []

    for p in procs:
        name = p.get("name", "")
        env = p.get("pm2_env", {})
        status = env.get("status", "")
        restarts = int(env.get("restart_time", 0))

        # Preserve all user astra-* services (additive-only policy)

        if status == "online":
            online_names.add(name)
            # 2. Stop runaway crash-loopers (excluding self & pilot)
            if restarts > int(pol["max_pm2_restarts"]) and name not in ("salathanie-guard", "salathanie-pilot"):
                subprocess.run(["pm2", "stop", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                actions.append(f"circuit_tripped:{name}(restarts={restarts})")

    # 3. Hardware RAM & Thermal Shedding
    ram_low = 0 < mem_mb < int(pol["min_mem_avail_mb"])
    hot = temp_c > float(pol["max_temp_c"]) and temp_c < 105.0
    if ram_low or hot:
        reason = f"ram={mem_mb}MB" if ram_low else f"temp={temp_c}C"
        for victim in pol["shed_order"]:
            if victim in online_names:
                subprocess.run(["pm2", "stop", victim], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                actions.append(f"shed:{victim}({reason})")
                break

    # 4. Periodic SQLite WAL checkpoint every ~10 minutes (40 ticks * 15s)
    if tick % 40 == 0:
        try:
            import astra_memory_spine as _spine
            _spine.take_snapshot(reason='autopilot_periodic', save_pm2_dump=False)
        except Exception:
            pass
        dbs = checkpoint_all_sqlite()
        if dbs and tick == 0:
            actions.append(f"wal_checkpoint:{len(dbs)}dbs")

    # 5. Publish HMAC-attested heartbeat to shared memory ring
    state_tag = f"guard:mem={mem_mb}MB:lock={int(pol['overnight_lock'])}:act={len(actions)}"
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-guard", 0, 200, deterministic_hv(state_tag))
    except Exception:
        pass

    if actions or tick % 20 == 0:
        _log(f"AUTOPILOT mem={mem_mb}MB temp={temp_c}C lock={pol['overnight_lock']} online={len(online_names)} actions={actions or ['NOMINAL']}")


def _stop_handler(signum, frame):
    global RUNNING
    RUNNING = False


def main():
    p = argparse.ArgumentParser(description="Salathanie Termux Autopilot Model Guard")
    p.add_argument("--daemon", action="store_true", help="Run continuous 15s autopilot loop")
    p.add_argument("--lock", action="store_true", help="Enable overnight model lock")
    p.add_argument("--unlock", action="store_true", help="Disable overnight model lock for live work")
    p.add_argument("--checkpoint", action="store_true", help="Flush all SQLite WAL databases now")
    p.add_argument("--status", action="store_true", help="Print policy & daily usage counters")
    args = p.parse_args()

    if args.lock:
        save_policy({"overnight_lock": True})
        _log("[GUARD] Overnight model lock ENABLED (live cloud APIs blocked; offline safe mode active)")
    if args.unlock:
        save_policy({"overnight_lock": False})
        _log("[GUARD] Overnight model lock DISABLED (live APIs unlocked under daily caps)")
    if args.checkpoint:
        dbs = checkpoint_all_sqlite()
        print(json.dumps({"checkpointed_dbs": dbs}, indent=2))
    if args.status or not (args.daemon or args.lock or args.unlock or args.checkpoint):
        print(json.dumps({"policy": load_policy(), "usage_today": _load_state()}, indent=2))
    if args.daemon:
        signal.signal(signal.SIGTERM, _stop_handler)
        signal.signal(signal.SIGINT, _stop_handler)
        _log("[GUARD] Salathanie Autopilot Model Guard online (15s patrol)")
        tick = 0
        while RUNNING:
            guard_cycle(tick)
            tick += 1
            for _ in range(15):
                if not RUNNING:
                    break
                time.sleep(1)


if __name__ == "__main__":
    main()
