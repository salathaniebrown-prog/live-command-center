#!/usr/bin/env python3
"""
SalathanieAI — Upgraded Astra + Alstra Closed-Loop Jet Bridge
Fuses 4 sensor pods (SAR-LIDAR, RF-MESH, OPTIC-IR, AUX-POD), pilot stick vectors,
host silicon telemetry, live USGS/NWS/EONET feeds, and PX4 drone coordinates (UDP 14550)
directly into the 3-worker supercomputer genome fitness evaluator & SQLite WAL flight recorder.
"""
import ast
import concurrent.futures
import json
import math
import py_compile
import random
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

import astra_flight_ledger as ledger
from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv, sample_silicon_side_channel

REPO = Path("/data/data/com.termux/files/home/live-command-center")
MUT_DIR = REPO / "builds" / "astra_jet" / "mutations"
MUT_DIR.mkdir(parents=True, exist_ok=True)

RUNNING = True
MESH_PORTS = (8090, 8099, 8125, 8126, 8151, 8182)
DEFAULT_GENOME = {
    "kp_pitch": 0.52,
    "kd_pitch": 0.25,
    "kp_roll": 0.56,
    "kd_roll": 0.26,
    "thrust_trim": 0.68,
    "thermal_derate": 0.78,
}


def _host_ram() -> dict:
    tot = avail = 0
    try:
        for ln in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ln.startswith("MemTotal:"):
                tot = int(ln.split()[1])
            elif ln.startswith("MemAvailable:"):
                avail = int(ln.split()[1])
    except OSError:
        pass
    pct = round(((tot - avail) / tot) * 100.0, 2) if tot > 0 else 0.0
    return {"ram_pct": pct, "mem_avail_mb": avail // 1024}


def _pm2_workers() -> tuple[int, int]:
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=4)
        if r.returncode == 0 and r.stdout.strip().startswith("["):
            arr = json.loads(r.stdout)
            on = sum(1 for p in arr if p.get("pm2_env", {}).get("status") == "online")
            return on, len(arr)
    except Exception:
        pass
    return 1, 1


def _probe_mesh() -> int:
    up = 0
    for port in MESH_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                up += 1
    return up


def _render_ctrl(gen_id: str, g: dict) -> str:
    return f'''#!/usr/bin/env python3
"""Closed-Loop Fused Astra+Alstra Control Law — {gen_id}"""
GEN_ID = "{gen_id}"
PARAMS = {json.dumps(g, indent=2)}

def step_control(state: dict, stick: dict, pods: list, hazard: float) -> dict:
    p = PARAMS
    pod_gain = 0.75 + 0.25 * (sum(1 for x in pods if x) / 4.0)
    target_pitch = stick.get("pitch", 0.0) * 12.0
    target_roll = stick.get("roll", 0.0) * 24.0
    pitch_cmd = max(-15.0, min(15.0, (target_pitch - state["pitch"]) * p["kp_pitch"] * pod_gain - state["pitch"] * p["kd_pitch"] * (1.0 + hazard * 0.4)))
    roll_cmd = max(-30.0, min(30.0, (target_roll - state["roll"]) * p["kp_roll"] * pod_gain - state["roll"] * p["kd_roll"] * (1.0 + hazard * 0.4)))
    thr = max(0.15, min(1.0, (p["thrust_trim"] * 0.55) + (stick.get("thrust", p["thrust_trim"]) * 0.45)))
    if state.get("ram_pct", 0.0) > 84.0 or state.get("temp_c", 40.0) > 65.0:
        thr = min(thr, p["thermal_derate"])
    return {{"pitch_cmd": round(pitch_cmd, 4), "roll_cmd": round(roll_cmd, 4), "throttle": round(thr, 4)}}
'''


