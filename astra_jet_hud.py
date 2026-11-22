#!/usr/bin/env python3
"""
SalathanieAI — Upgraded Astra + Alstra 3D Core Jet HUD
Depth-sorted shaded stealth hull, fusion core interior, 4 core themes,
live genome sync, and instant 2K PNG + 3D .OBJ export.
"""
import http.server
import json
import socket
import socketserver
import time
from pathlib import Path

JET_DIR = Path.home() / "live-command-center" / "builds" / "astra_jet"
TELEM_FILE = JET_DIR / "alstra_jet_telemetry.jsonl"
STATE_FILE = JET_DIR / "alstra_jet_state.json"
JET_DIR.mkdir(parents=True, exist_ok=True)

HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>SALATHANIE AI // ASTRA + ALSTRA 3D CORE JET</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:monospace;user-select:none}
html,body{width:100vw;height:100vh;overflow:hidden;background:#02060f;color:#7ef9ff;touch-action:none}
canvas{position:fixed;inset:0;width:100vw;height:100vh}
#hud{position:fixed;inset:0;display:grid;grid-template-columns:235px 1fr 245px;grid-template-rows:38px 1fr 34px;gap:5px;padding:5px;pointer-events:none}
.p{background:rgba(4,12,26,0.82);border:1px solid rgba(0,240,255,0.38);padding:6px;pointer-events:auto;overflow:hidden;backdrop-filter:blur(3px)}
#top,#bot{grid-column:1/4;display:flex;align-items:center;justify-content:space-between;padding:0 10px;font-size:11px;gap:8px}
h3{font-size:9px;color:#00f0ff;border-bottom:1px solid rgba(0,240,255,0.22);padding-bottom:2px;margin:4px 0 3px;text-transform:uppercase}
.kv{display:flex;justify-content:space-between;font-size:10px;margin:2px 0}
.v{color:#fff;font-weight:bold}
.g{display:grid;grid-template-columns:1fr 1fr;gap:3px}
button{background:#071d36;color:#7ef9ff;border:1px solid rgba(0,240,255,0.45);padding:4px;font-size:9px;cursor:pointer}
button.on{background:#00f0ff;color:#020813;font-weight:bold}
button.pod-on{background:#39ff14;color:#020813;font-weight:bold;border-color:#39ff14}
button.gold{background:#f59e0b;color:#020813;font-weight:bold;border-color:#fbbf24}
.n{font-size:9px;padding:2px 4px;margin:2px 0;border-left:2px solid #ffb703;background:rgba(8,28,52,0.55)}
input[type=range]{width:100%;accent-color:#00f0ff}
a.navb{color:#39ff14;text-decoration:none;border:1px solid #39ff14;padding:2px 6px;font-size:10px}
a.navb.org{color:#fb923c;border-color:#fb923c}
</style></head><body>
<canvas id="gl"></canvas>
<div id="hud">
  <div id="top" class="p">
    <div><a class="navb" href="/">PILOT</a> <a class="navb org" href="/creative">SALATHANIE STUDIO</a></div>
    <b>ASTRA + ALSTRA = SALATHANIE AI // CORE JET</b>
    <span id="gb">GEN: --</span>
    <span id="mb" style="color:#39ff14">MODE: AUTO</span>
  </div>
  <div class="p">
    <h3>View &amp; Core Visuals</h3>
    <div class="g"><button id="vE" class="on" onclick="setV('EXT')">EXTERIOR</button><button id="vI" onclick="setV('INT')">INTERIOR CORE</button></div>
    <div class="g" style="margin-top:3px">
      <button id="th0" class="on" onclick="setTheme('STEALTH')">STEALTH</button>
      <button id="th1" onclick="setTheme('GOLD')">GOLD CORE</button>
      <button id="th2" onclick="setTheme('PLASMA')">PLASMA</button>
      <button id="th3" onclick="setTheme('WIRE')">WIREFRAME</button>
    </div>
    <h3>Autopilot Modes</h3>
    <div class="g">
      <button id="m0" class="on" onclick="setM('AUTONOMOUS-MUTATE')">AUTO-MUTATE</button>
      <button id="m1" onclick="setM('TURBULENCE-LOCK')">TURB-LOCK</button>
      <button id="m2" onclick="setM('THERMAL-DERATE')">THERM-DERATE</button>
      <button id="m3" onclick="setM('CRUISE-VECTOR')">CRUISE-VEC</button>
    </div>
    <h3>3D Weapon / Sensor Pods</h3>
    <div class="g">
      <button id="pod0" class="pod-on" onclick="togPod(0)">[L1] SAR-LIDAR</button>
      <button id="pod1" class="pod-on" onclick="togPod(1)">[R1] RF-MESH</button>
      <button id="pod2" class="pod-on" onclick="togPod(2)">[L2] OPTIC-IR</button>
      <button id="pod3" class="pod-on" onclick="togPod(3)">[R2] AUX-POD</button>
    </div>
    <h3>Touch / Keyboard Flight</h3>
    <div class="kv"><span>THRUST [+/-]</span><span id="pThr" class="v">72%</span></div>
    <input id="thrSlider" type="range" min="10" max="100" value="72" oninput="setThr(this.value)">
    <div class="kv"><span>PITCH / ROLL</span><span id="pAtt" class="v">0.00 / 0.00</span></div>
    <div class="g" style="margin-top:3px">
      <button onclick="resetStick()">CENTER [R]</button>
      <button class="gold" onclick="snapCorePNG()">SNAP CORE PNG</button>
    </div>
    <div class="n" style="border-color:#39ff14">[EXT] Pods: <span id="n3" class="v">4/4 ONLINE</span></div>
  </div>
  <div></div>
  <div class="p">
    <h3>Control Genome</h3>
    <div class="kv"><span>kp_pitch</span><span id="gp1" class="v">--</span></div>
    <div class="kv"><span>kd_pitch</span><span id="gp2" class="v">--</span></div>
    <div class="kv"><span>kp_roll</span><span id="gr1" class="v">--</span></div>
    <div class="kv"><span>kd_roll</span><span id="gr2" class="v">--</span></div>
    <div class="kv"><span>thrust_trim</span><span id="gt1" class="v">--</span></div>
    <h3>Interior Core</h3>
    <div class="n">[INT-01] Genome: <span id="i1" class="v">--</span></div>
    <div class="n">[INT-02] Cluster: <span id="i2" class="v">--</span></div>
    <div class="n">[INT-03] RAM: <span id="i3" class="v">--</span></div>
    <h3>Core Asset Export</h3>
    <div class="g">
      <button onclick="exportOBJ()">EXPORT .OBJ</button>
      <button onclick="window.location='/creative'">OPEN STUDIO</button>
    </div>
    <h3>Self-Coding</h3>
    <div id="mr" style="font-size:9px;color:#aef">--</div>
  </div>
  <div id="bot" class="p"><span>DRAG: PITCH/ROLL | WASD/ARROWS | +/- THRUST</span><span>SALATHANIE AI // ASTRA+ALSTRA CORE</span></div>
</div>
<script>
const c=document.getElementById('gl'),x=c.getContext('2d');
let V='EXT',THEME='STEALTH',t=0,S={turb:0.4,thr:0.72},pods=[true,true,true,true];
let pilot={pitch:0,roll:0,manual:false,drag:false,sx:0,sy:0},keys={};
const THEMES={
  STEALTH:{hull:[16,32,58],edge:'#00f0ff',canopy:'#38bdf8',glow:'#00f0ff',core:'#39ff14'},
  GOLD:{hull:[58,42,14],edge:'#fbbf24',canopy:'#fef08a',glow:'#f59e0b',core:'#facc15'},
  PLASMA:{hull:[38,14,64],edge:'#e879f9',canopy:'#67e8f9',glow:'#c084fc',core:'#22d3ee'},
  WIRE:{hull:null,edge:'#00f0ff',canopy:'#38bdf8',glow:'#00f0ff',core:'#ffb703'}
};
function rz(){c.width=innerWidth;c.height=innerHeight;}
addEventListener('resize',rz);rz();
function setV(v){V=v;vE.classList.toggle('on',v==='EXT');vI.classList.toggle('on',v==='INT');}
function setTheme(th){
  THEME=th;
  ['STEALTH','GOLD','PLASMA','WIRE'].forEach((k,i)=>{document.getElementById('th'+i).classList.toggle('on',k===th);});
}
async function setM(m){await fetch('/api/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:m})});sync();}
async function togPod(i){pods[i]=!pods[i];renderPods();await fetch('/api/pods',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pods})}).catch(()=>{});}
function renderPods(){pods.forEach((on,i)=>{document.getElementById('pod'+i).className=on?'pod-on':'';});n3.textContent=pods.filter(Boolean).length+'/4 ONLINE';}
function setThr(v){S.thr=v/100;pThr.textContent=v+'%';pushPilot();}
function resetStick(){pilot.pitch=0;pilot.roll=0;pilot.manual=false;pushPilot();}
let pushT=0;
function pushPilot(){
  pAtt.textContent=pilot.pitch.toFixed(2)+' / '+pilot.roll.toFixed(2);
  if(Date.now()-pushT<180)return;
  pushT=Date.now();
  fetch('/api/pilot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pitch:pilot.pitch,roll:pilot.roll,thrust:S.thr})}).catch(()=>{});
}
c.addEventListener('pointerdown',e=>{pilot.drag=true;pilot.manual=true;pilot.sx=e.clientX;pilot.sy=e.clientY;});
addEventListener('pointermove',e=>{
  if(!pilot.drag)return;
  pilot.roll=Math.max(-1.2,Math.min(1.2,(e.clientX-pilot.sx)/110));
  pilot.pitch=Math.max(-0.9,Math.min(0.9,(e.clientY-pilot.sy)/110));
  pushPilot();
});
addEventListener('pointerup',()=>{pilot.drag=false;});
addEventListener('keydown',e=>{keys[e.key.toLowerCase()]=true;if(e.key.toLowerCase()==='r')resetStick();});
addEventListener('keyup',e=>{keys[e.key.toLowerCase()]=false;});
function stepKeys(){
  let ch=false;
  if(keys['w']||keys['arrowup']){pilot.pitch=Math.max(-0.9,pilot.pitch-0.03);pilot.manual=true;ch=true;}
  if(keys['s']||keys['arrowdown']){pilot.pitch=Math.min(0.9,pilot.pitch+0.03);pilot.manual=true;ch=true;}
  if(keys['a']||keys['arrowleft']){pilot.roll=Math.max(-1.2,pilot.roll-0.04);pilot.manual=true;ch=true;}
  if(keys['d']||keys['arrowright']){pilot.roll=Math.min(1.2,pilot.roll+0.04);pilot.manual=true;ch=true;}
  if(keys['=']||keys['+']||keys['shift']){thrSlider.value=Math.min(100,+thrSlider.value+2);setThr(thrSlider.value);}
  if(keys['-']||keys['_']||keys['control']){thrSlider.value=Math.max(10,+thrSlider.value-2);setThr(thrSlider.value);}
  if(!pilot.drag&&!ch&&pilot.manual){
    pilot.pitch*=0.94;pilot.roll*=0.94;
    if(Math.abs(pilot.pitch)<0.01&&Math.abs(pilot.roll)<0.01)pilot.manual=false;
  }
  if(ch)pushPilot();
}
function rot3D(pt,p,r,y){
  const X=pt[0],Y=pt[1],Z=pt[2];
  const y1=Y*Math.cos(p)-Z*Math.sin(p),z1=Y*Math.sin(p)+Z*Math.cos(p);
  const x2=X*Math.cos(r)-y1*Math.sin(r),y2=X*Math.sin(r)+y1*Math.cos(r);
  const x3=x2*Math.cos(y)+z1*Math.sin(y),z3=-x2*Math.sin(y)+z1*Math.cos(y);
  return [x3,y2,z3];
}
function proj(v,cx,cy,z){const f=460/(460+v[2]);return [cx+v[0]*f*z,cy+v[1]*f*z,v[2]];}

// Upgraded SalathanieAI Astra+Alstra Multi-Panel Stealth Jet Geometry (16 vertices)
const P=[
  [0,2,-185],      // 0: Sharp needle nose
  [0,-22,-78],     // 1: Canopy apex
  [-26,4,-52],     // 2: Left intake chine
  [26,4,-52],      // 3: Right intake chine
  [0,16,-58],      // 4: Lower keel front
  [-155,14,76],    // 5: Left stealth wingtip
  [155,14,76],     // 6: Right stealth wingtip
  [-42,4,116],     // 7: Left nozzle center
  [42,4,116],      // 8: Right nozzle center
  [-56,-56,112],   // 9: Left canted tailfin tip
  [56,-56,112],    // 10: Right canted tailfin tip
  [0,-14,12],      // 11: Dorsal spine ridge
  [0,18,74],       // 12: Belly aft keel
  [-66,10,104],    // 13: Left trailing flap corner
  [66,10,104],     // 14: Right trailing flap corner
  [0,-4,-14]       // 15: Astra+Alstra Fusion Core center
];
// Faces: [indices, type]
const FACES=[
  [[0,1,2],'canopy'], [[0,3,1],'canopy'], [[1,11,2],'hull'], [[1,3,11],'hull'],
  [[0,2,4],'hull'], [[0,4,3],'hull'], [[2,4,12,7],'hull'], [[3,8,12,4],'hull'],
  [[2,5,13,7],'wing'], [[3,8,14,6],'wing'], [[2,11,7],'hull'], [[3,8,11],'hull'],
  [[11,7,8],'hull'], [[7,9,11],'fin'], [[8,11,10],'fin'], [[7,12,8],'hull']
];
const PODS=[
  [-68,18,22,-68,9,22],[68,18,22,68,9,22],
  [-110,20,52,-110,12,52],[110,20,52,110,12,52]
];
const STARS=Array.from({length:70},()=>[Math.random(),Math.random(),0.4+Math.random()*1.4]);

function drawJet(){
  const th=THEMES[THEME]||THEMES.STEALTH;
  const cx=c.width/2,cy=c.height/2;
  const bg=x.createRadialGradient(cx,cy,20,cx,cy,Math.max(c.width,c.height)*0.72);
  bg.addColorStop(0,'#08172e');bg.addColorStop(1,'#02050c');
  x.fillStyle=bg;x.fillRect(0,0,c.width,c.height);

  // Subtle starfield + radar rings
  STARS.forEach(s=>{
    x.fillStyle='rgba(126,249,255,0.28)';
    x.fillRect(s[0]*c.width,((s[1]*c.height+t*18*s[2])%c.height),s[2],s[2]);
  });
  x.strokeStyle='rgba(0,240,255,0.11)';x.lineWidth=1;
  for(let rg=65;rg<=340;rg+=68){x.beginPath();x.ellipse(cx,cy+52,rg*1.45,rg*0.38,0,0,7);x.stroke();}

  const p=pilot.pitch+Math.sin(t*1.6)*(0.035+S.turb*0.12);
  const r=pilot.roll+Math.cos(t*1.2)*(0.04+S.turb*0.14);
  const y=V==='INT'?pilot.roll*0.38+Math.sin(t*0.5)*0.22:t*0.32;
  const z=V==='INT'?2.05:1.18;

  const V3=P.map(pt=>rot3D(pt,p,r,y));
  const R=V3.map(v=>proj(v,cx,cy-10,z));

  // Depth-sorted shaded panels
  const sorted=FACES.map(f=>{
    const pts=f[0].map(i=>V3[i]);
    const avgZ=pts.reduce((a,b)=>a+b[2],0)/pts.length;
    const u=[pts[1][0]-pts[0][0],pts[1][1]-pts[0][1],pts[1][2]-pts[0][2]];
    const w=[pts[2][0]-pts[0][0],pts[2][1]-pts[0][1],pts[2][2]-pts[0][2]];
    const nx=u[1]*w[2]-u[2]*w[1],ny=u[2]*w[0]-u[0]*w[2],nz=u[0]*w[1]-u[1]*w[0];
    const len=Math.hypot(nx,ny,nz)||1;
    const light=Math.max(0.25,Math.min(1.0,Math.abs((nx*0.35-ny*0.75-nz*0.55)/len)));
    return {idx:f[0],kind:f[1],avgZ,light};
  }).sort((a,b)=>b.avgZ-a.avgZ);

  sorted.forEach(f=>{
    x.beginPath();
    f.idx.forEach((vi,k)=>{if(k===0)x.moveTo(R[vi][0],R[vi][1]);else x.lineTo(R[vi][0],R[vi][1]);});
    x.closePath();
    if(th.hull){
      const alpha=V==='INT'?0.22:0.86;
      if(f.kind==='canopy'){
        x.fillStyle=V==='INT'?'rgba(56,189,248,0.18)':th.canopy;
        x.globalAlpha=V==='INT'?0.35:0.72*f.light+0.2;
        x.fill();
        x.globalAlpha=1;
      }else{
        const k=f.kind==='wing'?0.88:(f.kind==='fin'?1.12:1.0);
        const rr=Math.min(255,Math.round(th.hull[0]*(0.55+f.light*1.25)*k));
        const gg=Math.min(255,Math.round(th.hull[1]*(0.55+f.light*1.25)*k));
        const bb=Math.min(255,Math.round(th.hull[2]*(0.55+f.light*1.25)*k));
        x.fillStyle=`rgba(${rr},${gg},${bb},${alpha})`;
        x.fill();
      }
    }
    x.strokeStyle=V==='INT'?'rgba(0,240,255,0.42)':th.edge;
    x.lineWidth=f.kind==='canopy'?1.6:1.25;
    x.stroke();
  });

  // Interior Astra + Alstra Fusion Reactor Core
  if(V==='INT'||THEME==='PLASMA'){
    const core=R[15];
    const cr=18+Math.sin(t*5)*3;
    const cg=x.createRadialGradient(core[0],core[1],2,core[0],core[1],cr*2.4);
    cg.addColorStop(0,'#fff');cg.addColorStop(0.35,th.core);cg.addColorStop(1,'transparent');
    x.fillStyle=cg;x.beginPath();x.arc(core[0],core[1],cr*2.4,0,7);x.fill();
    x.strokeStyle=th.core;x.lineWidth=1.5;
    x.beginPath();x.ellipse(core[0],core[1],cr*1.5,cr*0.6,t*1.2,0,7);x.stroke();
    x.beginPath();x.ellipse(core[0],core[1],cr*1.5,cr*0.6,-t*1.2,0,7);x.stroke();
  }

  // SAR-LIDAR forward cone when L1 pod active
  if(pods[0]&&V==='EXT'){
    const nose=R[0];
    const cL=proj(rot3D([-52,-18,-295],p,r,y),cx,cy-10,z);
    const cR=proj(rot3D([52,-18,-295],p,r,y),cx,cy-10,z);
    const cB=proj(rot3D([0,24,-295],p,r,y),cx,cy-10,z);
    x.strokeStyle='rgba(57,255,20,0.34)';x.lineWidth=1;
    [[nose,cL],[nose,cR],[nose,cB],[cL,cR],[cR,cB],[cB,cL]].forEach(s=>{
      x.beginPath();x.moveTo(s[0][0],s[0][1]);x.lineTo(s[1][0],s[1][1]);x.stroke();
    });
  }

  // 4 Articulated Weapon / Sensor Pods
  PODS.forEach((pd,idx)=>{
    const tip=proj(rot3D([pd[0],pd[1],pd[2]-24],p,r,y),cx,cy-10,z);
    const tail=proj(rot3D([pd[0],pd[1],pd[2]+28],p,r,y),cx,cy-10,z);
    const wingM=proj(rot3D([pd[3],pd[4],pd[5]],p,r,y),cx,cy-10,z);
    const podM=proj(rot3D([pd[0],pd[1],pd[2]],p,r,y),cx,cy-10,z);
    x.strokeStyle=pods[idx]?'#39ff14':'#ff2a6d';x.lineWidth=2.2;
    x.beginPath();x.moveTo(wingM[0],wingM[1]);x.lineTo(podM[0],podM[1]);x.stroke();
    x.beginPath();x.moveTo(tip[0],tip[1]);x.lineTo(tail[0],tail[1]);x.stroke();
    x.fillStyle=pods[idx]?'#39ff14':'#ff2a6d';x.beginPath();x.arc(tip[0],tip[1],4,0,7);x.fill();
  });

  // Twin Afterburner Plumes with shock diamonds
  [7,8].forEach(i=>{
    const nx=R[i][0],ny=R[i][1],rad=24+S.thr*42+Math.sin(t*22+i)*3;
    const g=x.createRadialGradient(nx,ny,2,nx,ny,rad);
    g.addColorStop(0,'#ffffff');g.addColorStop(0.32,th.glow);g.addColorStop(0.68,'rgba(56,189,248,0.22)');g.addColorStop(1,'transparent');
    x.fillStyle=g;x.beginPath();x.arc(nx,ny,rad,0,7);x.fill();
  });

  if(pilot.drag){
    x.strokeStyle='#39ff14';x.lineWidth=1.5;x.beginPath();x.arc(pilot.sx,pilot.sy,32,0,7);x.stroke();
    x.fillStyle='#39ff14';x.beginPath();x.arc(pilot.sx+pilot.roll*90,pilot.sy+pilot.pitch*90,10,0,7);x.fill();
  }
}

function snapCorePNG(){
  const a=document.createElement('a');
  a.download='salathanieai_astra_alstra_jet_'+THEME.toLowerCase()+'.png';
  a.href=c.toDataURL('image/png');
  a.click();
}

function exportOBJ(){
  let obj='# SalathanieAI — Astra + Alstra Stealth Core Jet (.OBJ)\n';
  P.forEach(v=>{obj+='v '+(v[0]/50).toFixed(4)+' '+(-v[1]/50).toFixed(4)+' '+(v[2]/50).toFixed(4)+'\n';});
  FACES.forEach(f=>{obj+='f '+f[0].map(i=>i+1).join(' ')+'\n';});
  const blob=new Blob([obj],{type:'text/plain'});
  const a=document.createElement('a');
  a.download='salathanieai_astra_alstra_jet.obj';
  a.href=URL.createObjectURL(blob);
  a.click();
}

function loop(){stepKeys();drawJet();t+=0.024;requestAnimationFrame(loop);}
async function sync(){
  try{
    const d=await(await fetch('/api/hud')).json();
    const g=d.state?.genome||{},tel=d.latest?.telemetry||{},h=tel.host||{},m=d.state?.mode||'AUTONOMOUS-MUTATE';
    if(Array.isArray(d.state?.pods)&&d.state.pods.length===4){pods=d.state.pods;renderPods();}
    S.turb=tel.turbulence??0.4;
    if(!pilot.manual&&g.thrust_trim){S.thr=g.thrust_trim;thrSlider.value=Math.round(S.thr*100);pThr.textContent=thrSlider.value+'%';}
    gb.textContent='GEN: '+(d.latest?.gen_id||'--')+' | FIT: '+(d.latest?.new_fitness||'--');
    mb.textContent='MODE: '+m;
    ['AUTONOMOUS-MUTATE','TURBULENCE-LOCK','THERMAL-DERATE','CRUISE-VECTOR'].forEach((k,i)=>{document.getElementById('m'+i).classList.toggle('on',k===m);});
    gp1.textContent=g.kp_pitch??'--';gp2.textContent=g.kd_pitch??'--';
    gr1.textContent=g.kp_roll??'--';gr2.textContent=g.kd_roll??'--';
    gt1.textContent=g.thrust_trim??'--';
    i1.textContent=d.latest?.gen_id||'--';i2.textContent=tel.workers||'3/3';
    i3.textContent=(h.ram_pct||'--')+'% RAM';mr.textContent=d.latest?.reason||'--';
  }catch(e){}
}
loop();sync();setInterval(sync,2000);
</script></body></html>"""

PAGE = HTML.encode("utf-8")


def _read_json_safe(path: Path, default):
    try:
        if path.exists():
            raw = path.read_text(encoding="utf-8").strip()
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return default


def _read_last_jsonl(path: Path) -> dict:
    try:
        if path.exists():
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if lines:
                return json.loads(lines[-1])
    except Exception:
        pass
    return {}


def read_hud_payload() -> dict:
    return {
        "state": _read_json_safe(STATE_FILE, {}),
        "latest": _read_last_jsonl(TELEM_FILE),
    }


def update_hud_state(path: str, body: dict) -> dict:
    st = _read_json_safe(STATE_FILE, {})
    if path == "/api/mode":
        st["mode"] = body.get("mode", "AUTONOMOUS-MUTATE")
    elif path == "/api/pods":
        st["pods"] = body.get("pods", [True, True, True, True])
    elif path == "/api/pilot":
        st["pilot_input"] = body
        if "genome" in st and "thrust" in body:
            st["genome"]["thrust_trim"] = round(float(body["thrust"]), 4)
    STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    return {"ok": True}


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_REUSEPORT"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()


class H(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()

    def do_GET(self):
        try:
            if self.path == "/api/hud":
                self._send(200, "application/json", json.dumps(read_hud_payload()).encode("utf-8"))
            else:
                self._send(200, "text/html; charset=utf-8", PAGE)
        except Exception as e:
            self._send(500, "application/json", json.dumps({"error": str(e)}).encode("utf-8"))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, "application/json", json.dumps(update_hud_state(self.path, body)).encode("utf-8"))
        except Exception as e:
            self._send(500, "application/json", json.dumps({"error": str(e)}).encode("utf-8"))

    def _send(self, code, ct, data):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    while True:
        try:
            with Server(("0.0.0.0", 8095), H) as s:
                s.serve_forever()
        except Exception:
            time.sleep(1)
