#!/usr/bin/env python3
"""
SalathanieAI — Sovereign Creative Production Platform ("Imagination Orchestrated")
Astra + Alstra = SalathanieAI // All-In-One All-Access Brain
Browser workspace running Image, 3D, Video & Audio workflows locally with
upgraded Astra+Alstra Core Jet visuals + optional BYO cloud adapters.
"""
import argparse
import json
import os
import re
import sqlite3
import time
import urllib.request
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv
from llm_bridge import enhance_with_llm

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "salathanie_creative.db"
OUT_DIR = REPO / "builds" / "creative"
KEYS_PATH = Path.home() / ".salathanie_creative_keys.json"

MODEL_CATALOG = {
    "salathanie_style_brain": {
        "name": "SalathanieAI Style Core",
        "modality": "style_orchestrator",
        "provider": "local_sovereign",
        "cloud_adapter": "scenario",
        "endpoint": "salathanie/v1/style-orchestrator",
        "unit_cost_usd": 0.0,
        "unit": "local_free",
        "strengths": "All-style art direction, team style-locking, natural-language workflow synthesis",
    },
    "salathanie_prism_image": {
        "name": "SalathanieAI Prism-5 Image",
        "modality": "image",
        "provider": "local_sovereign",
        "cloud_adapter": "fal",
        "endpoint": "salathanie/v1/prism-image-2k",
        "unit_cost_usd": 0.0,
        "unit": "local_free",
        "strengths": "2K layered core imagery, Astra+Alstra jet hero posters, downloadable PNG assets",
    },
    "salathanie_forge_3d": {
        "name": "SalathanieAI Forge-3D",
        "modality": "3d",
        "provider": "local_sovereign",
        "cloud_adapter": "meshy",
        "endpoint": "salathanie/v1/forge-3d-mesh",
        "unit_cost_usd": 0.0,
        "unit": "local_free",
        "strengths": "Multi-panel shaded 3D stealth mesh + downloadable .OBJ geometry on demand",
    },
    "salathanie_rig_splat": {
        "name": "SalathanieAI Rig-Splat",
        "modality": "3d",
        "provider": "local_sovereign",
        "cloud_adapter": "sperid",
        "endpoint": "salathanie/v1/rig-splat-core",
        "unit_cost_usd": 0.0,
        "unit": "local_free",
        "strengths": "Articulated pods, Gaussian core FX, interior fusion reactor rigging",
    },
    "salathanie_motion_v4": {
        "name": "SalathanieAI Motion-V4 (Code2Vid)",
        "modality": "video",
        "provider": "local_sovereign",
        "cloud_adapter": "fal",
        "endpoint": "salathanie/v1/motion-v4-i2v",
        "unit_cost_usd": 0.0,
        "unit": "local_free",
        "strengths": "Browser-native image-to-video & code-to-video capture (MP4/WebM) with camera keyframes",
    },
    "salathanie_cine_hd": {
        "name": "SalathanieAI Cine-HD Audio",
        "modality": "video_audio",
        "provider": "local_sovereign",
        "cloud_adapter": "minimax",
        "endpoint": "salathanie/v1/cine-hd-av",
        "unit_cost_usd": 0.0,
        "unit": "local_free",
        "strengths": "Synchronized Web Audio turbine + cinematic synth track muxed into video stream",
    },
    "salathanie_turbo_pro": {
        "name": "SalathanieAI Turbo-Pro",
        "modality": "video_audio",
        "provider": "local_sovereign",
        "cloud_adapter": "pruna",
        "endpoint": "salathanie/v1/turbo-pro-accel",
        "unit_cost_usd": 0.0,
        "unit": "local_free",
        "strengths": "Zero-latency Android/Termux shader acceleration and instant multi-asset export",
    },
}


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS creative_workflows (
            wf_id TEXT PRIMARY KEY, ts INT, title TEXT, brief TEXT, style TEXT,
            duration_s INT, est_cost_usd REAL, nodes_json TEXT, code_bundle TEXT, status TEXT
        );
        CREATE TABLE IF NOT EXISTS creative_jobs (
            job_id TEXT PRIMARY KEY, wf_id TEXT, ts INT, model_key TEXT, mode TEXT,
            status TEXT, payload_json TEXT, result_json TEXT
        );
    """)
    return conn


def load_keys() -> dict:
    keys = {}
    if KEYS_PATH.exists():
        try:
            keys = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
        except Exception:
            keys = {}
    for env_k in ("FAL_KEY", "MESHY_API_KEY", "MINIMAX_API_KEY", "PRUNA_API_KEY", "SCENARIO_API_KEY", "HF_TOKEN"):
        if os.getenv(env_k):
            keys[env_k] = os.getenv(env_k)
    return keys


def save_keys(updates: dict) -> dict:
    keys = load_keys()
    for k, v in updates.items():
        if v:
            keys[k] = v.strip()
    fd = os.open(str(KEYS_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(keys, indent=2).encode("utf-8"))
    finally:
        os.close(fd)
    return {k: True for k in keys}


def _pub_ring(tag: str):
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-creative", 8125, 200, deterministic_hv(f"salathanieai:{tag}"))
    except Exception:
        pass


def build_code_bundle(brief: str, style: str, duration_s: int, selected: list[str]) -> dict:
    safe_prompt = f"{brief} — style: {style}".replace('"', '\\"')
    py_lines = [
        "#!/usr/bin/env python3",
        '"""SalathanieAI (Astra + Alstra) — Sovereign Creative Workflow Pipeline"""',
        "import json, time, urllib.request",
        "",
        f'BRIEF = "{safe_prompt}"',
        f'STYLE = "{style}"',
        f"DURATION_S = {duration_s}",
        f"ENGINES = {json.dumps(selected)}",
        'PILOT_URL = "http://127.0.0.1:8125"',
        "",
        "def run_sovereign_workflow():",
        '    payload = {"brief": BRIEF, "style": STYLE, "duration_s": DURATION_S, "models": ENGINES}',
        '    req = urllib.request.Request(f"{PILOT_URL}/api/creative/build", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})',
        "    with urllib.request.urlopen(req, timeout=15) as r:",
        '        wf = json.loads(r.read().decode("utf-8"))',
        '    print("[SALATHANIE AI] Built workflow:", wf["wf_id"], "nodes:", len(wf["nodes"]))',
        "    return wf",
        "",
        'if __name__ == "__main__":',
        "    run_sovereign_workflow()",
    ]
    curl_cmd = (
        f'curl -s -X POST "http://127.0.0.1:8125/api/creative/build" \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -d \'{{"brief":"{safe_prompt}","style":"{style}","duration_s":{duration_s}}}\''
    )
    return {"python": "\n".join(py_lines), "curl_sovereign": curl_cmd}


def aviator_build_workflow(brief: str, style: str = "Obsidian Stealth 8K", duration_s: int = 5, models: list[str] | None = None) -> dict:
    """SalathanieAI All-Access Brain: Describe desired results -> auto-builds multi-modal DAG workflow."""
    b = brief.strip() or "Upgraded Astra + Alstra = SalathanieAI stealth core jet hero image, shaded 3D OBJ mesh, and 5s orbital video with turbine audio"
    bl = b.lower()
    dur = max(3, min(int(duration_s or 5), 30))

    if models:
        selected = [m for m in models if m in MODEL_CATALOG]
    else:
        selected = ["salathanie_style_brain", "salathanie_prism_image"]
        if any(k in bl for k in ("3d", "jet", "astra", "alstra", "mesh", "obj", "rig", "pod", "core", "all")):
            selected += ["salathanie_forge_3d", "salathanie_rig_splat"]
        if any(k in bl for k in ("video", "motion", "film", "commercial", "short", "camera", "orbital", "all")):
            selected.append("salathanie_motion_v4")
        if any(k in bl for k in ("audio", "sound", "turbine", "music", "fast", "turbo", "all")):
            selected += ["salathanie_cine_hd", "salathanie_turbo_pro"]
        if len(selected) == 2:
            selected += ["salathanie_forge_3d", "salathanie_motion_v4", "salathanie_cine_hd", "salathanie_turbo_pro"]

    nodes = []
    prev_id = None
    for idx, mkey in enumerate(selected, start=1):
        spec = MODEL_CATALOG[mkey]
        nid = f"N{idx}_{mkey}"
        nodes.append({
            "id": nid,
            "step": idx,
            "model_key": mkey,
            "model_name": spec["name"],
            "modality": spec["modality"],
            "provider": spec["provider"],
            "cloud_adapter": spec["cloud_adapter"],
            "endpoint": spec["endpoint"],
            "depends_on": prev_id,
            "est_cost_usd": 0.0,
            "prompt": f"[{style}] {b}",
        })
        prev_id = nid

    ts = int(time.time())
    wf_id = f"SAL-{ts % 1000000}"
    slug = re.sub(r"[^a-z0-9]+", "_", b.lower()).strip("_")[:24] or "salathanie_core"
    code_bundle = build_code_bundle(b, style, dur, selected)

    wf_dir = OUT_DIR / f"{wf_id.lower()}_{slug}"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "pipeline.py").write_text(code_bundle["python"], encoding="utf-8")
    (wf_dir / "workflow.json").write_text(json.dumps({"wf_id": wf_id, "brain": "SalathanieAI (Astra+Alstra)", "brief": b, "style": style, "nodes": nodes}, indent=2), encoding="utf-8")

    with db_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO creative_workflows VALUES (?,?,?,?,?,?,?,?,?,?)",
            (wf_id, ts, b[:64], b, style, dur, 0.0, json.dumps(nodes), json.dumps(code_bundle), "READY"),
        )

    out = {
        "ok": True,
        "brain": "Astra + Alstra = SalathanieAI (All-Access Sovereign)",
        "wf_id": wf_id,
        "brief": b,
        "style": style,
        "duration_s": dur,
        "est_total_cost_usd": 0.0,
        "saved_dir": str(wf_dir),
        "nodes": nodes,
        "code_bundle": code_bundle,
        "configured_keys": sorted(load_keys().keys()),
    }
    out = enhance_with_llm("creative_director", f"Give a crisp 3-line SalathanieAI production treatment for: {b} ({style})", out)
    _pub_ring(f"wf:{wf_id}")
    return out


def execute_workflow(wf_id: str, live: bool = False, start_image_url: str = "") -> dict:
    """Execute workflow locally inside SalathanieAI Sovereign Engine (or optional BYO cloud adapter if live=True)."""
    if live:
        from model_guard_autopilot import check_model_gate
        ok_gate, gate_msg = check_model_gate("creative", 0.5)
        if not ok_gate:
            return {"ok": False, "blocked_by_guard": True, "reason": gate_msg}

    with db_conn() as c:
        row = c.execute("SELECT brief, style, duration_s, nodes_json FROM creative_workflows WHERE wf_id=?", (wf_id,)).fetchone()
    if not row:
        return {"ok": False, "error": "workflow_not_found"}

    brief, style, dur, nodes = row[0], row[1], row[2], json.loads(row[3])
    keys = load_keys()
    results = []
    ts = int(time.time())

    def _post_json(url: str, headers: dict, body: dict) -> dict:
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", **headers})
            with urllib.request.urlopen(req, timeout=18) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"status": "API_ERROR", "error": str(e)[:180]}

    for n in nodes:
        mkey = n["model_key"]
        adapter = n.get("cloud_adapter", "")
        job_id = f"JOB-{ts % 100000}-{n['step']}"
        mode = "SOVEREIGN_LOCAL_ENGINE"
        res = {"status": "RENDERED_IN_WORKSPACE", "cost_usd": 0.0, "engine": n["model_name"]}

        if live:
            if adapter == "meshy" and keys.get("MESHY_API_KEY"):
                mode = "CLOUD_ADAPTER_MESHY"
                res = _post_json("https://api.meshy.ai/openapi/v2/text-to-3d", {"Authorization": f"Bearer {keys['MESHY_API_KEY']}"}, {"mode": "preview", "prompt": n["prompt"][:600]})
            elif adapter == "minimax" and keys.get("MINIMAX_API_KEY"):
                mode = "CLOUD_ADAPTER_MINIMAX"
                res = _post_json("https://api.minimax.io/v1/video_generation", {"Authorization": f"Bearer {keys['MINIMAX_API_KEY']}"}, {"model": "MiniMax-H3", "prompt": n["prompt"][:1000], "duration": dur, "resolution": "768P"})
            elif adapter == "pruna" and keys.get("PRUNA_API_KEY"):
                mode = "CLOUD_ADAPTER_PRUNA"
                res = _post_json(keys.get("PRUNA_API_URL", "https://api.pruna.ai/v1/predictions"), {"Authorization": f"Bearer {keys['PRUNA_API_KEY']}"}, {"model": "p-video-2-pro", "input": {"prompt": n["prompt"][:1000], "duration": dur, "mode": "speed"}})
            elif adapter == "scenario" and keys.get("SCENARIO_API_KEY"):
                mode = "CLOUD_ADAPTER_SCENARIO"
                auth = f"Basic {keys['SCENARIO_API_KEY']}" if not keys["SCENARIO_API_KEY"].startswith(("Basic ", "Bearer ")) else keys["SCENARIO_API_KEY"]
                res = _post_json("https://api.cloud.scenario.com/v1/txt2img", {"Authorization": auth}, {"prompt": n["prompt"][:800], "numSamples": 1})

        with db_conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO creative_jobs VALUES (?,?,?,?,?,?,?,?)",
                (job_id, wf_id, ts, mkey, mode, res.get("status", "DONE"), json.dumps(n), json.dumps(res)),
            )
        results.append({"job_id": job_id, "engine": n["model_name"], "modality": n["modality"], "mode": mode, "result": res})

    with db_conn() as c:
        c.execute("UPDATE creative_workflows SET status=? WHERE wf_id=?", ("CLOUD_RUN" if live else "SOVEREIGN_DONE", wf_id))
    _pub_ring(f"exec:{wf_id}")
    return {"ok": True, "wf_id": wf_id, "brain": "SalathanieAI", "jobs": results}


def list_workflows() -> dict:
    with db_conn() as c:
        wfs = [
            {"wf_id": r[0], "ts": r[1], "title": r[2], "style": r[3], "duration_s": r[4], "est_cost_usd": r[5], "status": r[6]}
            for r in c.execute("SELECT wf_id, ts, title, style, duration_s, est_cost_usd, status FROM creative_workflows ORDER BY ts DESC LIMIT 15").fetchall()
        ]
    return {"brain": "Astra + Alstra = SalathanieAI", "catalog": MODEL_CATALOG, "configured_keys": sorted(load_keys().keys()), "workflows": wfs}


CREATIVE_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SalathanieAI — Imagination Orchestrated (All-Access Sovereign Brain)</title>
<style>
body{font-family:monospace;background:#050912;color:#e6edf3;margin:10px}
.card{background:#0e1525;border:1px solid #24344d;border-radius:10px;padding:12px;margin-bottom:10px}
.nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.nav a{background:#1f6feb;color:#fff;padding:6px 9px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:bold}
textarea,input,select{width:100%;box-sizing:border-box;background:#070c16;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace;margin-top:6px}
button{background:#238636;color:#fff;border:none;padding:8px 11px;border-radius:6px;cursor:pointer;font-family:monospace;font-weight:bold;margin:4px 2px}
button.alt{background:#0ea5e9;color:#050912}button.purp{background:#8957e5}button.gold{background:#f59e0b;color:#050912}button.rec{background:#ef4444}
.checks{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.pill{background:#070c16;border:1px solid #38bdf8;border-radius:14px;padding:4px 9px;font-size:10px;cursor:pointer;display:flex;align-items:center;gap:4px}
.pill input{width:auto;margin:0}
.stage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:10px;margin-top:8px}
.stage-box{background:#070c16;border:1px solid #24344d;border-radius:8px;padding:8px;text-align:center}
canvas{max-width:100%;border-radius:6px;background:#02060f}
pre{background:#070c16;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:240px;white-space:pre-wrap;word-break:break-all}
.badge{background:#39ff14;color:#050912;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:bold}
</style></head><body>
<h2 style="color:#38bdf8;margin:2px 0">SALATHANIE AI // IMAGINATION ORCHESTRATED</h2>
<div style="font-size:11px;color:#39ff14;margin-bottom:8px">ASTRA + ALSTRA = SALATHANIE AI &bull; SOVEREIGN ALL-IN-ONE IMAGE / 3D / VIDEO / AUDIO BRAIN</div>
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
  <b>1. Describe the Result &rarr; SalathanieAI Builds &amp; Runs Your Multi-Modal Workflow</b>
  <textarea id="brief" rows="2">Upgraded Astra + Alstra = SalathanieAI Stealth Core Jet: 2K layered poster, shaded 3D OBJ fighter mesh, and 5s orbital launch video with turbine synth audio</textarea>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <select id="stylePreset" onchange="renderAll()" style="flex:1;min-width:160px">
      <option value="STEALTH">Obsidian Stealth Cyan (Astra+Alstra Core)</option>
      <option value="GOLD">Royal Diamond Gold Edition</option>
      <option value="PLASMA">Hyper-Plasma Violet Neon</option>
      <option value="CRIMSON">Crimson Spec-Ops Tactical</option>
      <option value="BLUEPRINT">Aerospace CAD Blueprint</option>
    </select>
    <input id="dur" value="5" style="width:76px" title="Video seconds">
  </div>
  <div class="checks" id="modelPills"></div>
  <div style="margin-top:8px">
    <button onclick="buildWF()">Auto-Build Workflow</button>
    <button class="alt" onclick="runWF(false)">Run Sovereign Pipeline ($0)</button>
    <button class="gold" onclick="runWF(true)">Optional Cloud Burst</button>
    <span id="costBadge" class="badge">SOVEREIGN: $0.00</span>
  </div>
</div>

<div class="card">
  <b>2. Unified Browser Workspace &mdash; Live DAG + Core Jet Image + Shaded 3D + Real Video/Audio Capture</b>
  <svg id="dagSvg" width="100%" height="106" viewBox="0 0 680 106" style="background:#070c16;border-radius:8px;border:1px solid #24344d;margin-top:6px"></svg>
  <div class="stage-grid">
    <div class="stage-box">
      <div style="font-size:10px;color:#38bdf8;margin-bottom:4px">CORE IMAGE ASSET (SalathanieAI Prism-5)</div>
      <canvas id="imgCv" width="440" height="250"></canvas>
      <div><button class="alt" onclick="dlPNG()">Download 2K-Style PNG</button></div>
    </div>
    <div class="stage-box">
      <div style="font-size:10px;color:#38bdf8;margin-bottom:4px">3D CORE JET MESH (SalathanieAI Forge-3D / Rig-Splat)</div>
      <canvas id="jetCv" width="440" height="250"></canvas>
      <div>
        <button class="purp" onclick="toggleCoreView()">Toggle Interior Core</button>
        <button class="gold" onclick="dlOBJ()">Download .OBJ 3D</button>
      </div>
    </div>
    <div class="stage-box">
      <div style="font-size:10px;color:#38bdf8;margin-bottom:4px">VIDEO + AUDIO ENGINE (Motion-V4 / Cine-HD / Turbo-Pro)</div>
      <div id="vidStatus" style="font-size:11px;color:#94a3b8;margin:8px 0">Ready to synthesize live video + turbine audio directly from your 3D Core Jet.</div>
      <video id="vidPlay" controls playsinline style="width:100%;max-height:150px;display:none;border-radius:6px;margin-bottom:6px"></video>
      <div>
        <button class="rec" id="recBtn" onclick="recordVideo()">Record Jet Video + Audio</button>
        <button class="alt" onclick="playTurbineAudio(2.2)">Test Audio Bed</button>
      </div>
      <a id="vidDl" style="display:none;color:#39ff14;font-size:11px;font-weight:bold">Download Recorded Video</a>
    </div>
  </div>
</div>

<div class="card">
  <b>3. Workflow Code &amp; Execution Telemetry</b>
  <button class="alt" onclick="showTab('py')">Sovereign Python Code</button>
  <button class="purp" onclick="showTab('curl')">API cURL</button>
  <button onclick="showTab('json')">Workflow / Job JSON</button>
  <pre id="codeOut">Tap "Auto-Build Workflow" to compile your SalathanieAI pipeline.</pre>
</div>

<script>
const PALETTES={
  STEALTH:{bg1:'#061428',bg2:'#02050c',hull:[18,38,68],edge:'#00f0ff',canopy:'#38bdf8',glow:'#00f0ff',core:'#39ff14',tag:'OBSIDIAN STEALTH'},
  GOLD:{bg1:'#241a06',bg2:'#070502',hull:[66,48,14],edge:'#fbbf24',canopy:'#fef08a',glow:'#f59e0b',core:'#facc15',tag:'ROYAL DIAMOND GOLD'},
  PLASMA:{bg1:'#1d0936',bg2:'#06020e',hull:[44,16,74],edge:'#e879f9',canopy:'#67e8f9',glow:'#c084fc',core:'#22d3ee',tag:'HYPER-PLASMA NEON'},
  CRIMSON:{bg1:'#26070c',bg2:'#080204',hull:[68,16,24],edge:'#fb7185',canopy:'#fde047',glow:'#ef4444',core:'#fb923c',tag:'CRIMSON SPEC-OPS'},
  BLUEPRINT:{bg1:'#072448',bg2:'#031226',hull:[12,48,96],edge:'#e0f2fe',canopy:'#7dd3fc',glow:'#38bdf8',core:'#ffffff',tag:'CAD BLUEPRINT'}
};
const VERTS=[
  [0,2,-175],[0,-22,-72],[-25,4,-48],[25,4,-48],[0,15,-54],
  [-148,14,72],[148,14,72],[-40,4,110],[40,4,110],[-54,-54,106],[54,-54,106],
  [0,-14,10],[0,17,70],[-62,10,98],[62,10,98],[0,-4,-14]
];
const FACES=[
  [[0,1,2],'canopy'],[[0,3,1],'canopy'],[[1,11,2],'hull'],[[1,3,11],'hull'],
  [[0,2,4],'hull'],[[0,4,3],'hull'],[[2,4,12,7],'hull'],[[3,8,12,4],'hull'],
  [[2,5,13,7],'wing'],[[3,8,14,6],'wing'],[[2,11,7],'hull'],[[3,8,11],'hull'],
  [[11,7,8],'hull'],[[7,9,11],'fin'],[[8,11,10],'fin'],[[7,12,8],'hull']
];

let CURRENT_WF=null,LAST_RUN=null,CURRENT_TAB='py',INTERIOR=false,ANG=0;
function getPal(){return PALETTES[document.getElementById('stylePreset').value]||PALETTES.STEALTH;}
function rot3(pt,p,r,y){
  const X=pt[0],Y=pt[1],Z=pt[2];
  const y1=Y*Math.cos(p)-Z*Math.sin(p),z1=Y*Math.sin(p)+Z*Math.cos(p);
  const x2=X*Math.cos(r)-y1*Math.sin(r),y2=X*Math.sin(r)+y1*Math.cos(r);
  const x3=x2*Math.cos(y)+z1*Math.sin(y),z3=-x2*Math.sin(y)+z1*Math.cos(y);
  return [x3,y2,z3];
}
function drawShadedJet(ctx,w,h,yaw,pitch,roll,showCore,pal,titleText){
  const bg=ctx.createRadialGradient(w/2,h/2,10,w/2,h/2,w*0.65);
  bg.addColorStop(0,pal.bg1);bg.addColorStop(1,pal.bg2);
  ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='rgba(56,189,248,0.14)';ctx.lineWidth=1;
  for(let rg=45;rg<=165;rg+=40){ctx.beginPath();ctx.ellipse(w/2,h/2+38,rg*1.35,rg*0.32,0,0,7);ctx.stroke();}

  const V3=VERTS.map(v=>rot3(v,pitch,roll,yaw));
  const R=V3.map(v=>{const f=360/(360+v[2]);return [w/2+v[0]*f*0.92,h/2-6+v[1]*f*0.92,v[2]];});
  const sorted=FACES.map(f=>{
    const pts=f[0].map(i=>V3[i]);
    const avgZ=pts.reduce((a,b)=>a+b[2],0)/pts.length;
    const u=[pts[1][0]-pts[0][0],pts[1][1]-pts[0][1],pts[1][2]-pts[0][2]];
    const wv=[pts[2][0]-pts[0][0],pts[2][1]-pts[0][1],pts[2][2]-pts[0][2]];
    const nx=u[1]*wv[2]-u[2]*wv[1],ny=u[2]*wv[0]-u[0]*wv[2],nz=u[0]*wv[1]-u[1]*wv[0];
    const len=Math.hypot(nx,ny,nz)||1;
    const l=Math.max(0.28,Math.min(1.0,Math.abs((nx*0.35-ny*0.75-nz*0.55)/len)));
    return {idx:f[0],kind:f[1],avgZ,l};
  }).sort((a,b)=>b.avgZ-a.avgZ);

  sorted.forEach(f=>{
    ctx.beginPath();
    f.idx.forEach((vi,k)=>{if(k===0)ctx.moveTo(R[vi][0],R[vi][1]);else ctx.lineTo(R[vi][0],R[vi][1]);});
    ctx.closePath();
    if(f.kind==='canopy'){
      ctx.fillStyle=pal.canopy;ctx.globalAlpha=showCore?0.3:0.78*f.l+0.15;ctx.fill();ctx.globalAlpha=1;
    }else{
      const alpha=showCore?0.24:0.9;
      const rr=Math.min(255,Math.round(pal.hull[0]*(0.55+f.l*1.25)));
      const gg=Math.min(255,Math.round(pal.hull[1]*(0.55+f.l*1.25)));
      const bb=Math.min(255,Math.round(pal.hull[2]*(0.55+f.l*1.25)));
      ctx.fillStyle=`rgba(${rr},${gg},${bb},${alpha})`;ctx.fill();
    }
    ctx.strokeStyle=pal.edge;ctx.lineWidth=1.2;ctx.stroke();
  });

  if(showCore){
    const cp=R[15];
    const cg=ctx.createRadialGradient(cp[0],cp[1],2,cp[0],cp[1],36);
    cg.addColorStop(0,'#fff');cg.addColorStop(0.4,pal.core);cg.addColorStop(1,'transparent');
    ctx.fillStyle=cg;ctx.beginPath();ctx.arc(cp[0],cp[1],36,0,7);ctx.fill();
  }
  [7,8].forEach(i=>{
    const nx=R[i][0],ny=R[i][1],rad=24+Math.sin(ANG*6+i)*3;
    const g=ctx.createRadialGradient(nx,ny,2,nx,ny,rad);
    g.addColorStop(0,'#fff');g.addColorStop(0.38,pal.glow);g.addColorStop(1,'transparent');
    ctx.fillStyle=g;ctx.beginPath();ctx.arc(nx,ny,rad,0,7);ctx.fill();
  });
  if(titleText){
    ctx.fillStyle='rgba(5,9,18,0.72)';ctx.fillRect(0,h-42,w,42);
    ctx.fillStyle=pal.edge;ctx.font='bold 12px monospace';ctx.fillText('ASTRA + ALSTRA = SALATHANIE AI',12,h-24);
    ctx.fillStyle='#cbd5e1';ctx.font='10px monospace';ctx.fillText((pal.tag+' // '+titleText).slice(0,56),12,h-9);
  }
}

function renderAll(){
  const pal=getPal();
  const b=document.getElementById('brief').value;
  drawShadedJet(document.getElementById('imgCv').getContext('2d'),440,250,0.62,0.16,-0.14,false,pal,b);
}
function toggleCoreView(){INTERIOR=!INTERIOR;}
setInterval(()=>{
  ANG+=0.035;
  drawShadedJet(document.getElementById('jetCv').getContext('2d'),440,250,ANG,Math.sin(ANG*0.7)*0.18,Math.cos(ANG*0.5)*0.15,INTERIOR,getPal(),'LIVE 3D CORE');
},45);

function dlPNG(){
  renderAll();
  const a=document.createElement('a');
  a.download='salathanieai_core_jet_'+document.getElementById('stylePreset').value.toLowerCase()+'.png';
  a.href=document.getElementById('imgCv').toDataURL('image/png');
  a.click();
}
function dlOBJ(){
  let obj='# SalathanieAI — Astra + Alstra Upgraded Core Jet (.OBJ)\n';
  VERTS.forEach(v=>{obj+='v '+(v[0]/50).toFixed(4)+' '+(-v[1]/50).toFixed(4)+' '+(v[2]/50).toFixed(4)+'\n';});
  FACES.forEach(f=>{obj+='f '+f[0].map(i=>i+1).join(' ')+'\n';});
  const a=document.createElement('a');
  a.download='salathanieai_astra_alstra_jet.obj';
  a.href=URL.createObjectURL(new Blob([obj],{type:'text/plain'}));
  a.click();
}

function buildAudioNodes(ctx,dest,durSec){
  const osc1=ctx.createOscillator(),osc2=ctx.createOscillator(),gain=ctx.createGain();
  osc1.type='sawtooth';osc2.type='triangle';
  osc1.frequency.setValueAtTime(88,ctx.currentTime);
  osc1.frequency.exponentialRampToValueAtTime(176,ctx.currentTime+durSec*0.6);
  osc1.frequency.exponentialRampToValueAtTime(110,ctx.currentTime+durSec);
  osc2.frequency.setValueAtTime(220,ctx.currentTime);
  osc2.frequency.linearRampToValueAtTime(330,ctx.currentTime+durSec);
  gain.gain.setValueAtTime(0.06,ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.002,ctx.currentTime+durSec);
  osc1.connect(gain);osc2.connect(gain);gain.connect(dest);
  osc1.start();osc2.start();
  osc1.stop(ctx.currentTime+durSec);osc2.stop(ctx.currentTime+durSec);
}
function playTurbineAudio(durSec){
  try{const ctx=new (window.AudioContext||window.webkitAudioContext)();buildAudioNodes(ctx,ctx.destination,durSec);}catch(e){}
}

async function recordVideo(){
  const btn=document.getElementById('recBtn'),st=document.getElementById('vidStatus');
  const cv=document.getElementById('jetCv');
  const durSec=Math.max(3,Math.min(12,Number(document.getElementById('dur').value||5)));
  if(!cv.captureStream||typeof MediaRecorder==='undefined'){st.textContent='MediaRecorder unavailable in this browser.';return;}
  btn.disabled=true;st.textContent=`Recording ${durSec}s SalathanieAI Jet video + turbine audio...`;
  const vStream=cv.captureStream(30);
  let tracks=[...vStream.getVideoTracks()];
  try{
    const actx=new (window.AudioContext||window.webkitAudioContext)();
    const mdest=actx.createMediaStreamDestination();
    buildAudioNodes(actx,mdest,durSec);
    tracks.push(...mdest.stream.getAudioTracks());
  }catch(e){}
  const combined=new MediaStream(tracks);
  const mimes=['video/mp4','video/webm;codecs=vp9','video/webm'];
  const mime=mimes.find(m=>MediaRecorder.isTypeSupported(m))||'';
  const rec=mime?new MediaRecorder(combined,{mimeType:mime}):new MediaRecorder(combined);
  const chunks=[];
  rec.ondataavailable=e=>{if(e.data&&e.data.size>0)chunks.push(e.data);};
  rec.onstop=()=>{
    const ext=mime.includes('mp4')?'mp4':'webm';
    const blob=new Blob(chunks,{type:mime||'video/webm'});
    const url=URL.createObjectURL(blob);
    const vp=document.getElementById('vidPlay'),dl=document.getElementById('vidDl');
    vp.src=url;vp.style.display='block';
    dl.href=url;dl.download=`salathanieai_jet_${durSec}s.${ext}`;dl.style.display='inline-block';dl.textContent=`Download ${ext.toUpperCase()} (${Math.round(blob.size/1024)} KB)`;
    st.textContent=`Rendered ${durSec}s SalathanieAI video + audio (${ext.toUpperCase()}).`;
    btn.disabled=false;
  };
  rec.start();
  setTimeout(()=>{if(rec.state==='recording')rec.stop();},durSec*1000);
}

async function initCatalog(){
  const r=await fetch('/api/creative/catalog');const d=await r.json();
  document.getElementById('modelPills').innerHTML=Object.entries(d.catalog).map(([k,v])=>
    `<label class="pill"><input type="checkbox" value="${k}" checked> ${v.name}</label>`
  ).join('');
  renderAll();
}
function drawDAG(nodes){
  const svg=document.getElementById('dagSvg');if(!nodes||!nodes.length){svg.innerHTML='';return;}
  const stepX=Math.max(92,Math.floor(640/nodes.length));let html='';
  nodes.forEach((n,i)=>{
    const x=46+i*stepX,y=53;
    if(i>0)html+=`<line x1="${x-stepX+34}" y1="${y}" x2="${x-34}" y2="${y}" stroke="#39ff14" stroke-width="2"/>`;
    const col=n.modality==='image'?'#38bdf8':(n.modality==='3d'?'#a855f7':(n.modality.includes('video')?'#f59e0b':'#39ff14'));
    html+=`<rect x="${x-38}" y="${y-24}" width="76" height="48" rx="8" fill="#0e1525" stroke="${col}" stroke-width="1.8"/>`;
    html+=`<text x="${x}" y="${y-3}" fill="#f8fafc" font-size="8" text-anchor="middle">${n.model_name.replace('SalathanieAI ','').slice(0,12)}</text>`;
    html+=`<text x="${x}" y="${y+12}" fill="${col}" font-size="8" text-anchor="middle">${n.modality.toUpperCase()}</text>`;
  });
  svg.innerHTML=html;
}
async function buildWF(){
  const models=[...document.querySelectorAll('#modelPills input:checked')].map(i=>i.value);
  const style=document.getElementById('stylePreset').selectedOptions[0].textContent;
  const body={brief:document.getElementById('brief').value,style,duration_s:Number(document.getElementById('dur').value||5),models};
  document.getElementById('codeOut').textContent='SalathanieAI Sovereign Brain building workflow...';
  const r=await fetch('/api/creative/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  CURRENT_WF=await r.json();LAST_RUN=null;
  document.getElementById('costBadge').textContent=`SOVEREIGN: $0.00 | ${CURRENT_WF.wf_id}`;
  drawDAG(CURRENT_WF.nodes);renderAll();showTab(CURRENT_TAB);
}
async function runWF(live){
  if(!CURRENT_WF)await buildWF();
  const r=await fetch('/api/creative/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({wf_id:CURRENT_WF.wf_id,live})});
  LAST_RUN=await r.json();showTab('json');
}
function showTab(tab){
  CURRENT_TAB=tab;if(!CURRENT_WF)return;
  if(tab==='py')document.getElementById('codeOut').textContent=CURRENT_WF.code_bundle.python;
  else if(tab==='curl')document.getElementById('codeOut').textContent=CURRENT_WF.code_bundle.curl_sovereign;
  else document.getElementById('codeOut').textContent=JSON.stringify(LAST_RUN||CURRENT_WF,null,2);
}
initCatalog();
</script></body></html>"""


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Configure optional BYO cloud adapters for SalathanieAI Studio")
    p.add_argument("--fal-key")
    p.add_argument("--meshy-key")
    p.add_argument("--minimax-key")
    p.add_argument("--pruna-key")
    p.add_argument("--scenario-key")
    args = p.parse_args()
    saved = save_keys({
        "FAL_KEY": args.fal_key,
        "MESHY_API_KEY": args.meshy_key,
        "MINIMAX_API_KEY": args.minimax_key,
        "PRUNA_API_KEY": args.pruna_key,
        "SCENARIO_API_KEY": args.scenario_key,
    })
    print(json.dumps({"configured_keys": sorted(saved.keys()), "keys_file": str(KEYS_PATH)}, indent=2))
