#!/usr/bin/env python3
"""
S-Zero Plus Virtual Flying Car Digital Twin (/car-3d) + Solar Hybrid Chronicle UI.
Zero external dependencies; renders a 3D wireframe physical-build prototype with
foldable tilt-rotors, solar-hybrid power bus, telemetry chronicles, and Shell Catcher status.
"""

CAR_3D_HTML = b"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>S-ZERO PLUS // VIRTUAL FLYING CAR DIGITAL TWIN</title>
<style>
  :root{--bg:#050911;--panel:#0b1320;--border:#1e3a5f;--cyan:#38bdf8;--gold:#f59e0b;--green:#22c55e;--purple:#a855f7;--text:#e2e8f0}
  *{box-sizing:border-box;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  body{margin:0;background:var(--bg);color:var(--text);padding:12px}
  .top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;background:var(--panel);border:1px solid var(--border);padding:10px 14px;border-radius:8px;margin-bottom:10px}
  .top h1{margin:0;font-size:14px;color:var(--cyan)}
  .nav{display:flex;gap:6px;flex-wrap:wrap}
  .nav a{color:#fff;text-decoration:none;font-size:11px;padding:4px 8px;border-radius:4px;border:1px solid var(--border);background:#0f1d32}
  .main{display:grid;grid-template-columns:1.2fr 1fr;gap:10px}
  @media(max-width:760px){.main{grid-template-columns:1fr}}
  .box{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px}
  canvas{width:100%;height:270px;background:#03070d;border:1px solid #152842;border-radius:6px;display:block}
  .btns{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}
  button{background:#0f2942;color:var(--cyan);border:1px solid var(--cyan);padding:9px 6px;border-radius:5px;font-weight:700;font-size:11px;cursor:pointer}
  button:active{background:var(--cyan);color:#050911}
  .kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
  .kpi{background:#070e18;border:1px solid #162b47;padding:8px 10px;border-radius:6px}
  .lbl{font-size:10px;color:#94a3b8;text-transform:uppercase}
  .val{font-size:17px;font-weight:700;color:#fff;margin-top:2px}
  .log{margin-top:8px;background:#040810;border:1px solid #162b47;padding:8px;border-radius:6px;font-size:11px;line-height:1.45;color:#cbd5e1;max-height:135px;overflow:auto}
</style>
</head>
<body>
<div class="top">
  <h1>ASTRA + ALSTRA + SALATHANIE-AI // S-ZERO PLUS VIRTUAL CAR TWIN</h1>
  <div class="nav">
    <a href="/">Master Deck</a>
    <a href="/hud">eVTOL HUD</a>
    <a href="/jet-3d">3D Jet</a>
    <a href="/car-3d" style="border-color:var(--gold);color:var(--gold)">3D Flying Car</a>
  </div>
</div>
<div class="main">
  <div class="box">
    <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:6px">
      <span style="color:var(--gold)">PHYSICAL BUILD CAD WIREFRAME // 4x TILT-ROTOR + CARBON CHASSIS</span>
      <span id="phaseTag" style="color:var(--green)">ROAD-TO-FLIGHT READY</span>
    </div>
    <canvas id="carCanvas" width="520" height="270"></canvas>
    <div class="btns">
      <button onclick="setMode('ROAD',0.25)">ROAD DRIVE</button>
      <button onclick="setMode('VTOL_HOVER',0.65)">VTOL HOVER</button>
      <button onclick="setMode('WING_CRUISE',0.80)">WING CRUISE</button>
      <button onclick="setMode('SOLAR_CHARGE',0.0)">SOLAR DOCK</button>
    </div>
  </div>
  <div class="box">
    <div class="kpis">
      <div class="kpi"><div class="lbl">Solar Hybrid Bus</div><div class="val" id="solarVal">3840W / 783V</div></div>
      <div class="kpi"><div class="lbl">Altitude / Speed</div><div class="val" id="kinVal">0 FT / 0 KTS</div></div>
      <div class="kpi"><div class="lbl">Shell Catcher Guard</div><div class="val" id="scVal" style="color:var(--green)">ARMED</div></div>
      <div class="kpi"><div class="lbl">Telemetry Chronicle</div><div class="val" id="chrVal">WAL SYNC</div></div>
    </div>
    <div class="log" id="chronicleLog">Initializing S-Zero Plus digital twin & Solar Hybrid chronicle...</div>
  </div>
</div>
<script>
const cv = document.getElementById('carCanvas');
const ctx = cv.getContext('2d');
let angle = 0.4, wingDeploy = 1.0, rotorSpin = 0, flightMode = 'WING_CRUISE';

function rotY(p, a){ const c=Math.cos(a), s=Math.sin(a); return [p[0]*c + p[2]*s, p[1], -p[0]*s + p[2]*c]; }
function proj(p){ const z = p[2] + 6.2; const f = 260 / z; return [cv.width/2 + p[0]*f, cv.height/2 + 12 - p[1]*f]; }

function drawLine(a, b, col, w=1.5){
  const pa = proj(rotY(a, angle)), pb = proj(rotY(b, angle));
  ctx.strokeStyle = col; ctx.lineWidth = w;
  ctx.beginPath(); ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]); ctx.stroke();
}

function renderTwin(){
  ctx.clearRect(0, 0, cv.width, cv.height);
  angle += 0.012; rotorSpin += 0.35;
  const targetWing = (flightMode === 'ROAD' || flightMode === 'SOLAR_CHARGE') ? 0.15 : 1.0;
  wingDeploy += (targetWing - wingDeploy) * 0.08;

  // Carbon-fiber aerodynamic fuselage
  const nose=[0,0.1,2.2], tail=[0,0.35,-2.2];
  const fl=[-0.75,-0.15,1.3], fr=[0.75,-0.15,1.3], rl=[-0.8,-0.15,-1.4], rr=[0.8,-0.15,-1.4];
  const cl=[-0.55,0.45,0.4], cr=[0.55,0.45,0.4], crl=[-0.55,0.48,-0.8], crr=[0.55,0.48,-0.8];
  [[nose,fl],[nose,fr],[fl,rl],[fr,rr],[rl,tail],[rr,tail],[nose,cl],[nose,cr],[cl,cr],[cl,crl],[cr,crr],[crl,crr],[crl,tail],[crr,tail],[fl,cl],[fr,cr],[rl,crl],[rr,crr]].forEach(e=>drawLine(e[0],e[1],'#38bdf8',1.6));

  // Solar roof array cells (gold)
  drawLine([-0.42,0.47,0.3],[0.42,0.47,0.3],'#f59e0b',2);
  drawLine([-0.42,0.49,-0.7],[0.42,0.49,-0.7],'#f59e0b',2);
  drawLine([-0.42,0.47,0.3],[-0.42,0.49,-0.7],'#f59e0b',1.5);
  drawLine([0.42,0.47,0.3],[0.42,0.49,-0.7],'#f59e0b',1.5);

  // Foldable gull-wings + 4 tilt-rotor pods
  const span = 0.75 + 1.85 * wingDeploy;
  [[-1,1.0],[1,1.0],[-1,-1.0],[1,-1.0]].forEach(([sx, sz])=>{
    const root = [sx*0.65, 0.25, sz*0.75];
    const tip  = [sx*span, 0.32 + 0.12*wingDeploy, sz*0.65];
    drawLine(root, tip, '#a855f7', 2);
    const rx = Math.cos(rotorSpin)*0.36, rz = Math.sin(rotorSpin)*0.36;
    drawLine([tip[0]-rx, tip[1]+0.08, tip[2]-rz], [tip[0]+rx, tip[1]+0.08, tip[2]+rz], '#22c55e', 2);
  });

  // Retractable road wheels
  [[-0.78,-0.38,1.2],[0.78,-0.38,1.2],[-0.82,-0.38,-1.3],[0.82,-0.38,-1.3]].forEach(w=>{
    drawLine([w[0],w[1]-0.14,w[2]],[w[0],w[1]+0.14,w[2]],'#94a3b8',2.5);
  });
  requestAnimationFrame(renderTwin);
}

async function setMode(mode, throttle){
  flightMode = mode;
  document.getElementById('phaseTag').textContent = mode;
  await fetch('/api/evtol/szero-plus',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,throttle,dt:1.5})});
  syncTwin();
}

async function syncTwin(){
  try{
    const [hudR, scR] = await Promise.all([fetch('/api/cockpit/telemetry'), fetch('/api/shell-catcher/status')]);
    const hud = await hudR.json();
    const sc = await scR.json();
    const lat = (hud.spine && hud.spine.latest) || {};
    document.getElementById('kinVal').textContent = `${lat.altitude_ft||0} FT / ${lat.airspeed_kts||0} KTS`;
    document.getElementById('solarVal').textContent = `3840W / ${lat.battery_pct||95}% SoC`;
    document.getElementById('scVal').textContent = sc.guard_active ? `ARMED (${sc.event_count||0} ev)` : 'STANDBY';
    document.getElementById('chrVal').textContent = `FRAME #${lat.frame_id||0} / 500`;
    document.getElementById('chronicleLog').innerHTML =
      `<div>[CHRONICLE] Craft=${lat.craft_id||'S-ZERO-PLUS-01'} | Alt=${lat.altitude_ft||0}ft | Spd=${lat.airspeed_kts||0}kts | RPM=${lat.rotor_rpm||0}</div>`+
      `<div>[SOLAR-HYBRID] Array=3840W | Bus=783.04V | Predictive=${hud.predictive?.status||'NOMINAL'}</div>`+
      `<div>[SHELL-CATCHER] Core=${sc.guard_active?'VERIFIED':'MISSING'} | DB=${sc.db_exists?'WAL_ONLINE':'INIT'} | Rules=${(sc.agent_mastery_rules||[]).join(', ')}</div>`;
  }catch(e){}
}
renderTwin();
syncTwin();
setInterval(syncTwin, 3000);
</script>
</body>
</html>
"""