def evaluate_fused_genome(gen_id: str, g: dict, ctx: dict) -> dict:
    """Evaluate genome fitness fused with active pods, pilot stick vector, host RAM/temp, and external hazards."""
    code = _render_ctrl(gen_id, g)
    ast.parse(code)
    ns = {}
    exec(compile(code, f"<{gen_id}>", "exec"), ns, ns)
    fn = ns["step_control"]

    pods = ctx["pods"]
    stick = ctx["stick"]
    hazard = ctx["hazard"]
    mode = ctx["mode"]
    ram_pct = ctx["ram_pct"]
    temp_c = ctx["temp_c"]
    mesh_ratio = ctx["mesh_ratio"]

    sim = {"pitch": 2.5, "roll": 5.0, "ram_pct": ram_pct, "temp_c": temp_c}
    turb_amp = 4.2 if mode == "TURBULENCE-LOCK" else (1.5 if mode == "CRUISE-VECTOR" else 2.8)
    turb_amp *= (1.0 + hazard * 0.65)
    target_p = stick["pitch"] * 12.0
    target_r = stick["roll"] * 24.0

    err_sum = 0.0
    for step in range(20):
        gust_p = math.sin(step * 0.85) * turb_amp
        gust_r = math.cos(step * 0.65) * turb_amp * 1.4
        cmd = fn(sim, stick, pods, hazard)
        sim["pitch"] = sim["pitch"] * 0.52 + (cmd["pitch_cmd"] + gust_p * (0.65 if pods[0] else 1.0)) * 0.48
        sim["roll"] = sim["roll"] * 0.50 + (cmd["roll_cmd"] + gust_r * (0.70 if pods[2] else 1.0)) * 0.50
        p_err = abs(target_p - sim["pitch"]) * 0.22
        r_err = abs(target_r - sim["roll"]) * 0.14
        therm_pen = max(0.0, (cmd["throttle"] - 0.80) * 6.0) if (ram_pct > 84.0 or temp_c > 65.0 or mode == "THERMAL-DERATE") else 0.0
        err_sum += p_err + r_err + therm_pen

    pod_bonus = (sum(1 for b in pods if b) / 4.0) * 6.0
    mesh_bonus = mesh_ratio * 2.5
    fitness = round(max(0.0, min(100.0, 91.5 + pod_bonus + mesh_bonus - (err_sum / 20.0) * 6.2)), 3)
    return {"gen_id": gen_id, "fitness": fitness, "params": g, "code": code}


def _mutate_candidate(base: dict, scale: float) -> dict:
    m = dict(base)
    m["kp_pitch"] = round(max(0.15, min(1.35, m["kp_pitch"] + random.uniform(-0.12, 0.12) * scale)), 4)
    m["kd_pitch"] = round(max(0.08, min(0.85, m["kd_pitch"] + random.uniform(-0.10, 0.10) * scale)), 4)
    m["kp_roll"] = round(max(0.15, min(1.45, m["kp_roll"] + random.uniform(-0.14, 0.14) * scale)), 4)
    m["kd_roll"] = round(max(0.08, min(0.85, m["kd_roll"] + random.uniform(-0.10, 0.10) * scale)), 4)
    m["thrust_trim"] = round(max(0.35, min(0.92, m["thrust_trim"] + random.uniform(-0.06, 0.06) * scale)), 4)
    m["thermal_derate"] = round(max(0.55, min(0.86, m["thermal_derate"] + random.uniform(-0.05, 0.05) * scale)), 4)
    return m


