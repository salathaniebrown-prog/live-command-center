#!/usr/bin/env python3
"""
SalathanieAI — Port 8099 Unified Master Command Deck + Local Inference Engine
- Displays MODEL: SalathanieAI live across topbar & WAL ledger
- Exposes POST /api/salathanie-ai/infer returning ranked control/action decisions
  from live prompts, telemetry vectors, SQLite WAL flight ledger, PX4 & USGS/NWS/EONET feeds
"""
import http.server
import json
import os
import socket
import socketserver
import time
import urllib.request

import astra_alstra_jet_bridge as bridge
import astra_flight_ledger as ledger
import astra_memory_spine as spine
from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv

PORT = 8099
MODEL_NAME = "SalathanieAI"


def _proxy(targets: list[str], method: str = "GET", body: bytes = b"") -> tuple[int, str, bytes]:
    for url in targets:
        try:
            headers = {"User-Agent": "SalathanieAI-Deck-8099/4.0"}
            if method == "POST":
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=(body if method == "POST" else None), headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=5.0) as r:
                return r.status, r.headers.get("Content-Type", "text/html; charset=utf-8"), r.read()
        except Exception:
            continue
    return 502, "application/json", json.dumps({"error": "upstream_down", "targets": targets}).encode("utf-8")


def salathanie_ai_infer(body: dict) -> dict:
    """Fuse live prompt + telemetry vector + SQLite WAL flight ledger into ranked control/action decisions."""
    ts = int(time.time())
    prompt = str(body.get("prompt", "")).strip() or "Optimize Astra Jet stability and host efficiency"
    pl = prompt.lower()
    in_vec = body.get("telemetry") if isinstance(body.get("telemetry"), dict) else {}

    snap = ledger.get_ledger_snapshot(20)
    st = ledger.read_state_safe()
    gens = snap.get("generations") or []
    latest_g = gens[0] if gens else {}
    best_g = max(gens, key=lambda x: float(x.get("fitness", 0.0))) if gens else {}
    px4 = snap.get("px4_latest") or {}

    pods = in_vec.get("pods") if isinstance(in_vec.get("pods"), list) and len(in_vec["pods"]) == 4 else (st.get("pods") if isinstance(st.get("pods"), list) and len(st["pods"]) == 4 else [True, True, True, True])
    pods_active = sum(1 for b in pods if b)
    ram_pct = float(in_vec.get("ram_pct", latest_g.get("ram_pct", 80.0)))
    temp_c = float(in_vec.get("temp_c", latest_g.get("temp_c", 44.0)))
    pitch = float(in_vec.get("pitch", latest_g.get("pilot_pitch", 0.0)))
    roll = float(in_vec.get("roll", latest_g.get("pilot_roll", 0.0)))
    thrust = float(in_vec.get("thrust", latest_g.get("pilot_thrust", 0.68)))
    hazard = float(in_vec.get("hazard", snap.get("hazard_score", 0.0)))

    genome = dict(st.get("genome") or bridge.DEFAULT_GENOME)
    rag_hits = []
    try:
        from offline_wiki_rag import build_grounded_context
        rag = build_grounded_context(prompt, max_chars=500)
        if rag.get("hits"):
            rag_hits = rag.get("keywords", [])
    except Exception:
        pass

    # Compute real telemetry-driven scores for 5 actionable control strategies
    s_thermal = 58.0 + (26.0 if ram_pct >= 84.0 else 0.0) + (20.0 if temp_c >= 65.0 else 0.0) + (18.0 if any(k in pl for k in ("ram", "thermal", "heat", "cool", "save", "protect", "battery")) else 0.0)
    s_turb = 55.0 + hazard * 38.0 + (abs(pitch) + abs(roll)) * 12.0 + (18.0 if any(k in pl for k in ("turb", "storm", "wind", "hazard", "stabilize", "quake", "alert")) else 0.0)
    s_mutate = 62.0 + (14.0 if float(latest_g.get("fitness", 100.0)) < 96.0 else 0.0) + (24.0 if any(k in pl for k in ("mutate", "evolve", "upgrade", "optimize", "train", "genome")) else 0.0)
    s_promote = 64.0 + (float(best_g.get("fitness", 90.0)) - 85.0) * 1.1 + (pods_active * 2.0) + (14.0 if any(k in pl for k in ("best", "lock", "champion", "hold", "ledger")) else 0.0)
    s_px4 = 56.0 + (16.0 if px4.get("armed") else 4.0) + (24.0 if any(k in pl for k in ("px4", "drone", "waypoint", "gps", "cruise", "mission", "fria")) else 0.0)

    candidates = [
        {
            "action": "THERMAL_RAM_PROTECT_DERATE",
            "score": round(min(99.9, s_thermal), 2),
            "recommended_mode": "THERMAL-DERATE",
            "control_vector": {"pitch_cmd": round(-pitch * 0.4, 3), "roll_cmd": round(-roll * 0.4, 3), "thrust_trim": round(min(thrust, float(genome.get("thermal_derate", 0.72))), 4)},
            "rationale": f"Host RAM={ram_pct}% Temp={temp_c}C -> clamp thrust trim & preserve Android headroom.",
        },
        {
            "action": "TURBULENCE_HAZARD_DAMPING",
            "score": round(min(99.9, s_turb), 2),
            "recommended_mode": "TURBULENCE-LOCK",
            "control_vector": {"kp_pitch": round(min(1.2, float(genome.get("kp_pitch", 0.52)) * 1.1), 4), "kd_pitch": round(min(0.8, float(genome.get("kd_pitch", 0.25)) * 1.18), 4), "thrust_trim": round(max(0.55, min(0.82, thrust)), 4)},
            "rationale": f"External hazard={hazard} (USGS/NWS/EONET) & stick=({pitch:.2f},{roll:.2f}) -> boost derivative damping.",
        },
        {
            "action": "CLOSED_LOOP_MUTATE_SPRINT",
            "score": round(min(99.9, s_mutate), 2),
            "recommended_mode": "AUTONOMOUS-MUTATE",
            "control_vector": {"workers": 3, "pods_active": pods_active, "target_fitness": 98.5},
            "rationale": f"Run 3-worker supercomputer evolution over {pods_active}/4 pods and write verified GEN to WAL ledger.",
        },
        {
            "action": "PROMOTE_TOP_LEDGER_GENOME",
            "score": round(min(99.9, s_promote), 2),
            "recommended_mode": "AUTONOMOUS-MUTATE",
            "control_vector": {"champion_gen": best_g.get("gen_id", "GEN-000"), "fitness": best_g.get("fitness", 0.0), "thrust_trim": round(float(genome.get("thrust_trim", 0.68)), 4)},
            "rationale": f"Anchor controller to highest verified WAL ledger genome {best_g.get('gen_id', 'GEN-000')} (fit={best_g.get('fitness', 0.0)}).",
        },
        {
            "action": "PX4_VECTOR_CRUISE_LOCK",
            "score": round(min(99.9, s_px4), 2),
            "recommended_mode": "CRUISE-VECTOR",
            "control_vector": {"px4_lat": px4.get("lat"), "px4_lon": px4.get("lon"), "px4_alt_m": px4.get("alt_m"), "thrust_trim": round(min(0.76, thrust), 4)},
            "rationale": f"Sync cruise corridor with {px4.get('vehicle_id', 'PX4')} @ ({px4.get('lat')}, {px4.get('lon')}) [{px4.get('flight_mode', 'STANDBY')}].",
        },
    ]
    candidates.sort(key=lambda x: x["score"], reverse=True)
    for idx, c in enumerate(candidates, 1):
        c["rank"] = idx
        c["confidence"] = round(min(0.99, c["score"] / 100.0), 3)

    top = candidates[0]
    if body.get("apply"):
        ledger.atomic_write_state({"model": MODEL_NAME, "mode": top["recommended_mode"]}, preserve_overrides=False)

    fused_vec = {"ram_pct": ram_pct, "temp_c": temp_c, "pitch": pitch, "roll": roll, "thrust": thrust, "pods_active": pods_active, "hazard": hazard}
    sig = spine._hmac_sign(f"infer|{MODEL_NAME}|{ts}|{top['action']}|{top['score']}")
    try:
        with spine.db_conn() as c:
            c.execute(
                "INSERT INTO salathanie_inferences(ts,model,prompt,telemetry_json,top_action,top_score,decisions_json,hmac_sig) VALUES (?,?,?,?,?,?,?,?)",
                (ts, MODEL_NAME, prompt[:300], json.dumps(fused_vec), top["action"], top["score"], json.dumps(candidates), sig),
            )
    except Exception:
        pass

    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-ai-infer", PORT, 200, deterministic_hv(f"infer:{top['action']}:{top['score']}"))
    except Exception:
        pass

    return {
        "ok": True,
        "ts": ts,
        "model": MODEL_NAME,
        "role": "PRIMARY_SUPERCOMPUTER",
        "prompt": prompt,
        "telemetry_vector": fused_vec,
        "ledger_context": {"latest_gen": latest_g.get("gen_id"), "best_gen": best_g.get("gen_id"), "total_generations": snap["totals"]["generations"], "px4_vehicle": px4.get("vehicle_id"), "offline_wiki_keywords": rag_hits},
        "top_decision": top,
        "ranked_decisions": candidates,
        "applied": bool(body.get("apply")),
        "hmac_sig": sig,
    }


