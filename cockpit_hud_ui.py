#!/usr/bin/env python3
"""
Zero-Overhead S-Zero Plus & Astra/Alstra/SalathanieAI Tri-Avatar Cockpit HUD.
"""

HUD_HTML = b"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASTRA // ALSTRA // SALATHANIE-AI COCKPIT HUD</title>
<style>
  :root{--bg:#060b12;--panel:#0d1624;--border:#1d3557;--cyan:#38bdf8;--green:#22c55e;--amber:#f59e0b;--purple:#a855f7;--text:#e2e8f0}
  *{box-sizing:border-box;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  body{margin:0;background:var(--bg);color:var(--text);padding:14px}
  .hdr{display:flex;justify-content:space-between;align-items:center;border:1px solid var(--border);background:var(--panel);padding:12px 16px;border-radius:8px;margin-bottom:12px}
  .hdr h1{margin:0;font-size:15px;color:var(--cyan);letter-spacing:1px}
  .badge{padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;background:#132a1c;color:var(--green);border:1px solid var(--green)}
  .badge.warn{background:#2d1a12;color:var(--amber);border-color:var(--amber)}
  .avatars{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}
  .av{background:var(--panel);border:1px solid var(--purple);border-radius:8px;padding:10px;cursor:pointer;position:relative}
  .av.active{box-shadow:0 0 14px rgba(168,85,247,.35);background:#151129}
  .av-top{display:flex;align-items:center;gap:8px;margin-bottom:4px}
  .orb{width:14px;height:14px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#e879f9,#6b21a8);box-shadow:0 0 8px #c084fc}
  .av-name{font-weight:700;font-size:13px;color:#fff}
  .av-role{font-size:11px;color:#cbd5e1}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:12px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px}
  .lbl{font-size:11px;color:#94a3b8;text-transform:uppercase;margin-bottom:4px}
  .val{font-size:22px;font-weight:700;color:#fff}
  .unit{font-size:12px;color:var(--cyan)}
  .ctrls{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}
  button{background:#0f2942;color:var(--cyan);border:1px solid var(--cyan);padding:12px 8px;border-radius:6px;font-weight:700;cursor:pointer;font-size:13px}
  button:active{transform:scale(.98);background:var(--cyan);color:#060b12}
  .sub{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;font-size:12px;line-height:1.5;color:#cbd5e1}
  .poly{display:flex;gap:8px;margin-top:10px}
  input{flex:1;background:#060b12;border:1px solid var(--border);color:#fff;padding:8px 10px;border-radius:6px;font-size:12px}
</style>
</head>
<body>
<div class="hdr">
  <h1>ASTRA // ALSTRA // SALATHANIE-AI HUD</h1>
  <span id="statusBadge" class="badge">SYNCING...</span>
</div>
<div class="avatars" id="avatarBar">
  <div class="av active" onclick="selectAvatar('ASTRA',this)"><div class="av-top"><span class="orb"></span><span class="av-name">ASTRA</span></div><div class="av-role">Flight & Telemetry (:8101)</div></div>
  <div class="av" onclick="selectAvatar('ALSTRA',this)"><div class="av-top"><span class="orb"></span><span class="av-name">ALSTRA</span></div><div class="av-role">Tactical Co-Pilot (:8102)</div></div>
  <div class="av" onclick="selectAvatar('SALATHANIE-AI',this)"><div class="av-top"><span class="orb"></span><span class="av-name">SALATHANIE-AI</span></div><div class="av-role">Command Sovereign (:8102)</div></div>
</div>
<div class="grid">
  <div class="card"><div class="lbl">Altitude</div><div class="val"><span id="alt">--</span> <span class="unit">FT</span></div></div>
  <div class="card"><div class="lbl">Airspeed</div><div class="val"><span id="spd">--</span> <span class="unit">KTS</span></div></div>
  <div class="card"><div class="lbl">Battery</div><div class="val"><span id="bat">--</span> <span class="unit">%</span></div></div>
  <div class="card"><div class="lbl">Rotor RPM</div><div class="val"><span id="rpm">--</span> <span class="unit">RPM</span></div></div>
</div>
<div class="ctrls">
  <button onclick="stepFlight('CLIMB',0.85)">CLIMB</button>
  <button onclick="stepFlight('CRUISE',0.70)">CRUISE</button>
  <button onclick="stepFlight('HOVER',0.60)">HOVER</button>
  <button onclick="stepFlight('LAND',0.35)">LAND</button>
</div>
<div class="sub">
  <div><strong>Tri-Avatar & Neuro Merkle:</strong> <span id="merkle">--</span></div>
  <div><strong>Predictive Kernel (:8154):</strong> <span id="pred">--</span></div>
  <div><strong>Telemetry Spine (:8159):</strong> <span id="spine">--</span></div>
  <div><strong>Manifest Contract:</strong> <span id="man">--</span></div>
  <div class="poly">
    <input id="polyIn" placeholder="Speak / command active avatar in any language..." />
    <button style="padding:8px 14px" onclick="testPoly()">SEND</button>
  </div>
  <div id="polyOut" style="margin-top:6px;color:var(--cyan)"></div>
</div>
<script>
let activeAvatar = 'ASTRA';
function selectAvatar(name, el){
  activeAvatar = name;
  document.querySelectorAll('.av').forEach(x=>x.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('polyOut').textContent = `Active Avatar switched to ${name} (Polyglot All-Languages Ready)`;
}
async function refreshHUD(){
  try{
    const [hudR, manR, avR] = await Promise.all([
      fetch('/api/cockpit/telemetry'),
      fetch('/api/manifest/telemetry'),
      fetch('/v1/neuro/merkle')
    ]);
    const hud = await hudR.json();
    const man = await manR.json();
    const av = await avR.json();
    const lat = (hud.spine && hud.spine.latest) || {};
    const pr = hud.predictive || {};
    document.getElementById('alt').textContent = lat.altitude_ft ?? '--';
    document.getElementById('spd').textContent = lat.airspeed_kts ?? '--';
    document.getElementById('bat').textContent = lat.battery_pct ?? '--';
    document.getElementById('rpm').textContent = lat.rotor_rpm ?? '--';
    const st = pr.status || 'NOMINAL';
    const b = document.getElementById('statusBadge');
    b.textContent = `${activeAvatar} // ${st}`;
    b.className = st === 'NOMINAL' ? 'badge' : 'badge warn';
    document.getElementById('merkle').textContent = `ONLINE (3/3 Avatars) | root=${(av.merkle_root||'').slice(0,16)}...`;
    document.getElementById('pred').textContent = `${st} | samples=${pr.samples||0} | drop=${pr.window_battery_drop_pct||0}% | rpm_spread=${pr.rotor_rpm_spread||0}`;
    document.getElementById('spine').textContent = `frame #${lat.frame_id||0} / cap ${hud.spine?.ring_cap||500} (${lat.craft_id||'S-ZERO-PLUS-01'})`;
    document.getElementById('man').textContent = `${man.manifest_version||'r7'} | ${man.online||0}/${man.registered||13} nodes online`;
  }catch(e){
    document.getElementById('statusBadge').textContent = 'LINK RETRY';
  }
}
async function stepFlight(mode, throttle){
  await fetch('/api/evtol/szero-plus',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,throttle,dt:1.5})});
  refreshHUD();
}
async function testPoly(){
  const prompt = document.getElementById('polyIn').value || 'Status check';
  const r = await fetch('/api/polyglot/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,avatar:activeAvatar})});
  const d = await r.json();
  document.getElementById('polyOut').textContent = `[${activeAvatar}] lang=${d.polyglot?.lang} (${d.polyglot?.source}) | all_languages=true`;
}
refreshHUD();
setInterval(refreshHUD, 2500);
</script>
</body>
</html>
"""
