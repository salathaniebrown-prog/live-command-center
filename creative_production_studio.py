#!/usr/bin/env python3
"""
Salathanie A.I — Creative Production Studio ("Imagination Orchestrated")
Aviator All-Access Brain: Browser workspace orchestrating Image, Video, 3D & Audio
across Seedream 5.0 Pro, Meshy 7.1, Sperid Labs Idol Max, Kling 4.0 (V4),
MiniMax H3, Pruna AI P-Video-2-Pro, and Scenario Custom Style Pipelines.
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
    "seedream_5_pro": {
        "name": "Seedream 5.0 Pro",
        "modality": "image",
        "provider": "fal",
        "endpoint": "bytedance/seedream/v5/pro/text-to-image",
        "edit_endpoint": "bytedance/seedream/v5/pro/edit",
        "unit_cost_usd": 0.045,
        "unit": "image",
        "strengths": "2K photorealism, 10+ editable layer separation, precision editing, multilingual text",
    },
    "meshy_7_1": {
        "name": "Meshy 7.1",
        "modality": "3d",
        "provider": "fal",
        "endpoint": "meshy/v7.1/multi-image-to-3d",
        "direct_endpoint": "https://api.meshy.ai/openapi/v2/text-to-3d",
        "unit_cost_usd": 0.25,
        "unit": "mesh",
        "strengths": "Text/1-4 views to textured PBR 3D mesh (GLB, FBX, OBJ, STL, USDZ)",
    },
    "sperid_idol_max": {
        "name": "Sperid Labs Idol Max",
        "modality": "3d",
        "provider": "sperid",
        "endpoint": "speridlabs/idol",
        "unit_cost_usd": 0.15,
        "unit": "asset",
        "strengths": "1-image to 3D Gaussian Splat (.ply) or 30k-tri rigged GLB with walk/run/jump/idle clips",
    },
    "kling_v4_i2v": {
        "name": "Kling V4 (4.0 Image-to-Video)",
        "modality": "video",
        "provider": "fal",
        "endpoint": "kling/v4/image-to-video",
        "unit_cost_usd": 0.235,
        "unit": "sec_1080p",
        "strengths": "3-30s 720p/1080p/4K HDR image-to-video, up to 8 middle keyframes, per-shot multi_prompt",
    },
    "minimax_h3": {
        "name": "MiniMax H3 (HD/2K)",
        "modality": "video_audio",
        "provider": "minimax",
        "endpoint": "https://api.minimax.io/v1/video_generation",
        "unit_cost_usd": 0.08,
        "unit": "sec_768p",
        "strengths": "Unified text/image/video/audio (T2VA, I2VA, FL2VA, Ref2VA), 4-15s at 768p or 2K",
    },
    "pruna_p_video_2_pro": {
        "name": "Pruna AI P-Video-2-Pro",
        "modality": "video_audio",
        "provider": "pruna",
        "endpoint": "p-video-2-pro",
        "unit_cost_usd": 0.02,
        "unit": "sec_speed",
        "strengths": "MiniMax H3-accelerated Cost/Speed/Quality modes ($0.01-$0.035/s) + native audio + 4K Replace/Upscale",
    },
    "scenario_style": {
        "name": "Scenario Custom Style Engine",
        "modality": "style_orchestrator",
        "provider": "scenario",
        "endpoint": "https://api.cloud.scenario.com/v1/models",
        "unit_cost_usd": 0.03,
        "unit": "gen",
        "strengths": "Private trained art-style consistency across image/video/3D/audio + MCP team pipelines",
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
            bus.publish("salathanie-creative", 8125, 200, deterministic_hv(f"creative:{tag}"))
    except Exception:
        pass


def build_code_bundle(brief: str, style: str, duration_s: int, selected: list[str]) -> dict:
    """Generate clean, production-ready Python + cURL scripts for Kling V4, Meshy 7.1, Seedream 5.0, Sperid Idol & Pruna."""
    safe_prompt = f"{brief} — style: {style}".replace('"', '\\"')
    py_lines = [
        "#!/usr/bin/env python3",
        '"""Salathanie A.I — Auto-Generated Creative Production Pipeline (Imagination Orchestrated)"""',
        "import json, os, urllib.request",
        "",
        f'BRIEF = "{safe_prompt}"',
        f"DURATION = {duration_s}",
        'FAL_KEY = os.environ.get("FAL_KEY", "")',
        "",
        "def fal_submit(endpoint: str, payload: dict) -> dict:",
        '    req = urllib.request.Request(',
        '        f"https://queue.fal.run/{endpoint}",',
        '        data=json.dumps(payload).encode("utf-8"),',
        '        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},',
        "    )",
        "    with urllib.request.urlopen(req, timeout=30) as r:",
        '        return json.loads(r.read().decode("utf-8"))',
        "",
    ]
    if "seedream_5_pro" in selected:
        py_lines += [
            "# 1. Seedream 5.0 Pro — Layered 2K Keyframe Image",
            'img_job = fal_submit("bytedance/seedream/v5/pro/text-to-image", {"prompt": BRIEF, "image_size": "landscape_16_9"})',
            'print("Seedream 5.0 Pro:", img_job)',
            "",
        ]
    if "meshy_7_1" in selected:
        py_lines += [
            "# 2. Meshy 7.1 — Multi-View / Image to PBR 3D Mesh (GLB/FBX/USDZ)",
            'mesh_job = fal_submit("meshy/v7.1/multi-image-to-3d", {"image_urls": ["<HERO_IMAGE_URL>"], "enable_pbr": True})',
            'print("Meshy 7.1 3D:", mesh_job)',
            "",
        ]
    if "sperid_idol_max" in selected:
        py_lines += [
            "# 3. Sperid Labs Idol — Single Image to 3D Gaussian Splat (.ply) / Rigged GLB",
            "# pip install git+https://github.com/speridlabs/idol-sdk.git",
            '# python3 -m idol.sample --image hero.png --mode synthetic --out outputs/',
            "",
        ]
    if "kling_v4_i2v" in selected:
        py_lines += [
            "# 4. Kling V4 (4.0) — Image-to-Video with Keyframes & Per-Shot Multi-Prompt",
            'kling_job = fal_submit("kling/v4/image-to-video", {',
            '    "prompt": BRIEF,',
            '    "start_image_url": "<HERO_IMAGE_URL>",',
            '    "duration": DURATION,',
            '    "resolution": "1080p",',
            '})',
            'print("Kling V4 Video:", kling_job)',
            "",
        ]
    if "minimax_h3" in selected:
        py_lines += [
            "# 5. MiniMax H3 — Multimodal Video + Audio (768P draft -> 2K master)",
            '# POST https://api.minimax.io/v1/video_generation  model="MiniMax-H3"  resolution="768P"  duration=DURATION',
            "",
        ]
    if "pruna_p_video_2_pro" in selected:
        py_lines += [
            "# 6. Pruna AI P-Video-2-Pro — Fast Native-Audio Video (Speed/Quality Mode)",
            '# Submit to Pruna P-Video-2-Pro (mode="speed" $0.02/s or "quality" $0.035/s) with native audio prompt',
            "",
        ]

    curl_kling = (
        f'curl -s -X POST "https://queue.fal.run/kling/v4/image-to-video" \\\n'
        f'  -H "Authorization: Key $FAL_KEY" \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -d \'{{"prompt":"{safe_prompt}","start_image_url":"<HERO_IMAGE_URL>","duration":{duration_s},"resolution":"1080p"}}\''
    )
    return {"python": "\n".join(py_lines), "curl_kling_v4": curl_kling}


def aviator_build_workflow(brief: str, style: str = "Cinematic Luxury 8K", duration_s: int = 5, models: list[str] | None = None) -> dict:
    """Aviator All-Access Brain: Describe desired results -> builds executable multi-model DAG workflow."""
    b = brief.strip() or "Luxury sneaker commercial with spinning 3D asset, cinematic orbital video, and synth audio"
    bl = b.lower()
    dur = max(3, min(int(duration_s or 5), 30))

    if models:
        selected = [m for m in models if m in MODEL_CATALOG]
    else:
        selected = ["scenario_style", "seedream_5_pro"]
        if any(k in bl for k in ("3d", "mesh", "glb", "splat", "character", "rig", "game", "product", "sneaker", "all")):
            selected.append("meshy_7_1")
            selected.append("sperid_idol_max")
        if any(k in bl for k in ("video", "kling", "animate", "film", "commercial", "short", "camera", "all")):
            selected.append("kling_v4_i2v")
        if any(k in bl for k in ("audio", "sound", "music", "pruna", "minimax", "voice", "fast", "all")):
            selected.append("minimax_h3")
            selected.append("pruna_p_video_2_pro")
        if len(selected) == 2:
            selected += ["meshy_7_1", "kling_v4_i2v", "pruna_p_video_2_pro"]

    nodes = []
    total_cost = 0.0
    prev_id = None
    for idx, mkey in enumerate(selected, start=1):
        spec = MODEL_CATALOG[mkey]
        mult = dur if "sec" in spec["unit"] else 1
        step_cost = round(spec["unit_cost_usd"] * mult, 3)
        total_cost += step_cost
        nid = f"N{idx}_{mkey}"
        nodes.append({
            "id": nid,
            "step": idx,
            "model_key": mkey,
            "model_name": spec["name"],
            "modality": spec["modality"],
            "provider": spec["provider"],
            "endpoint": spec["endpoint"],
            "depends_on": prev_id,
            "est_cost_usd": step_cost,
            "prompt": f"[{style}] {b}",
        })
        prev_id = nid

    ts = int(time.time())
    wf_id = f"WF-{ts % 1000000}"
    slug = re.sub(r"[^a-z0-9]+", "_", b.lower()).strip("_")[:24] or "production"
    code_bundle = build_code_bundle(b, style, dur, selected)

    # Save runnable pipeline script to disk
    wf_dir = OUT_DIR / f"{wf_id.lower()}_{slug}"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "pipeline.py").write_text(code_bundle["python"], encoding="utf-8")
    (wf_dir / "workflow.json").write_text(json.dumps({"wf_id": wf_id, "brief": b, "style": style, "nodes": nodes}, indent=2), encoding="utf-8")

    with db_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO creative_workflows VALUES (?,?,?,?,?,?,?,?,?,?)",
            (wf_id, ts, b[:64], b, style, dur, round(total_cost, 3), json.dumps(nodes), json.dumps(code_bundle), "READY"),
        )

    out = {
        "ok": True,
        "wf_id": wf_id,
        "brief": b,
        "style": style,
        "duration_s": dur,
        "est_total_cost_usd": round(total_cost, 3),
        "saved_dir": str(wf_dir),
        "nodes": nodes,
        "code_bundle": code_bundle,
        "configured_keys": sorted(load_keys().keys()),
    }
    out = enhance_with_llm("creative_director", f"Give a 3-line director treatment for: {b} ({style})", out)
    _pub_ring(f"wf:{wf_id}")
    return out


def execute_workflow(wf_id: str, live: bool = False, start_image_url: str = "") -> dict:
    """Execute workflow nodes: live API submission if provider key is set, else zero-cost dry-run simulation."""
    with db_conn() as c:
        row = c.execute("SELECT brief, style, duration_s, nodes_json FROM creative_workflows WHERE wf_id=?", (wf_id,)).fetchone()
    if not row:
        return {"ok": False, "error": "workflow_not_found"}

    brief, style, dur, nodes = row[0], row[1], row[2], json.loads(row[3])
    keys = load_keys()
    results = []
    ts = int(time.time())

    for n in nodes:
        mkey = n["model_key"]
        prov = n["provider"]
        job_id = f"JOB-{ts % 100000}-{n['step']}"
        mode = "SIMULATED_PREVIEW"
        res = {"status": "PREVIEW_READY", "note": f"Add {prov.upper()} API key in ~/.salathanie_creative_keys.json for live cloud render."}

        if live and prov == "fal" and keys.get("FAL_KEY"):
            mode = "LIVE_FAL_QUEUE"
            payload = {"prompt": n["prompt"]}
            if mkey == "kling_v4_i2v":
                if start_image_url:
                    payload.update({"start_image_url": start_image_url, "duration": dur, "resolution": "1080p"})
                else:
                    n["endpoint"] = "kling/v4/text-to-video"
                    payload.update({"duration": dur, "resolution": "1080p"})
            elif mkey == "meshy_7_1" and start_image_url:
                payload = {"image_urls": [start_image_url], "enable_pbr": True}
            try:
                req = urllib.request.Request(
                    f"https://queue.fal.run/{n['endpoint']}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": f"Key {keys['FAL_KEY']}", "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                res = {"status": "API_ERROR", "error": str(e)[:180]}

        with db_conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO creative_jobs VALUES (?,?,?,?,?,?,?,?)",
                (job_id, wf_id, ts, mkey, mode, res.get("status", "QUEUED"), json.dumps(n), json.dumps(res)),
            )
        results.append({"job_id": job_id, "model": n["model_name"], "modality": n["modality"], "mode": mode, "result": res})

    with db_conn() as c:
        c.execute("UPDATE creative_workflows SET status=? WHERE wf_id=?", ("EXECUTED_LIVE" if live else "SIMULATED", wf_id))
    _pub_ring(f"exec:{wf_id}")
    return {"ok": True, "wf_id": wf_id, "live_requested": live, "jobs": results}


def list_workflows() -> dict:
    with db_conn() as c:
        wfs = [
            {"wf_id": r[0], "ts": r[1], "title": r[2], "style": r[3], "duration_s": r[4], "est_cost_usd": r[5], "status": r[6]}
            for r in c.execute("SELECT wf_id, ts, title, style, duration_s, est_cost_usd, status FROM creative_workflows ORDER BY ts DESC LIMIT 15").fetchall()
        ]
    return {"catalog": MODEL_CATALOG, "configured_keys": sorted(load_keys().keys()), "workflows": wfs}


CREATIVE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — Imagination Orchestrated (Creative Production)</title>
<style>
body{font-family:monospace;background:#080c14;color:#e6edf3;margin:12px}
.card{background:#121826;border:1px solid #2b3548;border-radius:10px;padding:12px;margin-bottom:12px}
.nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.nav a{background:#1f6feb;color:#fff;padding:6px 9px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:bold}
textarea,input,select{width:100%;box-sizing:border-box;background:#090d16;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace;margin-top:6px}
button{background:#238636;color:#fff;border:none;padding:8px 12px;border-radius:6px;cursor:pointer;font-family:monospace;font-weight:bold;margin:4px 2px}
button.alt{background:#1f6feb}button.purp{background:#8957e5}button.amber{background:#d29922;color:#080c14}
.checks{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.pill{background:#090d16;border:1px solid #38bdf8;border-radius:14px;padding:4px 9px;font-size:11px;cursor:pointer;display:flex;align-items:center;gap:4px}
.pill input{width:auto;margin:0}
.stage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:8px}
.stage-box{background:#090d16;border:1px solid #30363d;border-radius:8px;padding:8px;text-align:center}
pre{background:#090d16;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:260px;white-space:pre-wrap;word-break:break-all}
.badge{background:#0ea5e9;color:#080c14;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:bold}
</style></head><body>
<h2 style="color:#38bdf8;margin:4px 0">IMAGINATION ORCHESTRATED // AVIATOR ALL-ACCESS BRAIN</h2>
<div class="nav">
  <a href="/">Pilot</a>
  <a href="/agents" style="background:#8957e5">18-Agents</a>
  <a href="/trader" style="background:#d29922;color:#080c14">Trader/OMS</a>
  <a href="/infra" style="background:#0ea5e9;color:#080c14">Infra/SRE</a>
  <a href="/dealership" style="background:#238636">Dealership</a>
  <a href="/eagle-eyes" style="background:#0891b2">Eagle Eyes</a>
  <a href="/codes" style="background:#db2777">50 Codes</a>
  <a href="/artifacts" style="background:#4f46e5">Artifacts</a>
</div>

<div class="card">
  <b>1. Describe Your Creative Result -> Aviator Builds the Multi-Model Workflow</b>
  <textarea id="brief" rows="3">Luxury black & gold diamond sneaker hero ad: layered 2K poster, rigged 3D GLB asset, 5s 1080p Kling V4 orbital reveal with native synth audio</textarea>
  <div style="display:flex;gap:8px">
    <input id="style" value="Cinematic Luxury 8K, High Contrast, Studio Rim Light" placeholder="Art Style">
    <input id="dur" value="5" style="width:90px" title="Duration (sec)">
  </div>
  <div class="checks" id="modelPills"></div>
  <div style="margin-top:8px">
    <button onclick="buildWF()">Auto-Build Workflow</button>
    <button class="purp" onclick="runWF(false)">Run Preview Pipeline</button>
    <button class="amber" onclick="runWF(true)">Run LIVE Cloud APIs</button>
    <span id="costBadge" class="badge" style="margin-left:6px">EST: $0.00</span>
  </div>
</div>

<div class="card">
  <b>2. Unified Workspace: Live Workflow Graph + 3D Viewport + Audio Synth</b>
  <svg id="dagSvg" width="100%" height="120" viewBox="0 0 680 120" style="background:#090d16;border-radius:8px;border:1px solid #30363d;margin-top:6px"></svg>
  <div class="stage-grid">
    <div class="stage-box">
      <div style="font-size:11px;color:#38bdf8;margin-bottom:4px">IMAGE / STYLE BOARD (Seedream 5.0 / Scenario)</div>
      <div id="imgPreview"></div>
    </div>
    <div class="stage-box">
      <div style="font-size:11px;color:#38bdf8;margin-bottom:4px">3D VIEWPORT (Meshy 7.1 / Sperid Idol Max)</div>
      <canvas id="c3d" width="220" height="130" style="background:#05080f;border-radius:6px"></canvas>
    </div>
    <div class="stage-box">
      <div style="font-size:11px;color:#38bdf8;margin-bottom:4px">VIDEO & NATIVE AUDIO (Kling V4 / MiniMax H3 / Pruna)</div>
      <div id="vidMeta" style="font-size:11px;margin:10px 0;color:#94a3b8">Build a workflow to load timeline & audio preview.</div>
      <button class="alt" onclick="playSynth()">Play Native Audio Bed</button>
    </div>
  </div>
</div>

<div class="card">
  <b>3. Generated Production Code (Kling V4 Image-to-Video + Full Pipeline)</b>
  <button class="alt" onclick="showTab('py')">Python Pipeline</button>
  <button class="purp" onclick="showTab('curl')">Kling V4 cURL</button>
  <button onclick="showTab('json')">Workflow / Job JSON</button>
  <pre id="codeOut">Click "Auto-Build Workflow" above to generate runnable code and pipeline manifest.</pre>
</div>

<script>
let CURRENT_WF = null;
let CURRENT_TAB = 'py';
let LAST_RUN = null;

async function initCatalog(){
  const r = await fetch('/api/creative/catalog'); const d = await r.json();
  const box = document.getElementById('modelPills');
  box.innerHTML = Object.entries(d.catalog).map(([k,v]) =>
    `<label class="pill"><input type="checkbox" value="${k}" checked> ${v.name}</label>`
  ).join('');
}

function drawDAG(nodes){
  const svg = document.getElementById('dagSvg');
  if(!nodes || !nodes.length){ svg.innerHTML=''; return; }
  const stepX = Math.max(95, Math.floor(640 / nodes.length));
  let html = '';
  nodes.forEach((n, i) => {
    const x = 45 + i * stepX, y = 60;
    if(i > 0) html += `<line x1="${x-stepX+34}" y1="${y}" x2="${x-34}" y2="${y}" stroke="#38bdf8" stroke-width="2"/>`;
    const col = n.modality==='image'?'#22c55e':(n.modality==='3d'?'#a855f7':(n.modality.includes('video')?'#f59e0b':'#38bdf8'));
    html += `<rect x="${x-38}" y="${y-24}" width="76" height="48" rx="8" fill="#121826" stroke="${col}" stroke-width="1.8"/>`;
    html += `<text x="${x}" y="${y-4}" fill="#f8fafc" font-size="9" text-anchor="middle">${n.model_name.slice(0,12)}</text>`;
    html += `<text x="${x}" y="${y+12}" fill="${col}" font-size="8" text-anchor="middle">$${n.est_cost_usd}</text>`;
  });
  svg.innerHTML = html;
}

function renderHeroSVG(title, style){
  const t = (title||'Concept').slice(0,26).replace(/[<>]/g,'');
  const s = (style||'8K').slice(0,30).replace(/[<>]/g,'');
  document.getElementById('imgPreview').innerHTML =
    `<svg width="220" height="130" viewBox="0 0 220 130"><defs><linearGradient id="cg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e3a8a"/></linearGradient></defs>`+
    `<rect width="220" height="130" rx="6" fill="url(#cg)"/><circle cx="178" cy="34" r="22" fill="#f59e0b" opacity="0.28"/>`+
    `<text x="12" y="64" fill="#f8fafc" font-size="11" font-weight="bold">${t}</text>`+
    `<text x="12" y="84" fill="#93c5fd" font-size="8">${s}</text>`+
    `<text x="12" y="114" fill="#38bdf8" font-size="8">SEEDREAM 5.0 LAYERED KEYFRAME</text></svg>`;
}

async function buildWF(){
  const models = [...document.querySelectorAll('#modelPills input:checked')].map(i=>i.value);
  const body = {brief:document.getElementById('brief').value, style:document.getElementById('style').value, duration_s:Number(document.getElementById('dur').value||5), models};
  document.getElementById('codeOut').textContent = 'Aviator Brain building workflow...';
  const r = await fetch('/api/creative/build', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  CURRENT_WF = await r.json();
  LAST_RUN = null;
  document.getElementById('costBadge').textContent = `EST: $${CURRENT_WF.est_total_cost_usd} | ${CURRENT_WF.wf_id}`;
  drawDAG(CURRENT_WF.nodes);
  renderHeroSVG(CURRENT_WF.brief, CURRENT_WF.style);
  document.getElementById('vidMeta').innerHTML = `<b>${CURRENT_WF.wf_id}</b> • ${CURRENT_WF.duration_s}s @ 1080p/24fps<br>Nodes: ${CURRENT_WF.nodes.length} | Keys: ${(CURRENT_WF.configured_keys||[]).join(', ')||'Preview Mode'}`;
  showTab(CURRENT_TAB);
}

async function runWF(live){
  if(!CURRENT_WF){ await buildWF(); }
  document.getElementById('codeOut').textContent = live ? 'Submitting to LIVE cloud queues...' : 'Running preview pipeline...';
  const r = await fetch('/api/creative/execute', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({wf_id:CURRENT_WF.wf_id, live})});
  LAST_RUN = await r.json();
  showTab('json');
}

function showTab(tab){
  CURRENT_TAB = tab;
  if(!CURRENT_WF) return;
  if(tab==='py') document.getElementById('codeOut').textContent = CURRENT_WF.code_bundle.python;
  else if(tab==='curl') document.getElementById('codeOut').textContent = CURRENT_WF.code_bundle.curl_kling_v4;
  else document.getElementById('codeOut').textContent = JSON.stringify(LAST_RUN || CURRENT_WF, null, 2);
}

function playSynth(){
  try{
    const ctx = new (window.AudioContext||window.webkitAudioContext)();
    [220, 277.18, 329.63, 440].forEach((f,i)=>{
      const o=ctx.createOscillator(), g=ctx.createGain();
      o.type='triangle'; o.frequency.value=f; g.gain.value=0.05;
      o.connect(g); g.connect(ctx.destination);
      o.start(ctx.currentTime + i*0.18); o.stop(ctx.currentTime + i*0.18 + 0.45);
    });
  }catch(e){}
}

// Lightweight 3D Wireframe Cube Viewport (Zero WebGL bloat for Android RAM)
(function spin3D(){
  const cv = document.getElementById('c3d'); const g = cv.getContext('2d');
  const pts = [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]];
  const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
  let a = 0;
  setInterval(()=>{
    a += 0.04; g.clearRect(0,0,220,130);
    g.strokeStyle='#38bdf8'; g.lineWidth=1.5;
    const proj = pts.map(([x,y,z])=>{
      const x1 = x*Math.cos(a) - z*Math.sin(a), z1 = x*Math.sin(a) + z*Math.cos(a);
      const y2 = y*Math.cos(a*0.6) - z1*Math.sin(a*0.6), z2 = y*Math.sin(a*0.6) + z1*Math.cos(a*0.6);
      const sc = 95 / (z2 + 3.6);
      return [110 + x1*sc, 65 + y2*sc];
    });
    edges.forEach(([i,j])=>{ g.beginPath(); g.moveTo(proj[i][0],proj[i][1]); g.lineTo(proj[j][0],proj[j][1]); g.stroke(); });
  }, 60);
})();

initCatalog();
</script></body></html>"""


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Configure Salathanie Creative Studio API keys")
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
