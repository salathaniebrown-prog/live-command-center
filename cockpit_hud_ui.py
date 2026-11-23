#!/usr/bin/env python3
"""
Zero-Overhead S-Zero Plus & Astra/Alstra Flying Car Live Cockpit HUD (HTML/JS).
Polls relative /api/cockpit/telemetry & /api/manifest/telemetry and dispatches
flight mode commands to /api/evtol/szero-plus with 0 extra daemon RAM.
"""

HUD_HTML = b"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASTRA // ALSTRA // S-ZERO PLUS COCKPIT HUD</title>
<style>
  :root{--bg:#060b12;--panel:#0d1624;--border:#1d3557;--cyan:#38bdf8;--green:#22c55e;--amber:#f59e0b;--red:#ef4444;--text:#e2e8f0}
  *{box-sizing:border-box;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  body{margin:0;background:var(--bg);color:var(--text);padding:14px}
  .hdr{display:flex;justify-content:space-between;align-items:center;border:1px solid var(--border);background:var(--panel);padding:12px 16px;border-radius:8px;margin-bottom:12px}
  .hdr h1{margin:0;font-size:15px;color:var(--cyan);letter-spacing:1px}
  .badge{padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;background:#132a1c;color:var(--green);border:1px solid var(--green)}
  .badge.warn{background:#2d1a12;color:var(--amber);border-color:var(--amber)}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:12px}
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
  <h1>ASTRA // ALSTRA // S-ZERO-PLUS-01 HUD</h1>
  <span id="statusBadge" class="badge">SYNCING...</span>
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
  <div><strong>Predictive Kernel (:8154):</strong> <span id="pred">--</span></div>
  <div><strong>Telemetry Spine (:8159):</strong> <span id="spine">--</span></div>
  <div><strong>Manifest Contract:</strong> <span id="man">--</span></div>
  <div class="poly">
    <input id="polyIn" placeholder="Polyglot command / prompt in any language..." />
    <button style="padding:8px 14px" onclick="testPoly()">POLYGLOT</button>
  </div>
  <div id="polyOut" style="margin-top:6px;color:var(--cyan)"></div>
</div>
<script>
async function refreshHUD(){
  try{
    const [hudR, manR] = await Promise.all([
      fetch('/api/cockpit/telemetry'),
      fetch('/api/manifest/telemetry')
    ]);
    const hud = await hudR.json();
    const man = await manR.json();
    const lat = (hud.spine && hud.spine.latest) || {};
    const pr = hud.predictive || {};
    document.getElementById('alt').textContent = lat.altitude_ft ?? '--';
    document.getElementById('spd').textContent = lat.airspeed_kts ?? '--';
    document.getElementById('bat').textContent = lat.battery_pct ?? '--';
    document.getElementById('rpm').textContent = lat.rotor_rpm ?? '--';
    const st = pr.status || 'NOMINAL';
    const b = document.getElementById('statusBadge');
    b.textContent = st;
    b.className = st === 'NOMINAL' ? 'badge' : 'badge warn';
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
  const r = await fetch('/api/polyglot/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt})});
  const d = await r.json();
  document.getElementById('polyOut').textContent = `Detected lang=${d.polyglot?.lang} (${d.polyglot?.source}) | all_languages=true`;
}
refreshHUD();
setInterval(refreshHUD, 2500);
</script>
</body>
</html>
"""
