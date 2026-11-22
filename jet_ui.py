HUD_CSS = """*{box-sizing:border-box;margin:0;padding:0;font-family:monospace;user-select:none}
html,body{width:100vw;height:100vh;overflow:hidden;background:#030812;color:#7ef9ff;touch-action:none}
canvas{position:fixed;inset:0;width:100vw;height:100vh}
#hud{position:fixed;inset:0;display:grid;grid-template-columns:245px 1fr 255px;grid-template-rows:36px 1fr 34px;gap:5px;padding:5px;pointer-events:none}
.p{background:rgba(5,16,32,0.85);border:1px solid #0ff5;padding:6px;pointer-events:auto;overflow:hidden}
#top,#bot{grid-column:1/4;display:flex;align-items:center;justify-content:space-between;padding:0 10px;font-size:11px}
h3{font-size:9px;color:#00f0ff;border-bottom:1px solid #0ff3;padding-bottom:2px;margin:4px 0 3px;text-transform:uppercase}
.kv{display:flex;justify-content:space-between;font-size:10px;margin:2px 0}.v{color:#fff;font-weight:bold}
.g{display:grid;grid-template-columns:1fr 1fr;gap:3px}
button{background:#071d36;color:#7ef9ff;border:1px solid #0ff6;padding:4px;font-size:9px;cursor:pointer}
button.on{background:#00f0ff;color:#020813;font-weight:bold}
button.pod-on{background:#39ff14;color:#020813;font-weight:bold;border-color:#39ff14}
.n{font-size:9px;padding:2px 4px;margin:2px 0;border-left:2px solid #39ff14;background:#081c3488}
input[type=range]{width:100%;accent-color:#00f0ff}"""

HUD_BODY = """<canvas id="gl"></canvas><div id="hud">
<div id="top" class="p"><b>ASTRA // ALSTRA 3D JET</b><span id="gb">GEN: --</span><span id="mb" style="color:#39ff14">MODE: AUTO</span></div>
<div class="p"><h3>View & Flight Modes</h3>
<div class="g"><button id="vE" class="on" onclick="setV('EXT')">EXTERIOR</button><button id="vI" onclick="setV('INT')">INTERIOR</button></div>
<div class="g" style="margin-top:3px">
<button id="m0" class="on" onclick="setM('AUTONOMOUS-MUTATE')">AUTO-MUTATE</button>
<button id="m1" onclick="setM('TURBULENCE-LOCK')">TURB-LOCK</button>
<button id="m2" onclick="setM('THERMAL-DERATE')">THERM-DERATE</button>
<button id="m3" onclick="setM('CRUISE-VECTOR')">CRUISE-VEC</button></div>
<h3>3D Weapon / Sensor Pods</h3>
<div class="g">
<button id="pod0" class="pod-on" onclick="togPod(0)">[L1] SAR-LIDAR</button>
<button id="pod1" class="pod-on" onclick="togPod(1)">[R1] RF-MESH</button>
<button id="pod2" class="pod-on" onclick="togPod(2)">[L2] OPTIC-IR</button>
<button id="pod3" class="pod-on" onclick="togPod(3)">[R2] AUX-POD</button></div>
<h3>Touch / Keyboard Flight</h3>
<div class="kv"><span>THRUST [+/-]</span><span id="pThr" class="v">72%</span></div>
<input id="thrSlider" type="range" min="10" max="100" value="72" oninput="setThr(this.value)">
<div class="kv"><span>PITCH / ROLL</span><span id="pAtt" class="v">0.00 / 0.00</span></div>
<button style="width:100%;margin-top:2px" onclick="resetStick()">CENTER STICK [R]</button>
<div class="n">[EXT] Active Pods: <span id="n3" class="v">4/4 ONLINE</span></div></div>
<div></div>
<div class="p"><h3>Control Genome</h3>
<div class="kv"><span>kp_pitch</span><span id="gp1" class="v">--</span></div>
<div class="kv"><span>kd_pitch</span><span id="gp2" class="v">--</span></div>
<div class="kv"><span>kp_roll</span><span id="gr1" class="v">--</span></div>
<div class="kv"><span>kd_roll</span><span id="gr2" class="v">--</span></div>
<div class="kv"><span>thrust_trim</span><span id="gt1" class="v">--</span></div>
<h3>Interior Core & Compute</h3>
<div class="n" style="border-color:#ffb703">[INT-01] Genome: <span id="i1" class="v">--</span></div>
<div class="n" style="border-color:#ffb703">[INT-02] Cluster: <span id="i2" class="v">--</span></div>
<div class="n" style="border-color:#ffb703">[INT-03] Host RAM: <span id="i3" class="v">--</span></div>
<h3>Self-Coding Status</h3><div id="mr" style="font-size:9px;color:#aef">--</div></div>
<div id="bot" class="p"><span>DRAG CANVAS: PITCH/ROLL | WASD/ARROWS | +/- THRUST</span><span>PORT 8095</span></div></div>"""