DECK_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>SALATHANIE AI // PORT 8099 UNIFIED COMMAND DECK</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:monospace}
html,body{width:100vw;height:100vh;overflow:hidden;background:#02060f;color:#e6f7ff}
#app{display:grid;grid-template-columns:45% 27% 28%;grid-template-rows:38px 1fr;gap:5px;padding:5px;width:100vw;height:100vh}
#topbar{grid-column:1/4;display:flex;align-items:center;justify-content:space-between;background:#081428;border:1px solid #00f0ff66;border-radius:6px;padding:0 10px;font-size:11px;gap:6px;overflow:hidden}
.pane{background:#071122;border:1px solid #1c3556;border-radius:6px;display:flex;flex-direction:column;overflow:hidden;min-height:0}
.phead{background:#0b1b34;border-bottom:1px solid #1c3556;padding:4px 8px;font-size:10px;font-weight:bold;color:#38bdf8;display:flex;justify-content:space-between;align-items:center}
.pbody{flex:1;overflow:auto;padding:6px;font-size:10px;min-height:0}
.split{display:grid;grid-template-rows:44% 56%;gap:5px;min-height:0}
iframe{width:100%;height:100%;border:none;background:#02060f}
button{background:#0ea5e9;color:#02060f;border:none;padding:3px 7px;border-radius:4px;font-family:monospace;font-size:9px;font-weight:bold;cursor:pointer}
button.grn{background:#39ff14}button.amb{background:#f59e0b}button.pur{background:#a855f7;color:#fff}
.row{border-bottom:1px solid #142844;padding:4px 0}
.badge{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:bold;background:#1e3a5f;color:#7ef9ff}
.b-ok{background:#14532d;color:#4ade80}.b-warn{background:#78350f;color:#fde047}.b-err{background:#7f1d1d;color:#fca5a5}.b-ai{background:#581c87;color:#f3e8ff;border:1px solid #c084fc}
.px4-box{background:#040b18;border:1px solid #0ea5e955;border-radius:5px;padding:5px;margin-bottom:6px}
.px4-in{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:3px;margin-top:4px}
.inf-in{display:grid;grid-template-columns:1fr auto auto;gap:3px;margin-bottom:5px}
input{background:#02060f;color:#e6f7ff;border:1px solid #2b4568;border-radius:3px;padding:3px 5px;font-family:monospace;font-size:9px;width:100%}
</style></head><body>
<div id="app">
  <div id="topbar">
    <div><b>UNIFIED COMMAND DECK (:8099)</b> <span id="modelBadge" class="badge b-ai">MODEL: SalathanieAI</span></div>
    <span id="topMeta" style="color:#39ff14">MODEL: SalathanieAI | WAL LEDGER SYNCING...</span>
    <div style="display:flex;gap:4px">
      <button class="grn" onclick="forceMutate()">FUSE &amp; MUTATE</button>
      <button class="amb" onclick="syncExternal()">SYNC USGS/NWS/EONET</button>
      <button class="pur" onclick="walFlush()">WAL FLUSH</button>
      <button onclick="window.open('http://127.0.0.1:8125','_blank')">PILOT :8125</button>
    </div>
  </div>

  <!-- LEFT: 3D JET COCKPIT -->
  <div class="pane">
    <div class="phead"><span>1. 3D JET COCKPIT (8095 &rarr; SALATHANIE AI)</span><span class="badge b-ok">LIVE</span></div>
    <iframe src="/proxy/jet" title="3D Jet Cockpit"></iframe>
  </div>

  <!-- CENTER: GATEWAY 8090 + PX4 & EXTERNAL FEEDS -->
  <div class="split">
    <div class="pane">
      <div class="phead"><span>2. UNIFIED GATEWAY PROXY (:8090)</span><span class="badge">8095 + 8088</span></div>
      <iframe src="/proxy/8090" title="Port 8090 Gateway"></iframe>
    </div>
    <div class="pane">
      <div class="phead"><span>3. PX4 DRONE + USGS / NWS / EONET</span><span id="hazBadge" class="badge">HAZARD 0.0</span></div>
      <div class="pbody">
        <div class="px4-box">
          <div id="px4Live">Loading PX4 telemetry...</div>
          <div class="px4-in">
            <input id="pLat" value="36.0999"><input id="pLon" value="-80.2442"><input id="pAlt" value="120.5">
            <button class="grn" onclick="pushPX4()">PX4 FIX</button>
          </div>
        </div>
        <div id="extList">Loading external feeds...</div>
      </div>
    </div>
  </div>

  <!-- RIGHT: SALATHANIE AI INFERENCE + SQLITE WAL FLIGHT LEDGER -->
  <div class="split">
    <div class="pane">
      <div class="phead"><span>4. SALATHANIE AI INFER (/api/salathanie-ai/infer)</span><span class="badge b-ai">RANKED</span></div>
      <div class="pbody">
        <div class="inf-in">
          <input id="aiPrompt" value="Stabilize jet, protect RAM, and lock best ledger genome">
          <button class="pur" onclick="runInfer(false)">INFER</button>
          <button class="grn" onclick="runInfer(true)">APPLY</button>
        </div>
        <div id="inferOut" style="color:#c4b5fd">Ready for live prompt + telemetry vector inference.</div>
      </div>
    </div>
    <div class="pane">
      <div class="phead"><span>5. SQLITE WAL FLIGHT LEDGER</span><span id="walBadge" class="badge b-ok">WAL OK</span></div>
      <div class="pbody" id="ledgerFeed">Connecting to WAL stream...</div>
    </div>
  </div>
</div>

<script>
async function refreshDeck(){
  try{
    const d=await(await fetch('/api/ledger')).json();
    const g0=(d.generations||[])[0]||{};
    document.getElementById('topMeta').textContent=
      `MODEL: SalathanieAI | GEN: ${g0.gen_id||'--'} | FIT: ${g0.fitness??'--'} | PODS: ${g0.pods_mask||'----'} | RAM: ${g0.ram_pct??'--'}%`;
    document.getElementById('walBadge').textContent=`${d.totals.generations} GENS | WAL ${d.wal.wal_kb}KB`;
    const hz=document.getElementById('hazBadge');
    hz.textContent=`HAZARD ${d.hazard_score}`;
    hz.className='badge '+(d.hazard_score>=0.35?'b-err':(d.hazard_score>0.1?'b-warn':'b-ok'));

    const p=d.px4_latest||{};
    document.getElementById('px4Live').innerHTML=
      `<b style="color:#39ff14">${p.vehicle_id||'PX4'}</b> [${p.flight_mode||'--'}] (${p.source||'--'})<br>`+
      `LAT: <b>${p.lat}</b> | LON: <b>${p.lon}</b> | ALT: <b>${p.alt_m}m</b> | BAT: <b>${p.battery_pct}%</b>`;

    document.getElementById('extList').innerHTML=(d.external_feeds||[]).map(e=>{
      const cls=(e.severity==='HIGH'||e.severity==='SEVERE'||e.severity==='ALERT')?'b-warn':(e.severity==='NOMINAL'?'b-ok':'');
      return `<div class="row"><span class="badge ${cls}">${e.source}</span> <b>${e.title}</b></div>`;
    }).join('')||'No external events.';

    document.getElementById('ledgerFeed').innerHTML=(d.generations||[]).map(g=>{
      const t=new Date(g.ts*1000).toLocaleTimeString();
      return `<div class="row">`+
        `<span class="badge b-ai">SalathanieAI</span> <b>${g.gen_id}</b> <span class="badge ${g.promoted?'b-ok':''}">${g.promoted?'PROMOTED':'HOLD'}</span> `+
        `<span style="color:#38bdf8">FIT ${g.fitness}</span> <small style="color:#94a3b8">${t}</small><br>`+
        `<small>MODE: ${g.mode} | PODS: [${g.pods_mask}] | STICK: (${g.pilot_pitch},${g.pilot_roll}) | RAM ${g.ram_pct}%</small><br>`+
        `<small style="color:#cbd5e1">${g.reason}</small></div>`;
    }).join('')||'Waiting for cycle...';
  }catch(e){}
}
async function runInfer(apply){
  const prompt=document.getElementById('aiPrompt').value;
  document.getElementById('inferOut').textContent='Running SalathanieAI ranked decision engine...';
  const r=await fetch('/api/salathanie-ai/infer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,apply})});
  const d=await r.json();
  document.getElementById('inferOut').innerHTML=(d.ranked_decisions||[]).map(x=>
    `<div class="row"><span class="badge ${x.rank===1?'b-ok':''}">#${x.rank} (${x.score})</span> <b>${x.action}</b> &rarr; ${x.recommended_mode}<br><small style="color:#cbd5e1">${x.rationale}</small></div>`
  ).join('');
  if(apply) refreshDeck();
}
async function forceMutate(){
  await fetch('/api/bridge/cycle',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"sync_ext":false}'});
  refreshDeck();
}
async function syncExternal(){
  await fetch('/api/external/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  refreshDeck();
}
async function walFlush(){
  await fetch('/api/wal/checkpoint',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  refreshDeck();
}
async function pushPX4(){
  await fetch('/api/px4',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    vehicle_id:'PX4-EAGLE-01',lat:parseFloat(document.getElementById('pLat').value),lon:parseFloat(document.getElementById('pLon').value),
    alt_m:parseFloat(document.getElementById('pAlt').value),flight_mode:'MISSION_ACTIVE',armed:true,battery_pct:94.0
  })});
  refreshDeck();
}
refreshDeck(); runInfer(false); setInterval(refreshDeck, 3000);
</script></body></html>""".encode("utf-8")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class H(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        try:
            p = self.path.split("?")[0]
            if p == "/":
                return self._send(200, "text/html; charset=utf-8", DECK_HTML)
            if p == "/api/ledger":
                return self._send(200, "application/json", json.dumps(ledger.get_ledger_snapshot(20)).encode("utf-8"))
            if p == "/api/salathanie-ai/status":
                return self._send(200, "application/json", json.dumps({"ok": True, "model": MODEL_NAME, "endpoint": "/api/salathanie-ai/infer", "spine": spine.spine_status()}).encode("utf-8"))
            if p == "/proxy/jet":
                c, ct, data = _proxy(["http://127.0.0.1:8095/", "http://127.0.0.1:8125/jet-3d"])
                return self._send(c, ct, data)
            if p == "/proxy/8090":
                c, ct, data = _proxy(["http://127.0.0.1:8090/"])
                return self._send(c, ct, data)
            if p == "/proxy/8088":
                c, ct, data = _proxy(["http://127.0.0.1:8088/", "http://127.0.0.1:8125/"])
                return self._send(c, ct, data)
            if p in ("/api/hud", "/api/gw/status"):
                targets = ["http://127.0.0.1:8095/api/hud", "http://127.0.0.1:8125/api/hud"] if p == "/api/hud" else ["http://127.0.0.1:8090/api/gw/status"]
                c, ct, data = _proxy(targets)
                return self._send(c, ct, data)
            return self._send(404, "application/json", b'{"error":"not_found"}')
        except Exception as e:
            return self._send(500, "application/json", json.dumps({"error": str(e)}).encode("utf-8"))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 65536)) if length else b"{}"
            p = self.path.split("?")[0]
            body = json.loads(raw.decode("utf-8", errors="ignore") or "{}")
            if p == "/api/salathanie-ai/infer":
                return self._send(200, "application/json", json.dumps(salathanie_ai_infer(body)).encode("utf-8"))
            if p == "/api/px4":
                return self._send(200, "application/json", json.dumps({"ok": True, "px4": ledger.record_px4(body, "px4_deck_8099")}).encode("utf-8"))
            if p == "/api/external/sync":
                return self._send(200, "application/json", json.dumps(ledger.sync_external_feeds()).encode("utf-8"))
            if p == "/api/wal/checkpoint":
                return self._send(200, "application/json", json.dumps(ledger.wal_checkpoint()).encode("utf-8"))
            if p == "/api/bridge/cycle":
                return self._send(200, "application/json", json.dumps(bridge.run_closed_loop_cycle(bool(body.get("sync_ext")))).encode("utf-8"))
            if p in ("/api/mode", "/api/pods", "/api/pilot"):
                c, ct, data = _proxy([f"http://127.0.0.1:8095{p}", f"http://127.0.0.1:8125{p}"], "POST", raw)
                return self._send(c, ct, data)
            return self._send(404, "application/json", b'{"error":"not_found"}')
        except Exception as e:
            return self._send(500, "application/json", json.dumps({"error": str(e)}).encode("utf-8"))

    def _send(self, code, ct, data):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    with Server(("0.0.0.0", PORT), H) as srv:
        srv.serve_forever()