def run_closed_loop_cycle(force_external_sync: bool = False) -> dict:
    if force_external_sync:
        ledger.sync_external_feeds()

    st = ledger.read_state_safe()
    mode = st.get("mode", "AUTONOMOUS-MUTATE")
    pods = st.get("pods") if isinstance(st.get("pods"), list) and len(st.get("pods")) == 4 else [True, True, True, True]
    pin = st.get("pilot_input") if isinstance(st.get("pilot_input"), dict) else {}
    genome = dict(DEFAULT_GENOME)
    if isinstance(st.get("genome"), dict):
        genome.update({k: float(v) for k, v in st["genome"].items() if k in DEFAULT_GENOME})

    stick = {
        "pitch": float(pin.get("pitch", 0.0)),
        "roll": float(pin.get("roll", 0.0)),
        "thrust": float(pin.get("thrust", genome["thrust_trim"])),
    }
    ram = _host_ram()
    hw = sample_silicon_side_channel()
    temp_c = round(hw["max_temp_mc"] / 1000.0, 1) if 0 < hw["max_temp_mc"] < 105000 else 42.0
    pm2_on, pm2_tot = _pm2_workers()
    mesh_up = _probe_mesh()
    px4 = ledger.latest_px4()
    hazard = ledger.external_hazard_score()

    ctx = {
        "mode": mode, "pods": pods, "stick": stick, "hazard": hazard,
        "ram_pct": ram["ram_pct"], "temp_c": temp_c, "mesh_ratio": mesh_up / len(MESH_PORTS),
    }

    base_eval = evaluate_fused_genome("CHAMP", genome, ctx)
    with ledger.db_conn() as c:
        gen_num = c.execute("SELECT COUNT(*) FROM flight_generations").fetchone()[0] + 1
    parent_gen = st.get("active_gen", f"GEN-{max(0, gen_num - 1):03d}")
    next_gen = f"GEN-{gen_num:03d}"

    candidates = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(evaluate_fused_genome, f"C{i}", _mutate_candidate(genome, 0.9 if i < 3 else 0.4), ctx) for i in range(6)]
        for f in concurrent.futures.as_completed(futs):
            candidates.append(f.result())

    best = max(candidates, key=lambda x: x["fitness"])
    promoted = False
    code_path = st.get("code_path", "")
    win_genome = dict(genome)
    win_fitness = base_eval["fitness"]
    reason = f"HOLD {parent_gen} (fit={base_eval['fitness']} >= best={best['fitness']} | pods={sum(pods)}/4 | hazard={hazard})"

    if best["fitness"] > base_eval["fitness"] and mode in ("AUTONOMOUS-MUTATE", "TURBULENCE-LOCK"):
        fp = MUT_DIR / f"bridge_{next_gen.lower().replace('-', '_')}.py"
        fp.write_text(best["code"].replace('"C0"', f'"{next_gen}"'), encoding="utf-8")
        py_compile.compile(str(fp), doraise=True)
        promoted = True
        win_genome = dict(best["params"])
        win_fitness = best["fitness"]
        code_path = str(fp)
        delta = round(win_fitness - base_eval["fitness"], 3)
        reason = f"PROMOTED {next_gen}: +{delta} fused gain (pods={sum(pods)}/4 stick=({stick['pitch']:.2f},{stick['roll']:.2f}) hazard={hazard} ast+py_compile OK)"
    else:
        next_gen = parent_gen

    ts = int(time.time())
    pods_mask = "".join("1" if b else "0" for b in pods)

    sig = ledger.record_generation({
        "ts": ts, "gen_id": next_gen, "parent_gen": parent_gen, "mode": mode,
        "pods_mask": pods_mask, "pods_active": sum(1 for b in pods if b),
        "pilot_pitch": stick["pitch"], "pilot_roll": stick["roll"], "pilot_thrust": stick["thrust"],
        "fitness": win_fitness, "prev_fitness": base_eval["fitness"], "promoted": promoted,
        "ram_pct": ram["ram_pct"], "mem_avail_mb": ram["mem_avail_mb"], "temp_c": temp_c,
        "ext_hazard_score": hazard, "px4_lat": px4["lat"], "px4_lon": px4["lon"], "px4_alt_m": px4["alt_m"],
        "reason": reason, "genome": win_genome, "code_path": code_path,
    })

    # Atomic state update preserving user overrides
    ledger.atomic_write_state(
        {"model": "SalathanieAI", "active_gen": next_gen, "fitness": win_fitness, "genome": win_genome, "code_path": code_path, "last_hmac": sig},
        preserve_overrides=True,
    )

    telem_rec = {
        "ts": ts,
        "model": "SalathanieAI",
        "gen_id": next_gen,
        "new_fitness": win_fitness,
        "promoted": promoted,
        "reason": reason,
        "hmac_sig": sig,
        "telemetry": {
            "workers": f"{pm2_on}/{pm2_tot} PM2 | 3W",
            "turbulence": round(0.25 + hazard * 0.5, 2),
            "pods_mask": pods_mask,
            "pilot_stick": stick,
            "px4": px4,
            "host": {"ram_pct": ram["ram_pct"], "mem_avail_mb": ram["mem_avail_mb"], "temp_c": temp_c, "jitter_ns": hw["jitter_ns"]},
        },
    }
    ledger.append_jsonl_atomic(telem_rec)

    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-jet-bridge", 8099, 200, deterministic_hv(f"bridge:{next_gen}:{pods_mask}:{win_fitness}"))
    except Exception:
        pass

    return telem_rec


def _px4_udp_listener():
    """Listen on UDP 127.0.0.1:14550 for live JSON-formatted PX4/MAVLink drone coordinate packets."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 14550))
        sock.settimeout(2.0)
    except OSError:
        return
    while RUNNING:
        try:
            data, _ = sock.recvfrom(4096)
            msg = json.loads(data.decode("utf-8", errors="ignore"))
            if isinstance(msg, dict) and ("lat" in msg or "latitude" in msg):
                if "latitude" in msg and "lat" not in msg:
                    msg["lat"] = msg["latitude"]
                if "longitude" in msg and "lon" not in msg:
                    msg["lon"] = msg["longitude"]
                ledger.record_px4(msg, source="px4_live_udp_14550")
        except socket.timeout:
            continue
        except Exception:
            continue


def _stop_sig(signum, frame):
    global RUNNING
    RUNNING = False


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _stop_sig)
    signal.signal(signal.SIGINT, _stop_sig)
    threading.Thread(target=_px4_udp_listener, daemon=True).start()
    tick = 0
    while RUNNING:
        try:
            run_closed_loop_cycle(force_external_sync=(tick % 8 == 0))
            if tick % 12 == 0:
                ledger.wal_checkpoint()
        except Exception as e:
            print(f"[BRIDGE WARN] {e}", flush=True)
        tick += 1
        for _ in range(10):
            if not RUNNING:
                break
            time.sleep(1)
