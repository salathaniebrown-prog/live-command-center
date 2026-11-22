#!/usr/bin/env python3
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

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>ASTRA // ALSTRA 3D JET HUD</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:monospace;user-select:none}
html,body{width:100vw;height:100vh;overflow:hidden;background:#030812;color:#7ef9ff;touch-action:none}
canvas{position:fixed;inset:0;width:100vw;height:100vh}
#hud{position:fixed;inset:0;display:grid;grid-template-columns:235px 1fr 245px;grid-template-rows:36px 1fr 34px;gap:5px;padding:5px;pointer-events:none}
.p{background:rgba(5,16,32,0.85);border:1px solid #0ff5;padding:6px;pointer-events:auto;overflow:hidden}
#top,#bot{grid-column:1/4;display:flex;align-items:center;justify-content:space-between;padding:0 10px;font-size:11px}
h3{font-size:9px;color:#00f0ff;border-bottom:1px solid #0ff3;padding-bottom:2px;margin:4px 0 3px;text-transform:uppercase}
.kv{display:flex;justify-content:space-between;font-size:10px;margin:2px 0}
.v{color:#fff;font-weight:bold}
.g{display:grid;grid-template-columns:1fr 1fr;gap:3px}
button{background:#071d36;color:#7ef9ff;border:1px solid #0ff6;padding:4px;font-size:9px;cursor:pointer}
button.on{background:#00f0ff;color:#020813;font-weight:bold}
button.pod-on{background:#39ff14;color:#020813;font-weight:bold;border-color:#39ff14}
.n{font-size:9px;padding:2px 4px;margin:2px 0;border-left:2px solid #ffb703;background:#081c3488}
input[type=range]{width:100%;accent-color:#00f0ff}
a.back{color:#39ff14;text-decoration:none;border:1px solid #39ff14;padding:2px 6px;font-size:10px}
</style></head><body>
<canvas id="gl"></canvas>
<div id="hud">
  <div id="top" class="p"><a class="back" href="/">PILOT</a><b>ASTRA // ALSTRA 3D JET</b><span id="gb">GEN: --</span><span id="mb" style="color:#39ff14">MODE: AUTO</span></div>
  <div class="p">
    <h3>View &amp; Modes</h3>
    <div class="g"><button id="vE" class="on" onclick="setV('EXT')">EXTERIOR</button><button id="vI" onclick="setV('INT')">INTERIOR</button></div>
    <div class="g" style="margin-top:3px">
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
    <button style="width:100%;margin-top:2px" onclick="resetStick()">CENTER STICK [R]</button>
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
    <h3>Self-Coding</h3>
    <div id="mr" style="font-size:9px;color:#aef">--</div>
  </div>
  <div id="bot" class="p"><span>DRAG: PITCH/ROLL | WASD/ARROWS | +/- THRUST</span><span>ASTRA 3D HUD</span></div>
</div>
<script>
const c=document.getElementById('gl'),x=c.getContext('2d');
let V='EXT',t=0,S={turb:0.4,thr:0.72},pods=[true,true,true,true];
let pilot={pitch:0,roll:0,manual:false,drag:false,sx:0,sy:0},keys={};
function rz(){c.width=innerWidth;c.height=innerHeight;}
addEventListener('resize',rz);rz();
function setV(v){V=v;vE.classList.toggle('on',v==='EXT');vI.classList.toggle('on',v==='INT');}
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
function rotPt(pt,p,r,y,cx,cy,z){
  const X=pt[0],Y=pt[1],Z=pt[2];
  const y1=Y*Math.cos(p)-Z*Math.sin(p),z1=Y*Math.sin(p)+Z*Math.cos(p);
  const x2=X*Math.cos(r)-y1*Math.sin(r),y2=X*Math.sin(r)+y1*Math.cos(r);
  const x3=x2*Math.cos(y)+z1*Math.sin(y),z3=-x2*Math.sin(y)+z1*Math.cos(y);
  const f=400/(400+z3);
  return [cx+x3*f*z,cy+y2*f*z];
}
const P=[
  [0,0,-165],[0,-15,-55],[-25,6,-38],[25,6,-38],
  [-140,14,72],[140,14,72],[-32,4,110],[32,4,110],
  [-44,-52,105],[44,-52,105],[0,-4,-12]
];
const E=[
  [0,1],[0,2],[0,3],[1,2],[1,3],[1,10],[2,10],[3,10],
  [2,4],[3,5],[4,6],[5,7],[6,7],[10,6],[10,7],[6,8],[7,9],[10,8],[10,9]
];
const PODS=[
  [-62,18,18,-62,8,18],[62,18,18,62,8,18],
  [-102,20,44,-102,11,44],[102,20,44,102,11,44]
];
function loop(){
  stepKeys();
  x.fillStyle='#030812';x.fillRect(0,0,c.width,c.height);
  const cx=c.width/2,cy=c.height/2;
  x.strokeStyle='rgba(0,240,255,0.12)';x.lineWidth=1;
  for(let rg=60;rg<=320;rg+=65){x.beginPath();x.ellipse(cx,cy+50,rg*1.4,rg*0.4,0,0,7);x.stroke();}
  const p=pilot.pitch+Math.sin(t*1.8)*(0.04+S.turb*0.14);
  const r=pilot.roll+Math.cos(t*1.3)*(0.05+S.turb*0.18);
  const y=V==='INT'?pilot.roll*0.35:t*0.35,z=V==='INT'?2.1:1.15;
  const R=P.map(pt=>rotPt(pt,p,r,y,cx,cy-10,z));
  x.strokeStyle=V==='EXT'?'#00f0ff':'rgba(0,240,255,0.35)';x.lineWidth=1.6;
  E.forEach(e=>{x.beginPath();x.moveTo(R[e[0]][0],R[e[0]][1]);x.lineTo(R[e[1]][0],R[e[1]][1]);x.stroke();});
  if(pods[0]&&V==='EXT'){
    const nose=R[0],cL=rotPt([-48,-18,-275],p,r,y,cx,cy-10,z),cR=rotPt([48,-18,-275],p,r,y,cx,cy-10,z),cB=rotPt([0,24,-275],p,r,y,cx,cy-10,z);
    x.strokeStyle='rgba(57,255,20,0.35)';x.lineWidth=1;
    [[nose,cL],[nose,cR],[nose,cB],[cL,cR],[cR,cB],[cB,cL]].forEach(s=>{x.beginPath();x.moveTo(s[0][0],s[0][1]);x.lineTo(s[1][0],s[1][1]);x.stroke();});
  }
  PODS.forEach((pd,idx)=>{
    const tip=rotPt([pd[0],pd[1],pd[2]-22],p,r,y,cx,cy-10,z);
    const tail=rotPt([pd[0],pd[1],pd[2]+26],p,r,y,cx,cy-10,z);
    const wingM=rotPt([pd[3],pd[4],pd[5]],p,r,y,cx,cy-10,z);
    const podM=rotPt([pd[0],pd[1],pd[2]],p,r,y,cx,cy-10,z);
    x.strokeStyle=pods[idx]?'#39ff14':'#ff2a6d';x.lineWidth=2;
    x.beginPath();x.moveTo(wingM[0],wingM[1]);x.lineTo(podM[0],podM[1]);x.stroke();
    x.beginPath();x.moveTo(tip[0],tip[1]);x.lineTo(tail[0],tail[1]);x.stroke();
    x.fillStyle=pods[idx]?'#39ff14':'#ff2a6d';x.beginPath();x.arc(tip[0],tip[1],4,0,7);x.fill();
  });
  [6,7].forEach(i=>{
    const nx=R[i][0],ny=R[i][1],rad=24+S.thr*36;
    const g=x.createRadialGradient(nx,ny,2,nx,ny,rad);
    g.addColorStop(0,'#fff');g.addColorStop(0.4,'#0ff');g.addColorStop(1,'transparent');
    x.fillStyle=g;x.beginPath();x.arc(nx,ny,rad,0,7);x.fill();
  });
  (V==='EXT'?[0,4,5,8,9]:[1,2,3,10]).forEach(i=>{
    x.fillStyle=V==='EXT'?'#00f0ff':'#ffb703';
    x.beginPath();x.arc(R[i][0],R[i][1],4.5,0,7);x.fill();
  });
  if(pilot.drag){
    x.strokeStyle='#39ff14';x.beginPath();x.arc(pilot.sx,pilot.sy,32,0,7);x.stroke();
    x.fillStyle='#39ff14';x.beginPath();x.arc(pilot.sx+pilot.roll*90,pilot.sy+pilot.pitch*90,10,0,7);x.fill();
  }
  t+=0.025;requestAnimationFrame(loop);
}
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
    i1.textContent=d.latest?.gen_id||'--';i2.textContent=tel.workers||'--';
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
