HUD_JS = """const c=document.getElementById('gl'),x=c.getContext('2d');
let V='EXT',t=0,S={turb:0.4,thr:0.72},pods=[true,true,true,true],pilot={pitch:0,roll:0,manual:false,drag:false,sx:0,sy:0},keys={};
function rz(){c.width=innerWidth;c.height=innerHeight}addEventListener('resize',rz);rz();
function setV(v){V=v;vE.classList.toggle('on',v=='EXT');vI.classList.toggle('on',v=='INT')}
async function setM(m){await fetch('/api/mode',{method:'POST',body:JSON.stringify({mode:m})});sync()}
async function togPod(i){pods[i]=!pods[i];renderPods();await fetch('/api/pods',{method:'POST',body:JSON.stringify({pods})}).catch(()=>{})}
function renderPods(){pods.forEach((on,i)=>document.getElementById('pod'+i).className=on?'pod-on':'');n3.textContent=pods.filter(Boolean).length+'/4 ONLINE'}
function setThr(v){S.thr=v/100;pThr.textContent=v+'%';pushPilot()}
function resetStick(){pilot.pitch=0;pilot.roll=0;pilot.manual=false;pushPilot()}
let pushT=0;
function pushPilot(){
  pAtt.textContent=`${pilot.pitch.toFixed(2)} / ${pilot.roll.toFixed(2)}`;
  if(Date.now()-pushT<180)return;pushT=Date.now();
  fetch('/api/pilot',{method:'POST',body:JSON.stringify({pitch:pilot.pitch,roll:pilot.roll,thrust:S.thr})}).catch(()=>{});
}
c.addEventListener('pointerdown',e=>{pilot.drag=true;pilot.manual=true;pilot.sx=e.clientX;pilot.sy=e.clientY});
addEventListener('pointermove',e=>{if(!pilot.drag)return;pilot.roll=Math.max(-1.2,Math.min(1.2,(e.clientX-pilot.sx)/110));pilot.pitch=Math.max(-0.9,Math.min(0.9,(e.clientY-pilot.sy)/110));pushPilot()});
addEventListener('pointerup',()=>{pilot.drag=false});
addEventListener('keydown',e=>{keys[e.key.toLowerCase()]=true;if(e.key.toLowerCase()=='r')resetStick()});
addEventListener('keyup',e=>{keys[e.key.toLowerCase()]=false});
function stepKeys(){
  let ch=false;
  if(keys['w']||keys['arrowup']){pilot.pitch=Math.max(-0.9,pilot.pitch-0.03);pilot.manual=true;ch=true}
  if(keys['s']||keys['arrowdown']){pilot.pitch=Math.min(0.9,pilot.pitch+0.03);pilot.manual=true;ch=true}
  if(keys['a']||keys['arrowleft']){pilot.roll=Math.max(-1.2,pilot.roll-0.04);pilot.manual=true;ch=true}
  if(keys['d']||keys['arrowright']){pilot.roll=Math.min(1.2,pilot.roll+0.04);pilot.manual=true;ch=true}
  if(keys['=']||keys['+']||keys['shift']){thrSlider.value=Math.min(100,+thrSlider.value+2);setThr(thrSlider.value)}
  if(keys['-']||keys['_']||keys['control']){thrSlider.value=Math.max(10,+thrSlider.value-2);setThr(thrSlider.value)}
  if(!pilot.drag&&!ch&&pilot.manual){pilot.pitch*=0.94;pilot.roll*=0.94;if(Math.abs(pilot.pitch)<0.01&&Math.abs(pilot.roll)<0.01)pilot.manual=false}
  if(ch)pushPilot();
}
function rotPt([X,Y,Z],p,r,y,cx,cy,z){
  let y1=Y*Math.cos(p)-Z*Math.sin(p),z1=Y*Math.sin(p)+Z*Math.cos(p);
  let x2=X*Math.cos(r)-y1*Math.sin(r),y2=X*Math.sin(r)+y1*Math.cos(r);
  let x3=x2*Math.cos(y)+z1*Math.sin(y),z3=-x2*Math.sin(y)+z1*Math.cos(y);
  const f=400/(400+z3);return [cx+x3*f*z,cy+y2*f*z];
}
function loop(){
  stepKeys();x.fillStyle='#030812';x.fillRect(0,0,c.width,c.height);
  const cx=c.width/2,cy=c.height/2;x.strokeStyle='rgba(0,240,255,0.12)';
  for(let r=60;r<=320;r+=65){x.beginPath();x.ellipse(cx,cy+50,r*1.4,r*0.4,0,0,7);x.stroke()}
  const p=pilot.pitch+Math.sin(t*1.8)*(0.04+S.turb*0.14),r=pilot.roll+Math.cos(t*1.3)*(0.05+S.turb*0.18),y=V=='INT'?pilot.roll*0.35:t*0.35,z=V=='INT'?2.1:1.15;
  const P=[[0,0,-165],[0,-15,-55],[-25,6,-38],[25,6,-38],[-140,14,72],,[-32,4,110],,[-44,-52,105],[44,-52,105],[0,-4,-12]];
  const E=[,,,,,,,,,,,,,,,];
  const R=P.map(pt=>rotPt(pt,p,r,y,cx,cy-10,z));
  x.strokeStyle=V=='EXT'?'#00f0ff':'rgba(0,240,255,0.35)';x.lineWidth=1.6;
  E.forEach(([a,b])=>{x.beginPath();x.moveTo(R[a],R[a]);x.lineTo(R[b],R[b]);x.stroke()});
  if(pods&&V=='EXT'){
    const nose=R,cL=rotPt([-48,-18,-275],p,r,y,cx,cy-10,z),cR=rotPt([48,-18,-275],p,r,y,cx,cy-10,z),cB=rotPt([0,24,-275],p,r,y,cx,cy-10,z);
    x.strokeStyle='rgba(57,255,20,0.35)';x.lineWidth=1;
    [[nose,cL],[nose,cR],[nose,cB],[cL,cR],[cR,cB],[cB,cL]].forEach(([u,w])=>{x.beginPath();x.moveTo(u,u);x.lineTo(w,w);x.stroke()});
  }
  const podDefs=[[-62,18,18,-62,8,18],,[-102,20,44,-102,11,44],];
  podDefs.forEach((pd,idx)=>{
    const tip=rotPt([pd,pd,pd-22],p,r,y,cx,cy-10,z),tail=rotPt([pd,pd,pd+26],p,r,y,cx,cy-10,z);
    const wingM=rotPt([pd,pd,pd],p,r,y,cx,cy-10,z),podM=rotPt([pd,pd,pd],p,r,y,cx,cy-10,z);
    x.strokeStyle=pods[idx]?'#39ff14':'#ff2a6d';x.lineWidth=2;
    x.beginPath();x.moveTo(wingM,wingM);x.lineTo(podM,podM);x.stroke();
    x.beginPath();x.moveTo(tip,tip);x.lineTo(tail,tail);x.stroke();
    x.fillStyle=pods[idx]?'#39ff14':'#ff2a6d';x.beginPath();x.arc(tip,tip,4,0,7);x.fill();
  });
 .forEach(i=>{const [nx,ny]=R[i],g=x.createRadialGradient(nx,ny,2,nx,ny,24+S.thr*36);g.addColorStop(0,'#fff');g.addColorStop(0.4,'#0ff');g.addColorStop(1,'transparent');x.fillStyle=g;x.beginPath();x.arc(nx,ny,24+S.thr*36,0,7);x.fill()});
  (V=='EXT'?:).forEach(i=>{const [px,py]=R[i];x.fillStyle=V=='EXT'?'#00f0ff':'#ffb703';x.beginPath();x.arc(px,py,4.5,0,7);x.fill()});
  if(pilot.drag){x.strokeStyle='#39ff14';x.beginPath();x.arc(pilot.sx,pilot.sy,32,0,7);x.stroke();x.beginPath();x.arc(pilot.sx+pilot.roll*90,pilot.sy+pilot.pitch*90,10,0,7);x.fillStyle='#39ff14';x.fill()}
  t+=0.025;requestAnimationFrame(loop)
}
async function sync(){
  try{const d=await(await fetch('/api/hud')).json(),g=d.state?.genome||{},tel=d.latest?.telemetry||{},h=tel.host||{},m=d.state?.mode||'AUTONOMOUS-MUTATE';
  if(Array.isArray(d.state?.pods)&&d.state.pods.length===4){pods=d.state.pods;renderPods()}
  S.turb=tel.turbulence??0.4;if(!pilot.manual&&g.thrust_trim){S.thr=g.thrust_trim;thrSlider.value=Math.round(S.thr*100);pThr.textContent=thrSlider.value+'%'}
  gb.textContent=`GEN: ${d.latest?.gen_id||'--'} | FIT: ${d.latest?.new_fitness||'--'}`;mb.textContent='MODE: '+m;
  ['AUTONOMOUS-MUTATE','TURBULENCE-LOCK','THERMAL-DERATE','CRUISE-VECTOR'].forEach((k,i)=>document.getElementById('m'+i).classList.toggle('on',k==m));
  gp1.textContent=g.kp_pitch??'--';gp2.textContent=g.kd_pitch??'--';gr1.textContent=g.kp_roll??'--';gr2.textContent=g.kd_roll??'--';gt1.textContent=g.thrust_trim??'--';
  i1.textContent=d.latest?.gen_id||'--';i2.textContent=tel.workers||'--';i3.textContent=(h.ram_pct||'--')+'% RAM';
  mr.textContent=d.latest?.reason||'--'}catch(e){}
}
loop();sync();setInterval(sync,2000);"""
