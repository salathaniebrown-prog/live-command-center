#!/usr/bin/env python3
"""
SalathanieAI — EV Car + Jet = Astra + Alstra = SalathanieAI Flying Car
Fuses EV ground-drive/battery/regen telemetry, jet/pod/pilot-stick flight controls,
live KGSO/NASA/PX4 telemetry, cabin/cockpit avatar state, and WAL flight ledger.
Strictly additive: never replaces existing modules or PM2 services.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path

import astra_flight_ledger as ledger
from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv, sample_silicon_side_channel

REPO = Path("/data/data/com.termux/files/home/live-command-center")
WAL_DB = REPO / "alstra_flight_ledger.db"
HOME = Path.home()

VALID_FC_MODES = ("EV-GROUND", "REGEN-BRAKE", "TRANSITION-HOVER", "JET-CRUISE", "SAFE-PROTECT")

_FC_STATE = {
    "mode": "EV-GROUND",
    "wheel_speed_kmh": 0.0,
    "wheel_torque_nm": 180.0,
    "regen_kw": 0.0,
    "pack_soc_pct": 92.0,
    "pack_temp_c": 29.5,
    "jet_thrust_pct": 18.0,
    "airborne": False,
    "avatar_screen_active": True,
    "avatars": ["SalathanieAI", "ASTRA-CORE-V10", "SIMLI-TRINITY-2"],
    "last_update_ts": 0,
}


def _db() -> sqlite3.Connection:
    WAL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WAL_DB), timeout=6.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flying_car_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INT NOT NULL,
            mode TEXT NOT NULL,
            wheel_speed_kmh REAL,
            wheel_torque_nm REAL,
            regen_kw REAL,
            pack_soc_pct REAL,
            pack_temp_c REAL,
            jet_thrust_pct REAL,
            airborne INT,
            ram_pct REAL,
            hazard_score REAL,
            state_json TEXT NOT NULL,
            hmac_sig TEXT NOT NULL
        );
    """)
    return conn


def _sign(msg: str) -> str:
    kp = HOME / ".salathanie_hmac.key"
    key = kp.read_bytes()[:32] if kp.exists() else b"salathanie-flying-car-key"
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()[:24].upper()


def _host_ram_pct() -> float:
    tot_kb = avail_kb = 0
    try:
        for ln in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ln.startswith("MemTotal:"):
                tot_kb = int(ln.split()[1])
            elif ln.startswith("MemAvailable:"):
                avail_kb = int(ln.split()[1])
    except OSError:
        pass
    return round(((tot_kb - avail_kb) / tot_kb) * 100.0, 2) if tot_kb else 80.0


