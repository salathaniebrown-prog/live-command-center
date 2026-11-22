#!/usr/bin/env python3
"""
Salathanie A.I — Virtual Astra Jet + AI Supercomputing Telemetry + Self-Mutating Engine
- Pure stdlib + SQLite WAL + Zero-Copy HDC Ring (~0 extra PM2 processes)
- 3-worker parallel genome evaluation (RAM-safe for Android/Termux)
- Verified code synthesis (py_compile + simulation fitness gate + HMAC lineage + rollback)
"""
import concurrent.futures
import hashlib
import hmac
import importlib.util
import json
import math
import os
import py_compile
import random
import sqlite3
import time
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv, sample_silicon_side_channel
from llm_bridge import enhance_with_llm

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "salathanie_astra_jet.db"
MUT_DIR = REPO / "builds" / "astra_jet" / "mutations"
HOME = Path.home()

DEFAULT_GENOME = {
    "kp_pitch": 0.42,
    "kd_pitch": 0.18,
    "kp_roll": 0.48,
    "kd_roll": 0.20,
    "thrust_trim": 0.72,
    "thermal_derate": 0.85,
    "target_alt_ft": 38000.0,
    "target_mach": 1.65,
}

JET_STATE = {
    "callsign": "ASTRA-JET-01",
    "lat": 36.0977,   # KGSO Greensboro, NC
    "lon": -79.9373,
    "alt_ft": 36500.0,
    "mach": 1.52,
    "heading": 72.0,
    "pitch": 1.8,
    "roll": 0.4,
    "g_load": 1.02,
    "egt_c": 715.0,
    "fuel_pct": 94.0,
    "active_gen": "GEN-000",
    "fitness": 0.0,
    "last_fault": "NOMINAL",
}


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jet_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT, lat REAL, lon REAL, alt_ft REAL, mach REAL,
            heading REAL, pitch REAL, roll REAL, g_load REAL,
            egt_c REAL, fuel_pct REAL, fitness REAL, gen_id TEXT,
            mem_mb INT, jitter_ns INT, fault TEXT
        );
        CREATE TABLE IF NOT EXISTS jet_mutations (
            gen_id TEXT PRIMARY KEY,
            parent_gen TEXT,
            ts INT,
            fitness REAL,
            prev_fitness REAL,
            promoted INT,
            reason TEXT,
            params_json TEXT,
            code_path TEXT,
            code_sha256 TEXT,
            hmac_sig TEXT
        );
    """)
    return conn


def _hmac_sign(payload: str) -> str:
    kp = HOME / ".salathanie_hmac.key"
    key = kp.read_bytes()[:32] if kp.exists() else b"salathanie-astra-jet-key"
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24].upper()


def _pub_ring(tag: str):
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-astra-jet", 8125, 200, deterministic_hv(f"jet:{tag}"))
    except Exception:
        pass


def render_control_module(gen_id: str, g: dict) -> str:
    """Synthesize a standalone, deterministic Python flight-control law module."""
    return f'''#!/usr/bin/env python3
"""Auto-mutated Astra Jet Control Law — {gen_id}"""
GEN_ID = "{gen_id}"
PARAMS = {json.dumps(g, indent=2)}

def compute_control(state: dict, disturbance: dict) -> dict:
    p = PARAMS
    alt_err = (p["target_alt_ft"] - state["alt_ft"]) / 4000.0
    mach_err = p["target_mach"] - state["mach"]
    pitch_cmd = max(-15.0, min(15.0, (alt_err * p["kp_pitch"] * 10.0) - (state["pitch"] * p["kd_pitch"]) + disturbance.get("pitch_gust", 0.0)))
    roll_cmd = max(-30.0, min(30.0, -(state["roll"] * p["kp_roll"]) + disturbance.get("roll_gust", 0.0) * (1.0 - p["kd_roll"])))
    throttle = max(0.25, min(1.0, p["thrust_trim"] + (mach_err * 0.45)))
    if state.get("mem_mb", 600) < 420 or state.get("temp_c", 45.0) > 65.0:
        throttle = min(throttle, p["thermal_derate"])
    return {{
        "pitch_cmd": round(pitch_cmd, 4),
        "roll_cmd": round(roll_cmd, 4),
        "throttle": round(throttle, 4),
    }}
'''


def _load_and_score_genome(gen_id: str, g: dict, fault: str = "turbulence", write_artifact: bool = False) -> dict:
    """Evaluate genome fitness across a 24-step physics + fault benchmark."""
    code = render_control_module(gen_id, g)
    sha = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
    code_path = ""

    if write_artifact:
        MUT_DIR.mkdir(parents=True, exist_ok=True)
        fp = MUT_DIR / f"ctrl_{gen_id.lower().replace('-', '_')}.py"
        fp.write_text(code, encoding="utf-8")
        py_compile.compile(str(fp), doraise=True)
        code_path = str(fp)
        spec = importlib.util.spec_from_file_location(f"ctrl_{gen_id}", fp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ctrl_fn = mod.compute_control
    else:
        ns = {}
        exec(compile(code, f"<{gen_id}>", "exec"), ns, ns)
        ctrl_fn = ns["compute_control"]

    # Deterministic fault scenarios for fair A/B fitness comparison
    sim = {"alt_ft": 36200.0, "mach": 1.48, "pitch": 3.5, "roll": 8.0, "mem_mb": 560, "temp_c": 52.0}
    total_penalty = 0.0
    fuel_used = 0.0

    for step in range(24):
        if fault == "turbulence":
            dist = {"pitch_gust": math.sin(step * 0.9) * 3.2, "roll_gust": math.cos(step * 0.7) * 6.5}
        elif fault == "thermal_spike":
            sim["temp_c"] = 72.0 if step > 6 else 52.0
            dist = {"pitch_gust": math.sin(step * 0.5) * 1.4, "roll_gust": math.cos(step * 0.4) * 2.0}
        elif fault == "hypersonic_dash":
            dist = {"pitch_gust": 1.2 if step < 8 else -0.5, "roll_gust": math.sin(step) * 3.0}
        else:
            dist = {"pitch_gust": 0.4 * math.sin(step), "roll_gust": 0.8 * math.cos(step)}

        cmd = ctrl_fn(sim, dist)
        sim["pitch"] = sim["pitch"] * 0.55 + cmd["pitch_cmd"] * 0.45
        sim["roll"] = sim["roll"] * 0.50 + cmd["roll_cmd"] * 0.50
        sim["alt_ft"] += sim["pitch"] * 110.0
        sim["mach"] = max(0.6, min(2.4, sim["mach"] + (cmd["throttle"] - 0.68) * 0.18 - abs(sim["roll"]) * 0.002))
        fuel_used += cmd["throttle"] * 0.14

        alt_err = abs(g["target_alt_ft"] - sim["alt_ft"]) / 1000.0
        mach_err = abs(g["target_mach"] - sim["mach"]) * 3.5
        att_pen = (abs(sim["pitch"]) * 0.12) + (abs(sim["roll"]) * 0.08)
        therm_pen = max(0.0, (cmd["throttle"] - 0.82) * 4.0) if sim["temp_c"] > 65.0 else 0.0
        total_penalty += alt_err + mach_err + att_pen + therm_pen

    fitness = round(max(0.0, 100.0 - (total_penalty / 24.0) * 10.5 - fuel_used * 2.2), 3)
    return {"gen_id": gen_id, "fitness": fitness, "params": g, "code_path": code_path, "code_sha256": sha}


def ensure_seed_generation() -> dict:
    with db_conn() as c:
        row = c.execute(
            "SELECT gen_id, fitness, params_json, code_path FROM jet_mutations WHERE promoted=1 ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    if row:
        return {"gen_id": row[0], "fitness": row[1], "params": json.loads(row[2]), "code_path": row[3]}

    scored = _load_and_score_genome("GEN-000", dict(DEFAULT_GENOME), "turbulence", write_artifact=True)
    ts = int(time.time())
    sig = _hmac_sign(f"GEN-000|{scored['fitness']}|{scored['code_sha256']}|{ts}")
    with db_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO jet_mutations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("GEN-000", "ROOT", ts, scored["fitness"], 0.0, 1, "Baseline verified flight genome", json.dumps(scored["params"]), scored["code_path"], scored["code_sha256"], sig),
        )
    return scored


def step_telemetry(fault: str = "none") -> dict:
    """Advance Virtual Astra Jet physics + fuse live Termux silicon telemetry."""
    champ = ensure_seed_generation()
    g = champ["params"]
    hw = sample_silicon_side_channel()
    mem_mb = hw["mem_avail_kb"] // 1024
    temp_c = round(hw["max_temp_mc"] / 1000.0, 1) if 0 < hw["max_temp_mc"] < 105000 else 44.0

    dist = {"pitch_gust": 0.0, "roll_gust": 0.0}
    if fault == "turbulence":
        dist = {"pitch_gust": random.uniform(-4.5, 4.5), "roll_gust": random.uniform(-11.0, 11.0)}
    elif fault == "thermal_spike":
        temp_c = 71.5
        dist = {"pitch_gust": random.uniform(-2.0, 2.0), "roll_gust": random.uniform(-4.0, 4.0)}
    elif fault == "hypersonic_dash":
        g = dict(g)
        g["target_mach"] = 2.05

    # Execute active champion control law
    code_path = Path(champ["code_path"]) if champ.get("code_path") else None
    if code_path and code_path.exists():
        spec = importlib.util.spec_from_file_location("active_jet_ctrl", code_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cmd = mod.compute_control({**JET_STATE, "mem_mb": mem_mb, "temp_c": temp_c}, dist)
    else:
        cmd = {"pitch_cmd": 0.5, "roll_cmd": 0.0, "throttle": 0.72}

    JET_STATE["pitch"] = round(JET_STATE["pitch"] * 0.55 + cmd["pitch_cmd"] * 0.45, 2)
    JET_STATE["roll"] = round(JET_STATE["roll"] * 0.50 + cmd["roll_cmd"] * 0.50, 2)
    JET_STATE["alt_ft"] = round(max(12000.0, min(55000.0, JET_STATE["alt_ft"] + JET_STATE["pitch"] * 95.0)), 1)
    JET_STATE["mach"] = round(max(0.75, min(2.35, JET_STATE["mach"] + (cmd["throttle"] - 0.68) * 0.14)), 3)
    JET_STATE["heading"] = round((JET_STATE["heading"] + JET_STATE["roll"] * 0.15) % 360.0, 1)
    JET_STATE["g_load"] = round(1.0 + abs(JET_STATE["pitch"]) * 0.05 + abs(JET_STATE["roll"]) * 0.015, 2)
    JET_STATE["egt_c"] = round(540.0 + cmd["throttle"] * 285.0 + (temp_c - 40.0) * 1.4, 1)
    JET_STATE["fuel_pct"] = round(max(5.0, JET_STATE["fuel_pct"] - cmd["throttle"] * 0.08), 2)
    if JET_STATE["fuel_pct"] <= 10.0:
        JET_STATE["fuel_pct"] = 96.0  # Virtual aerial refuel

    rad = math.radians(JET_STATE["heading"])
    JET_STATE["lat"] = round(JET_STATE["lat"] + math.cos(rad) * JET_STATE["mach"] * 0.012, 4)
    JET_STATE["lon"] = round(JET_STATE["lon"] + math.sin(rad) * JET_STATE["mach"] * 0.014, 4)
    JET_STATE["active_gen"] = champ["gen_id"]
    JET_STATE["fitness"] = champ["fitness"]
    JET_STATE["last_fault"] = fault.upper()

    ts = int(time.time())
    with db_conn() as c:
        c.execute(
            "INSERT INTO jet_telemetry (ts,lat,lon,alt_ft,mach,heading,pitch,roll,g_load,egt_c,fuel_pct,fitness,gen_id,mem_mb,jitter_ns,fault) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ts, JET_STATE["lat"], JET_STATE["lon"], JET_STATE["alt_ft"], JET_STATE["mach"], JET_STATE["heading"], JET_STATE["pitch"], JET_STATE["roll"], JET_STATE["g_load"], JET_STATE["egt_c"], JET_STATE["fuel_pct"], champ["fitness"], champ["gen_id"], mem_mb, hw["jitter_ns"], fault.upper()),
        )

    _pub_ring(f"telem:{champ['gen_id']}:M{JET_STATE['mach']}:F{champ['fitness']}")
    return {
        "ts": ts,
        "jet": dict(JET_STATE),
        "control_cmd": cmd,
        "host_silicon": {"mem_avail_mb": mem_mb, "temp_c": temp_c, "jitter_ns": hw["jitter_ns"]},
        "active_genome": champ["params"],
    }


def _propose_mutant(base: dict, scale: float) -> dict:
    m = dict(base)
    m["kp_pitch"] = round(max(0.10, min(1.40, m["kp_pitch"] + random.uniform(-0.18, 0.18) * scale)), 4)
    m["kd_pitch"] = round(max(0.05, min(0.95, m["kd_pitch"] + random.uniform(-0.14, 0.14) * scale)), 4)
    m["kp_roll"] = round(max(0.15, min(1.50, m["kp_roll"] + random.uniform(-0.20, 0.20) * scale)), 4)
    m["kd_roll"] = round(max(0.05, min(0.95, m["kd_roll"] + random.uniform(-0.15, 0.15) * scale)), 4)
    m["thrust_trim"] = round(max(0.50, min(0.92, m["thrust_trim"] + random.uniform(-0.08, 0.08) * scale)), 4)
    m["thermal_derate"] = round(max(0.60, min(0.88, m["thermal_derate"] + random.uniform(-0.06, 0.06) * scale)), 4)
    return m


def supercompute_mutate(cycles: int = 3, fault: str = "turbulence") -> dict:
    """3-Worker Parallel Supercomputing Evolution with Syntax Verification & Automatic Rollback."""
    champ = ensure_seed_generation()
    base_fitness = _load_and_score_genome(champ["gen_id"], champ["params"], fault, write_artifact=False)["fitness"]
    cycles = max(1, min(int(cycles or 3), 6))

    with db_conn() as c:
        gen_count = c.execute("SELECT COUNT(*) FROM jet_mutations").fetchone()[0]

    candidates = []
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = []
        for i in range(cycles * 3):
            scale = 1.0 if i < cycles else 0.45
            mut = _propose_mutant(champ["params"], scale)
            cand_id = f"CAND-{i+1}"
            futs.append(ex.submit(_load_and_score_genome, cand_id, mut, fault, False))
        for f in concurrent.futures.as_completed(futs):
            candidates.append(f.result())

    best = max(candidates, key=lambda x: x["fitness"])
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    ts = int(time.time())
    next_gen_id = f"GEN-{gen_count:03d}"

    promoted = 0
    reason = f"ROLLBACK: Best mutant ({best['fitness']}) did not beat champion {champ['gen_id']} ({base_fitness})"
    saved = best

    if best["fitness"] > base_fitness:
        try:
            saved = _load_and_score_genome(next_gen_id, best["params"], fault, write_artifact=True)
            promoted = 1
            delta = round(saved["fitness"] - base_fitness, 3)
            reason = f"PROMOTED: +{delta} fitness gain under {fault} (verified py_compile + 24-step sim)"
            JET_STATE["active_gen"] = next_gen_id
            JET_STATE["fitness"] = saved["fitness"]
        except Exception as e:
            promoted = 0
            reason = f"ROLLBACK_SYNTAX_ERROR: {str(e)[:120]}"

    sig = _hmac_sign(f"{next_gen_id}|{saved['fitness']}|{saved['code_sha256']}|{promoted}|{ts}")
    with db_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO jet_mutations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (next_gen_id, champ["gen_id"], ts, saved["fitness"], base_fitness, promoted, reason, json.dumps(saved["params"]), saved.get("code_path", ""), saved["code_sha256"], sig),
        )

    _pub_ring(f"mutate:{next_gen_id}:p{promoted}:f{saved['fitness']}")
    out = {
        "ok": True,
        "supercomputer_workers": 3,
        "candidates_evaluated": len(candidates),
        "compute_ms": elapsed_ms,
        "fault_profile": fault,
        "parent_gen": champ["gen_id"],
        "parent_fitness": base_fitness,
        "new_gen": next_gen_id,
        "new_fitness": saved["fitness"],
        "promoted": bool(promoted),
        "reason": reason,
        "code_path": saved.get("code_path", ""),
        "hmac_sig": sig,
        "params": saved["params"],
    }
    return enhance_with_llm("aiml_dev", f"Summarize Astra Jet mutation {next_gen_id}: {reason}", out)


def rollback_generation(gen_id: str) -> dict:
    with db_conn() as c:
        row = c.execute("SELECT gen_id, fitness, params_json, code_path, code_sha256 FROM jet_mutations WHERE gen_id=?", (gen_id,)).fetchone()
        if not row:
            return {"ok": False, "error": f"generation '{gen_id}' not found"}
        ts = int(time.time())
        c.execute("UPDATE jet_mutations SET promoted=1, ts=? WHERE gen_id=?", (ts, gen_id))
    JET_STATE["active_gen"] = row[0]
    JET_STATE["fitness"] = row[1]
    _pub_ring(f"rollback:{gen_id}")
    return {"ok": True, "active_gen": row[0], "fitness": row[1], "params": json.loads(row[2]), "code_path": row[3]}


def get_lineage() -> dict:
    champ = ensure_seed_generation()
    with db_conn() as c:
        muts = [
            {
                "gen_id": r[0], "parent_gen": r[1], "ts": r[2], "fitness": r[3],
                "prev_fitness": r[4], "promoted": bool(r[5]), "reason": r[6],
                "code_path": r[8], "hmac_sig": r[10],
            }
            for r in c.execute("SELECT * FROM jet_mutations ORDER BY ts DESC LIMIT 20").fetchall()
        ]
        hist = [
            {"ts": r[0], "alt_ft": r[1], "mach": r[2], "pitch": r[3], "roll": r[4], "fitness": r[5], "gen_id": r[6]}
            for r in c.execute("SELECT ts, alt_ft, mach, pitch, roll, fitness, gen_id FROM jet_telemetry ORDER BY id DESC LIMIT 20").fetchall()
        ]
    return {"active": champ, "mutations": muts, "recent_telemetry": hist}


JET_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Virtual Astra Jet // AI Supercomputing Self-Mutating Telemetry</title>
<style>
body{font-family:monospace;background:#060a12;color:#e6edf3;margin:12px}
.card{background:#0f172a;border:1px solid #1e3a5f;border-radius:10px;padding:12px;margin-bottom:12px}
.nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.nav a{background:#1f6feb;color:#fff;padding:6px 9px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:bold}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:8px;margin-top:8px}
.metric{background:#090d16;border:1px solid #30363d;border-radius:8px;padding:8px}
.metric b{color:#38bdf8;font-size:15px}
button{background:#238636;color:#fff;border:none;padding:8px 11px;border-radius:6px;cursor:pointer;font-family:monospace;font-weight:bold;margin:3px 2px}
button.alt{background:#0ea5e9;color:#060a12}button.purp{background:#8957e5}button.warn{background:#d29922;color:#060a12}
select{background:#090d16;color:#e6edf3;border:1px solid #30363d;padding:7px;border-radius:6px;font-family:monospace}
pre{background:#090d16;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:240px;white-space:pre-wrap;word-break:break-all}
.ok{color:#3fb950}.bad{color:#f85149}
</style></head><body>
<h2 style="color:#38bdf8;margin:4px 0">VIRTUAL ASTRA JET // AI SUPERCOMPUTING SELF-MUTATING TELEMETRY</h2>
<div class="nav" style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px">
  <a href="/">Pilot</a>
  <a href="/agents" style="background:#8957e5">18-Agents</a>
  <a href="/trader" style="background:#d29922;color:#050912">Trader/OMS</a>
  <a href="/infra" style="background:#0ea5e9;color:#050912">Infra/SRE</a>
  <a href="/dealership" style="background:#238636">Dealership</a>
  <a href="/eagle-eyes" style="background:#0891b2">Eagle Eyes</a>
  <a href="/codes" style="background:#db2777">50 Codes</a>
  <a href="/artifacts" style="background:#4f46e5">Artifacts</a>
  <a href="/creative" style="background:#f97316;color:#050912">Creative Studio</a>
  <a href="/astra-jet" style="background:#38bdf8;color:#050912">Astra Jet AI</a>
  <a href="/jet-3d" style="background:#39ff14;color:#050912">3D Jet HUD</a>
</div>

<div class="card">
  <b>1. Glass-Cockpit HUD & Live Silicon-Fused Flight Telemetry</b><br>
  <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:8px">
    <canvas id="hud" width="260" height="170" style="background:#04070d;border:1px solid #38bdf8;border-radius:8px"></canvas>
    <div style="flex:1;min-width:210px">
      <div class="grid" id="metrics"></div>
      <div style="margin-top:10px">
        <select id="fault">
          <option value="none">Nominal Cruise</option>
          <option value="turbulence" selected>Severe Turbulence</option>
          <option value="thermal_spike">Silicon Thermal Spike</option>
          <option value="hypersonic_dash">Mach 2.05 Dash</option>
        </select>
        <button class="alt" onclick="stepJet()">Step Telemetry</button>
        <button class="purp" onclick="mutateSprint()">Run 3-Worker Self-Mutation</button>
      </div>
    </div>
  </div>
</div>

<div class="card">
  <b>2. Self-Mutating Control Genome Lineage (HMAC-Signed + Auto-Rollback)</b>
  <pre id="mutOut">Click "Run 3-Worker Self-Mutation" to synthesize, compile, benchmark, and promote a stronger flight control law.</pre>
  <div id="lineageTbl" style="font-size:12px;margin-top:8px"></div>
</div>

<script>
function drawHUD(j){
  const cv = document.getElementById('hud'), g = cv.getContext('2d');
  g.clearRect(0,0,260,170);
  g.save();
  g.translate(130, 85);
  g.rotate((-j.roll || 0) * Math.PI / 180);
  const py = (j.pitch || 0) * 4;
  g.fillStyle = '#0c2742'; g.fillRect(-180, -180 + py, 360, 180);
  g.fillStyle = '#1b140d'; g.fillRect(-180, py, 360, 180);
  g.strokeStyle = '#38bdf8'; g.lineWidth = 1.6;
  g.beginPath(); g.moveTo(-140, py); g.lineTo(140, py); g.stroke();
  g.restore();
  // Reticle & tapes
  g.strokeStyle = '#3fb950'; g.lineWidth = 2;
  g.beginPath(); g.moveTo(108,85); g.lineTo(124,85); g.moveTo(136,85); g.lineTo(152,85); g.stroke();
  g.fillStyle = '#38bdf8'; g.font = '11px monospace';
  g.fillText('M ' + j.mach, 8, 18);
  g.fillText('ALT ' + Math.round(j.alt_ft) + 'ft', 174, 18);
  g.fillText('HDG ' + j.heading + '°', 96, 162);
  g.fillText(j.active_gen + ' // FIT ' + j.fitness, 8, 162);
}

async function stepJet(){
  const f = encodeURIComponent(document.getElementById('fault').value);
  const r = await fetch('/api/jet/telemetry?fault=' + f);
  const d = await r.json();
  const j = d.jet, hw = d.host_silicon;
  drawHUD(j);
  document.getElementById('metrics').innerHTML =
    `<div class="metric">GENOME<br><b>${j.active_gen}</b></div>`+
    `<div class="metric">FITNESS<br><b>${j.fitness}</b></div>`+
    `<div class="metric">MACH / ALT<br><b>${j.mach} / ${Math.round(j.alt_ft)}</b></div>`+
    `<div class="metric">G-LOAD / EGT<br><b>${j.g_load}G / ${j.egt_c}°C</b></div>`+
    `<div class="metric">FUEL / POS<br><b>${j.fuel_pct}%</b></div>`+
    `<div class="metric">HOST SILICON<br><b>${hw.mem_avail_mb}MB / ${hw.temp_c}°C</b></div>`;
}

async function mutateSprint(){
  const f = document.getElementById('fault').value;
  document.getElementById('mutOut').textContent = 'Running 3-worker parallel supercomputing mutation & py_compile verification...';
  const r = await fetch('/api/jet/mutate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({cycles:3, fault:f})});
  const d = await r.json();
  document.getElementById('mutOut').textContent = JSON.stringify(d, null, 2);
  stepJet();
  loadLineage();
}

async function rollback(gid){
  const r = await fetch('/api/jet/rollback', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({gen_id:gid})});
  document.getElementById('mutOut').textContent = JSON.stringify(await r.json(), null, 2);
  stepJet();
  loadLineage();
}

async function loadLineage(){
  const r = await fetch('/api/jet/lineage');
  const d = await r.json();
  document.getElementById('lineageTbl').innerHTML = (d.mutations || []).map(m =>
    `<div style="border-bottom:1px solid #1e3a5f;padding:6px 0">
      <b>${m.gen_id}</b> (parent: ${m.parent_gen}) | Fitness: <b>${m.fitness}</b>
      <span class="${m.promoted?'ok':'bad'}">[${m.promoted?'PROMOTED':'ROLLED BACK'}]</span><br>
      <small>${m.reason} | HMAC: ${m.hmac_sig}</small>
      ${m.code_path ? ` <button class="warn" style="padding:3px 7px;font-size:10px" onclick="rollback('${m.gen_id}')">Activate</button>` : ''}
    </div>`
  ).join('');
}

stepJet(); loadLineage(); setInterval(stepJet, 5000);
</script></body></html>"""