def step_flying_car(cmd: dict | None = None) -> dict:
    """Update and persist EV Car + Jet Flying Car telemetry, safety interlocks, and cabin avatar state."""
    cmd = cmd or {}
    ts = int(time.time())
    ram_pct = _host_ram_pct()
    hazard = ledger.external_hazard_score()
    st = ledger.read_state_safe()
    pods = st.get("pods") if isinstance(st.get("pods"), list) and len(st["pods"]) == 4 else [True, True, True, True]

    req_mode = str(cmd.get("mode") or _FC_STATE["mode"]).strip().upper()
    if req_mode not in VALID_FC_MODES:
        req_mode = _FC_STATE["mode"]

    speed = float(cmd.get("wheel_speed_kmh", _FC_STATE["wheel_speed_kmh"]))
    torque = float(cmd.get("wheel_torque_nm", _FC_STATE["wheel_torque_nm"]))
    soc = float(cmd.get("pack_soc_pct", _FC_STATE["pack_soc_pct"]))
    pack_temp = float(cmd.get("pack_temp_c", _FC_STATE["pack_temp_c"]))
    thrust = float(cmd.get("jet_thrust_pct", _FC_STATE["jet_thrust_pct"]))

    # Real-build safety interlocks: low SOC, high pack temp, or high RAM forces safe/regen envelope
    interlocks = []
    if soc < 20.0 and req_mode in ("TRANSITION-HOVER", "JET-CRUISE"):
        req_mode = "EV-GROUND"
        interlocks.append("SOC_BELOW_20PCT_GROUND_LOCK")
    if pack_temp > 58.0 or ram_pct > 90.0:
        req_mode = "SAFE-PROTECT"
        interlocks.append("THERMAL_OR_RAM_PROTECT")

    if req_mode == "EV-GROUND":
        airborne = False
        thrust = min(thrust, 22.0)
        regen_kw = 0.0
        torque = max(120.0, min(680.0, torque))
    elif req_mode == "REGEN-BRAKE":
        airborne = False
        thrust = 0.0
        torque = 0.0
        regen_kw = round(max(15.0, min(140.0, speed * 1.4)), 2)
        speed = round(max(0.0, speed * 0.78), 2)
        soc = round(min(100.0, soc + 0.2), 2)
    elif req_mode == "TRANSITION-HOVER":
        airborne = True
        thrust = round(max(58.0, min(88.0, thrust if thrust >= 58.0 else 72.0)), 2)
        torque = round(torque * 0.25, 2)
        regen_kw = 0.0
    elif req_mode == "JET-CRUISE":
        airborne = True
        thrust = round(max(65.0, min(95.0, thrust if thrust >= 65.0 else 78.0)), 2)
        torque = 0.0
        regen_kw = 0.0
    else:  # SAFE-PROTECT
        airborne = False
        thrust = 0.0
        torque = 0.0
        regen_kw = 12.0

    _FC_STATE.update({
        "mode": req_mode,
        "wheel_speed_kmh": round(speed, 2),
        "wheel_torque_nm": round(torque, 2),
        "regen_kw": regen_kw,
        "pack_soc_pct": round(soc, 2),
        "pack_temp_c": round(pack_temp, 2),
        "jet_thrust_pct": round(thrust, 2),
        "airborne": airborne,
        "avatar_screen_active": bool(cmd.get("avatar_screen_active", True)),
        "last_update_ts": ts,
    })

    sig = _sign(f"fc|{ts}|{req_mode}|{thrust}|{_FC_STATE['wheel_speed_kmh']}|{ram_pct}")
    snapshot = {
        "ok": True,
        "ts": ts,
        "vehicle_name": "Astra + Alstra = SalathanieAI Flying Car",
        "architecture": "EV_CAR_PLUS_JET",
        "mode": _FC_STATE["mode"],
        "airborne": _FC_STATE["airborne"],
        "ev_bus": {
            "wheel_speed_kmh": _FC_STATE["wheel_speed_kmh"],
            "wheel_torque_nm": _FC_STATE["wheel_torque_nm"],
            "regen_kw": _FC_STATE["regen_kw"],
            "pack_soc_pct": _FC_STATE["pack_soc_pct"],
            "pack_temp_c": _FC_STATE["pack_temp_c"],
        },
        "jet_bus": {
            "jet_thrust_pct": _FC_STATE["jet_thrust_pct"],
            "pods_mask": "".join("1" if b else "0" for b in pods),
            "pods_active": sum(1 for b in pods if b),
            "active_gen": st.get("active_gen", "GEN-000"),
            "hazard_score": hazard,
        },
        "cabin_avatars": {
            "screen_active": _FC_STATE["avatar_screen_active"],
            "primary_model": "SalathanieAI",
            "avatars": [
                {"id": "salathanie-ai", "label": "SalathanieAI", "role": "Supercomputer & Flight/Drive Arbiter", "status": "ONLINE"},
                {"id": "astra-core-v10", "label": "ASTRA CORE v10", "role": "Cockpit Neural Avatar & Voice Core", "status": "ONLINE"},
                {"id": "simli-trinity-2", "label": "SIMLI TRINITY-2", "role": "Live Motion / Cabin Screen Feed", "status": "ONLINE"},
            ],
        },
        "build_roadmap": [
            {"stage": "01-DIGITAL-TWIN", "status": "ACTIVE", "detail": "WAL ledger + 3D jet/tunnel/GIS + cabin avatar telemetry live"},
            {"stage": "02-HV-EV-JET-BUS", "status": "IN_PROGRESS", "detail": "Dual HV battery bus + vectored thrust + ground/air interlocks"},
            {"stage": "03-TETHERED-HOVER-ROLL", "status": "PLANNED", "detail": "Low-speed EV taxi + tethered thrust & pod sensor validation"},
            {"stage": "04-FLIGHT-CLEARANCE", "status": "PLANNED", "detail": "FAA/FRIA & airworthiness compliance + emergency recovery"},
        ],
        "interlocks": interlocks,
        "host_ram_pct": ram_pct,
        "hmac_sig": sig,
    }

    with _db() as c:
        c.execute(
            """INSERT INTO flying_car_telemetry(
                ts,mode,wheel_speed_kmh,wheel_torque_nm,regen_kw,pack_soc_pct,pack_temp_c,
                jet_thrust_pct,airborne,ram_pct,hazard_score,state_json,hmac_sig
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts, _FC_STATE["mode"], _FC_STATE["wheel_speed_kmh"], _FC_STATE["wheel_torque_nm"],
                _FC_STATE["regen_kw"], _FC_STATE["pack_soc_pct"], _FC_STATE["pack_temp_c"],
                _FC_STATE["jet_thrust_pct"], 1 if _FC_STATE["airborne"] else 0,
                ram_pct, hazard, json.dumps(snapshot), sig,
            ),
        )
        c.commit()

    ledger.atomic_write_state({
        "flying_car_mode": _FC_STATE["mode"],
        "flying_car_airborne": _FC_STATE["airborne"],
        "flying_car_hmac": sig,
    }, preserve_overrides=True)

    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-flying-car", 8125, 200, deterministic_hv(f"fc:{_FC_STATE['mode']}:{sig}"))
    except Exception:
        pass

    return snapshot



def set_custom_livery(exterior_theme: str = "CYBER-CYAN-EMERALD", interior_theme: str = "COCKPIT-AVATAR-HUD", accent_color: str = "#22d3ee") -> dict:
    snap = step_flying_car({"avatar_screen_active": True})
    snap["customization"] = {
        "exterior_theme": exterior_theme,
        "interior_theme": interior_theme,
        "accent_color": accent_color,
    }
    return snap



def plan_mission_profile(waypoint_name: str = "KGSO-TRIAD-CORRIDOR", target_alt_m: float = 180.0, jet_thrust_pct: float = 72.0) -> dict:
    snap = step_flying_car({
        "mode": "JET-CRUISE" if target_alt_m > 10.0 else "EV-GROUND",
        "jet_thrust_pct": float(jet_thrust_pct),
    })
    env = compute_power_envelope(
        snap.get("mode", "JET-CRUISE"),
        float(snap.get("wheel_speed_kmh", 0.0)),
        float(snap.get("wheel_torque_nm", 0.0)),
        float(snap.get("regen_kw", 0.0)),
        float(jet_thrust_pct),
    )
    snap["mission_plan"] = {
        "waypoint": waypoint_name,
        "target_alt_m": round(float(target_alt_m), 1),
        "jet_thrust_pct": round(float(jet_thrust_pct), 1),
        "power_envelope": env,
    }
    return snap


def flying_car_status(limit: int = 10) -> dict:
    with _db() as c:
        total = c.execute("SELECT COUNT(*) FROM flying_car_telemetry").fetchone()[0]
        rows = c.execute(
            "SELECT ts,mode,wheel_speed_kmh,pack_soc_pct,jet_thrust_pct,airborne,hmac_sig FROM flying_car_telemetry ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    cur = step_flying_car() if total == 0 else None
    if cur is None:
        latest_row = c.execute("SELECT state_json FROM flying_car_telemetry ORDER BY id DESC LIMIT 1").fetchone()
        cur = json.loads(latest_row[0]) if latest_row else step_flying_car()
    history = [
        {"ts": r[0], "mode": r[1], "speed_kmh": r[2], "soc_pct": r[3], "thrust_pct": r[4], "airborne": bool(r[5]), "hmac_sig": r[6]}
        for r in rows
    ]
    return {"ok": True, "total_frames": total, "current": cur, "history": history}


FLYING_CAR_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Astra + Alstra = SalathanieAI Flying Car // Cabin Avatar &amp; EV+Jet Bus</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:monospace}
body{background:#040814;color:#e6f6ff;padding:10px;font-size:12px}
.top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;background:#0b162d;border:1px solid #1e3a5f;border-radius:8px;padding:8px 12px;margin-bottom:10px}
button{background:#0ea5e9;color:#030712;border:none;padding:6px 10px;border-radius:5px;font-weight:bold;cursor:pointer;font-size:11px;margin:2px}
button.grn{background:#22c55e}button.pur{background:#a855f7;color:#fff}button.amb{background:#f59e0b}
.grid{display:grid;grid-template-columns:1.1fr 1fr;gap:10px}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
.card{background:#0b162d;border:1px solid #1e3a5f;border-radius:8px;padding:10px;margin-bottom:10px}
.av-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px}
.av-box{background:#050c1a;border:1px solid #22d3ee55;border-radius:6px;padding:8px;text-align:center}
canvas{width:100%;height:170px;background:#020611;border:1px solid #173252;border-radius:6px;display:block;margin-top:6px}
pre{background:#030813;border:1px solid #173252;border-radius:6px;padding:8px;font-size:11px;overflow:auto;max-height:200px;white-space:pre-wrap}
a{color:#38bdf8;text-decoration:none;margin-right:8px}
</style></head><body>
<div class="top">
  <div><b>ASTRA + ALSTRA = SALATHANIE AI FLYING CAR</b> <span style="color:#39ff14">[EV DRIVE + JET BUS]</span></div>
  <div>
    <a href="/">Pilot</a><a href="/deck">Deck</a><a href="/tunnel-gis">Tunnel/GIS</a><a href="/memory">Memory</a>
  </div>
</div>

<div class="grid">
  <div class="card">
    <b>Cabin / Cockpit Avatar Screen Telemetry (Live Sync)</b>
    <canvas id="avCv" width="520" height="170"></canvas>
    <div class="av-grid" id="avCards"></div>
    <div style="margin-top:8px">
      <button class="grn" onclick="setMode('EV-GROUND')">EV-GROUND</button>
      <button class="amb" onclick="setMode('REGEN-BRAKE')">REGEN-BRAKE</button>
      <button class="pur" onclick="setMode('TRANSITION-HOVER')">TRANSITION-HOVER</button>
      <button onclick="setMode('JET-CRUISE')">JET-CRUISE</button>
    </div>
  </div>

  <div>
    <div class="card">
      <b>EV Powertrain &amp; Jet Propulsion Bus</b>
      <pre id="busOut" style="margin-top:6px">Loading EV + Jet telemetry...</pre>
    </div>
    <div class="card">
      <b>Future Real-Build Milestones &amp; Safety Interlocks</b>
      <pre id="roadOut" style="margin-top:6px">Loading build milestones...</pre>
    </div>
  </div>
</div>

<script>
let FC={mode:'EV-GROUND',ev_bus:{},jet_bus:{},cabin_avatars:{avatars:[]},build_roadmap:[],interlocks:[]};
let AT=0;
function drawAvatarScreen(){
  const cv=document.getElementById('avCv'); if(!cv) return;
  const cx=cv.getContext('2d'), w=cv.width, h=cv.height;
  cx.fillStyle='#020611'; cx.fillRect(0,0,w,h);
  const pulse=0.65+0.35*Math.sin(AT*3.2);
  const centers=[[95,88,'#39ff14','SalathanieAI'],[260,88,'#22d3ee','ASTRA v10'],[425,88,'#c084fc','SIMLI-2']];
  centers.forEach(([x,y,col,lbl],i)=>{
    cx.strokeStyle=col; cx.lineWidth=2;
    cx.beginPath(); cx.arc(x,y,34+pulse*4*(i===0?1.3:0.7),0,Math.PI*2); cx.stroke();
    cx.fillStyle=col+'33';
    cx.beginPath(); cx.arc(x,y,24,0,Math.PI*2); cx.fill();
    cx.fillStyle='#fff'; cx.font='bold 10px monospace'; cx.textAlign='center';
    cx.fillText(lbl,x,y+3);
    cx.fillStyle=col; cx.font='9px monospace';
    cx.fillText('ONLINE',x,y+52);
  });
  cx.textAlign='left'; cx.fillStyle='#7dd3fc'; cx.font='10px monospace';
  cx.fillText(`CABIN SCREEN LIVE // MODE: ${FC.mode||'EV-GROUND'} // AIRBORNE: ${FC.airborne?'YES':'NO'}`,12,16);
  AT+=0.035;
  requestAnimationFrame(drawAvatarScreen);
}
async function refreshFc(){
  try{
    const d=await(await fetch('/api/flying-car/status')).json();
    FC=d.current||FC;
    const avs=(FC.cabin_avatars&&FC.cabin_avatars.avatars)||[];
    document.getElementById('avCards').innerHTML=avs.map(a=>
      `<div class="av-box"><b style="color:#39ff14">${a.label}</b><br><small style="color:#cbd5e1">${a.role}</small><br><span style="color:#22d3ee">${a.status}</span></div>`
    ).join('');
    document.getElementById('busOut').textContent=JSON.stringify({
      mode:FC.mode, airborne:FC.airborne, ev_bus:FC.ev_bus, jet_bus:FC.jet_bus, host_ram_pct:FC.host_ram_pct, hmac_sig:FC.hmac_sig
    },null,2);
    document.getElementById('roadOut').textContent=JSON.stringify({
      interlocks:FC.interlocks, build_roadmap:FC.build_roadmap
    },null,2);
  }catch(e){}
}
async function setMode(mode){
  await fetch('/api/flying-car/step',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});
  refreshFc();
}
refreshFc(); drawAvatarScreen(); setInterval(refreshFc, 3000);
</script></body></html>"""
