import socketserver
socketserver.TCPServer.allow_reuse_address = True
import http.server
import socketserver
import json
import random
import datetime

# --- Data Generator for the Dashboard ---
def generate_log():
    now = datetime.datetime.now().strftime("%H:%M:%S")
    states = ["ACTIVE", "SYNCED", "SECURE", "STABLE"]
    state = random.choice(states)
    return f"[{now}] ASTRA_CORE_01 - {random.randint(1000, 9999)} active nodes. System {state}."

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Astra Command Center</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Load Leaflet.js for the map -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    
    <style>
        :root {
            --bg-color: #0a0e17;
            --panel-bg: rgba(16, 24, 39, 0.85);
            --border-color: #1f3a5f;
            --text-main: #8bb3e3;
            --text-highlight: #58a6ff;
            --text-green: #3fb950;
            --font-mono: 'Courier New', Courier, monospace;
        }
        body { 
            margin: 0; padding: 10px; background-color: var(--bg-color); color: var(--text-main); 
            font-family: var(--font-mono); height: 100vh; box-sizing: border-box;
            display: grid; grid-template-columns: 2fr 1fr; grid-template-rows: 1fr 200px; gap: 10px;
            background-image: radial-gradient(circle at center, #111827 0%, #0a0e17 100%);
        }
        
        /* Panel Styling */
        .panel { 
            background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 6px; 
            padding: 10px; position: relative; overflow: hidden;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }
        .panel-header { 
            color: var(--text-highlight); font-size: 14px; text-transform: uppercase; 
            letter-spacing: 2px; margin-bottom: 10px; border-bottom: 1px solid var(--border-color); 
            padding-bottom: 5px; 
        }

        /* 1. Map Panel */
        #map-container { grid-column: 1 / 2; grid-row: 1 / 2; padding: 0; }
        #map { width: 100%; height: 100%; border-radius: 6px; z-index: 1; }
        /* Dark filter for the map to match the theme */
        .leaflet-layer { filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%); }

        /* 2. Avatar Panel */
        #avatar-container { grid-column: 2 / 3; grid-row: 1 / 3; display: flex; flex-direction: column; }
        .avatar-display {
            flex-grow: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        /* CSS Art Avatar */
        .avatar-face {
            width: 120px; height: 120px; border-radius: 50%;
            background: linear-gradient(135deg, #1f3a5f, #0a0e17);
            border: 2px solid var(--text-highlight);
            box-shadow: 0 0 20px rgba(88, 166, 255, 0.3);
            position: relative; margin-bottom: 20px;
        }
        .avatar-eye { width: 15px; height: 15px; background: var(--text-highlight); border-radius: 50%; position: absolute; top: 40%; }
        .eye-left { left: 30%; } .eye-right { right: 30%; }
        .avatar-voice-wave { display: flex; gap: 3px; height: 30px; align-items: center; margin-bottom: 20px; }
        .bar { width: 4px; background: var(--text-green); border-radius: 2px; height: 10%; }
        
        /* 3. Logs Panel */
        #log-container { grid-column: 1 / 2; grid-row: 2 / 3; }
        #console-output { font-size: 12px; color: var(--text-green); overflow-y: auto; height: 140px; display: flex; flex-direction: column-reverse;}
        #console-output div { margin-bottom: 3px; }

        /* --- Animations --- */
        @keyframes wave {
            0%, 100% { height: 10%; }
            50% { height: 100%; }
        }
        .bar:nth-child(1) { animation: wave 1s infinite 0.1s; }
        .bar:nth-child(2) { animation: wave 1s infinite 0.3s; }
        .bar:nth-child(3) { animation: wave 1s infinite 0.0s; }
        .bar:nth-child(4) { animation: wave 1s infinite 0.4s; }
        .bar:nth-child(5) { animation: wave 1s infinite 0.2s; }

        /* Mobile adjustments */
        @media (max-width: 768px) {
            body { grid-template-columns: 1fr; grid-template-rows: 300px 1fr 150px; }
            #avatar-container { grid-column: 1 / 2; grid-row: 2 / 3; }
            #log-container { grid-row: 3 / 4; }
        }
    </style>
</head>
<body>

    <!-- 1. Map -->
    <div class="panel" id="map-container">
        <div id="map"></div>
    </div>

    <!-- 2. Avatar & Voice -->
    <div class="panel" id="avatar-container">
        <div class="panel-header">Astra Avatar [cite: 13]</div>
        <div class="avatar-display">
            <div class="avatar-face">
                <div class="avatar-eye eye-left"></div>
                <div class="avatar-eye eye-right"></div>
            </div>
            <div style="margin-bottom: 10px; color: var(--text-main);">Live Voice:</div>
            <div class="avatar-voice-wave">
                <div class="bar"></div><div class="bar"></div><div class="bar"></div>
                <div class="bar"></div><div class="bar"></div>
            </div>
            <button onclick="speak()" style="background: #1f3a5f; color: #58a6ff; border: 1px solid #58a6ff; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-family: inherit;">
                INITIATE VOICE LINK
            </button>
        </div>
    </div>

    <!-- 3. Terminal Logs -->
    <div class="panel" id="log-container">
        <div class="panel-header">Real-time Log</div>
        <div id="console-output"></div>
    </div>

    <script>
        // --- 1. Initialize the Map ---
        const map = L.map('map', {zoomControl: false}).setView([20, 0], 2);
        
        // Dark theme map tiles (CartoDB)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd', maxZoom: 19
        }).addTo(map);

        // Add a fake telemetry marker
        L.circleMarker([51.505, -0.09], {color: '#3fb950', radius: 8, fillOpacity: 1})
         .addTo(map)
         .bindPopup("Global Compute Node");

        // --- 2. Terminal Log Streamer ---
        const consoleEl = document.getElementById('console-output');
        function addLog() {
            // Simulate the data being printed by the astra-runner.py
            const time = new Date().toLocaleTimeString('en-US', { hour12: false });
            const nodeCount = Math.floor(Math.random() * 5000) + 5000;
            const status = ["ACTIVE", "SECURE", "SYNCED"][Math.floor(Math.random()*3)];
            
            const logLine = document.createElement('div');
            logLine.textContent = `[${time}] ASTRA_CORE_01 - ${nodeCount} active nodes. System ${status}.`;
            consoleEl.appendChild(logLine);
            
            // Keep only the last 15 logs to prevent memory issues
            if(consoleEl.children.length > 15) { consoleEl.removeChild(consoleEl.firstChild); }
        }
        setInterval(addLog, 2000); 
        addLog(); // Run once immediately

        // --- 3. Astra Voice Synthesis ---
        function speak() {
            if ('speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance("Astra command center online. Vision confirmation. Inter-agent meet-up synced.");
                utterance.rate = 1.1; // Slightly faster, robotic pace
                utterance.pitch = 0.8; // Deeper voice
                
                // Try to find a female/robotic voice
                const voices = window.speechSynthesis.getVoices();
                const preferredVoice = voices.find(voice => voice.name.includes('Google UK English Female') || voice.name.includes('Samantha'));
                if (preferredVoice) utterance.voice = preferredVoice;

                window.speechSynthesis.speak(utterance);
            } else {
                alert("Voice synthesis not supported in this browser.");
            }
        }
    </script>

<!-- 177B 8-GPU MODEL BRAIN & IDEA CROSSOVER -->
<section id="nexus-177b-crossover" style="margin:10px 0; border:1px solid #ff00ff88; background:#090514; padding:12px; font-family:monospace; color:#f2e6ff;">
  <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ff00ff44; padding-bottom:6px; margin-bottom:8px;">
    <strong style="color:#ff66ff;">177B MODEL BRAIN (8-GPU SPARSE STREAM) &amp; IDEA CROSSOVER</strong>
    <span style="font-size:11px; color:#39ff14; border:1px solid #39ff14; padding:2px 6px;">PORT 8100 // ACTIVE</span>
  </div>
  <div id="gpu-shard-strip" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:4px; margin-bottom:8px; font-size:10px;"></div>
  <div style="font-size:11px; color:#00f0ff; margin-bottom:4px;">DRAG OR TAP TWO IDEA CARDS TO SYNTHESIZE A NEW HYBRID CONCEPT:</div>
  <div id="idea-cards-grid" style="display:grid; grid-template-columns:repeat(2, 1fr); gap:6px; margin-bottom:8px;"></div>
  <div style="display:grid; grid-template-columns:1fr 115px 135px; gap:6px; margin-bottom:6px;">
    <input id="nexus-goal-input" placeholder="Seed new idea OR goal to evolve Android Assistant skill..." style="background:#040812; border:1px solid #ff66ff; color:#fff; padding:6px; font-family:monospace; font-size:11px;" />
    <button onclick="seedNewIdea()" style="background:#00f0ff22; border:1px solid #00f0ff; color:#00f0ff; font-family:monospace; font-weight:bold; font-size:11px; cursor:pointer;">+ SEED IDEA</button>
    <button onclick="evolveAssistantSkill()" style="background:#39ff1422; border:1px solid #39ff14; color:#39ff14; font-family:monospace; font-weight:bold; font-size:11px; cursor:pointer;">EVOLVE SKILL</button>
  </div>
  <div id="nexus-proving-box" style="background:#03060c; border:1px solid #ff66ff44; padding:7px; font-size:11px; color:#39ff14;">
    [177B NEXUS READY] 8 GPU Expert Shards mounted in Zero-Disk Sparse Mode.
  </div>
</section>
<script>
let draggedIdeaId = null, selectedFirstIdea = null;
async function refreshNexus177B() {
  try {
    const r = await fetch('/api/nexus/state');
    const d = await r.json();
    document.getElementById('gpu-shard-strip').innerHTML = (d.gpu_topology || []).map(g =>
      '<div style="background:#0a1122; border:1px solid #00f0ff33; padding:4px;"><strong style="color:#00f0ff;">' + g.gpu + '</strong> (' + g.params + ')<br><span style="color:#a8f9ff;">' + g.expert.slice(0, 20) + '</span></div>'
    ).join('');
    document.getElementById('idea-cards-grid').innerHTML = (d.ideas || []).slice(0, 6).map(idea =>
      '<div draggable="true" ondragstart="draggedIdeaId=\'' + idea.idea_id + '\'" ondragover="event.preventDefault()" ondrop="event.preventDefault(); triggerCrossover(draggedIdeaId, \'' + idea.idea_id + '\')" onclick="handleTapSelect(\'' + idea.idea_id + '\', this)" style="background:#080f1e; border:1px dashed #ff66ff55; padding:7px; cursor:grab; font-size:11px;">' +
      '<div style="display:flex; justify-content:space-between; color:#ff66ff;"><strong>' + idea.idea_id + ' [GEN-' + idea.generation + ']</strong><span>' + idea.domain + '</span></div>' +
      '<div style="color:#fff; font-weight:bold; margin:2px 0;">' + idea.title + '</div>' +
      '<div style="color:#a8f9ff; font-size:10px;">' + idea.payload.slice(0, 80) + '...</div></div>'
    ).join('');
  } catch (e) {}
}
function handleTapSelect(id, el) {
  if (!selectedFirstIdea) {
    selectedFirstIdea = id;
    el.style.borderColor = '#39ff14';
    document.getElementById('nexus-proving-box').innerText = '[SELECTED ' + id + '] Tap a second Idea Card to fuse!';
  } else if (selectedFirstIdea !== id) {
    const first = selectedFirstIdea; selectedFirstIdea = null;
    triggerCrossover(first, id);
  } else {
    selectedFirstIdea = null; el.style.borderColor = '#ff66ff55';
  }
}
async function triggerCrossover(idA, idB) {
  if (!idA || !idB || idA === idB) return;
  const r = await fetch('/api/nexus/crossover', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({idea_a:idA, idea_b:idB})});
  const out = await r.json();
  if (out.idea) {
    document.getElementById('nexus-proving-box').innerHTML = '<strong style="color:#ff66ff;">[SYNTHESIZED: ' + out.idea.idea_id + '] ' + out.idea.title + '</strong><br>' + out.idea.payload + '<br><span style="color:#00f0ff;">PROOF: ' + out.proving.proof_hash + '</span>';
    refreshNexus177B();
  }
}
async function seedNewIdea() {
  const inp = document.getElementById('nexus-goal-input');
  const title = inp.value.trim(); if (!title) return;
  const r = await fetch('/api/nexus/add_idea', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title, domain:'OPERATOR_SEED', payload:title})});
  const out = await r.json(); inp.value = '';
  document.getElementById('nexus-proving-box').innerText = '[SEEDED ' + out.idea_id + '] ' + out.title;
  refreshNexus177B();
}
async function evolveAssistantSkill() {
  const inp = document.getElementById('nexus-goal-input');
  const goal = inp.value.trim() || 'Self-upgrade Android assistant telemetry & fleet execution';
  const r = await fetch('/api/nexus/evolve', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({goal})});
  const out = await r.json(); inp.value = '';
  document.getElementById('nexus-proving-box').innerHTML = '<strong style="color:#39ff14;">[SELF-UPGRADED: ' + out.skill_id + '] ' + out.name + '</strong><br>PROOF: ' + out.proving.proof_hash;
  refreshNexus177B();
}
refreshNexus177B();
</script>

<section style="margin:10px 0;border:1px solid #00f0ff;background:#061320;padding:10px;font-family:monospace;color:#fff"><strong style="color:#00f0ff">GLASS-BOX UNIFIED OS (PORT 8101)</strong><div style="display:flex;gap:5px;margin:6px 0"><input id="ghr" value="google-ai-edge/LiteRT-LM" style="flex:1;background:#020810;color:#fff;border:1px solid #00f0ff;padding:5px"><button onclick="fetch('/api/os/github',{method:'POST',body:JSON.stringify({repo:ghr.value})}).then(r=>r.json()).then(d=>osout.innerText=JSON.stringify(d))" style="background:#00f0ff22;color:#00f0ff;border:1px solid #00f0ff;padding:5px">HARVEST GH</button></div><div style="display:flex;gap:5px"><input id="osp" placeholder="Ask Gemma 4 / LiteRT-LM RAG..." style="flex:1;background:#020810;color:#fff;border:1px solid #39ff14;padding:5px"><button onclick="fetch('/api/os/generate',{method:'POST',body:JSON.stringify({prompt:osp.value})}).then(r=>r.json()).then(d=>osout.innerText=d.artifact.output)" style="background:#39ff1422;color:#39ff14;border:1px solid #39ff14;padding:5px">GENERATE</button></div><pre id="osout" style="margin-top:6px;font-size:11px;color:#39ff14;white-space:pre-wrap">READY</pre></section>

<section id="claude-code-ui" style="margin:10px 0;border:1px solid #d97757;background:#141210;padding:12px;font-family:monospace;color:#f5ede6;border-radius:6px">
  <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #d9775744;padding-bottom:6px;margin-bottom:8px">
    <strong style="color:#e88c6d">⚡ CLAUDE CODE // ENGINEERING MEMORY & UI UPGRADE ENGINE</strong>
    <span style="font-size:10px;color:#39ff14;border:1px solid #39ff14;padding:2px 6px">CLAUDE.md SYNCED</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 120px 120px;gap:6px;margin-bottom:8px">
    <input id="cc-task" placeholder="Describe UI component or engineering upgrade..." style="background:#0c0b0a;border:1px solid #d97757;color:#fff;padding:6px;font-family:monospace;font-size:11px">
    <button onclick="runClaudeUpgrade()" style="background:#d9775733;border:1px solid #d97757;color:#ffb49a;font-weight:bold;font-size:11px;cursor:pointer">BUILD + MEMORIZE</button>
    <button onclick="loadClaudeMemory()" style="background:#00f0ff22;border:1px solid #00f0ff;color:#00f0ff;font-weight:bold;font-size:11px;cursor:pointer">READ CLAUDE.md</button>
  </div>
  <button onclick="runFableReasoning()" style="background:#39ff1422;border:1px solid #39ff14;color:#39ff14;font-weight:bold;font-size:11px;cursor:pointer;margin-top:6px;width:100%;padding:5px">RUN MULTI-STEP REASONING &amp; STATE AUDIT (FABLE 5.2)</button>
  <button onclick="browseArtifacts()" style="background:#ffaa0022;border:1px solid #ffaa00;color:#ffaa00;font-weight:bold;font-size:11px;cursor:pointer;margin-top:4px;width:100%;padding:5px">BROWSE SAVED ARTIFACTS (~/astra-unified-brain/artifacts)</button>
  <button onclick="window.location.href='/api/os/export-zip'" style="background:#00f0ff22;border:1px solid #00f0ff;color:#00f0ff;font-weight:bold;font-size:11px;cursor:pointer;margin-top:4px;width:100%;padding:5px">DOWNLOAD ALL ARTIFACTS (.ZIP)</button>
  <div id="cc-trace" style="background:#0a0908;border:1px solid #d9775733;padding:8px;font-size:11px;color:#d6ccc2;white-space:pre-wrap">● Tool(Memory.Sync): Ready. Indexed CLAUDE.md into 45M-Token Brain (8096).</div>

  <div style="margin-top:8px;border:1px solid #d9775755;background:#0a0908;padding:6px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-size:10px;color:#e88c6d">
      <span>● LIVE COMPONENT SANDBOX PREVIEW</span>
      <button onclick="renderLivePreview()" style="background:#39ff1422;border:1px solid #39ff14;color:#39ff14;padding:2px 8px;font-size:10px;cursor:pointer">RENDER PREVIEW</button>
    </div>
    <iframe id="cc-preview-frame" style="width:100%;height:150px;border:1px solid #39ff1433;background:#050a10"></iframe>
  </div>
</section>
<script>
async function runClaudeUpgrade(){
  const t = document.getElementById('cc-task').value.trim() || 'Upgrade cybernetic telemetry grid component';
  document.getElementById('cc-trace').innerText = '● Tool(Brain.Recall) -> Querying engineering patterns...\n● Tool(Generator.Synth) -> Building component...';
  const r = await fetch('/api/os/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:'Claude Code Engineering Upgrade: '+t})});
  const d = await r.json();
  await fetch('/api/brain/remember',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain:'CLAUDE_CODE_ENG',title:'Upgrade: '+t.slice(0,32),content:d.artifact.output})});
  document.getElementById('cc-trace').innerText = '● Tool(Artifact.Write) -> Saved ' + d.artifact.artifact_id + '\n● Tool(Brain.Commit) -> Persisted to 45M Brain\n\n' + d.artifact.output;
}
async function loadClaudeMemory(){
  const r = await fetch('/api/brain/graph');
  const d = await r.json();
  const eng = (d.nodes||[]).filter(n=>n.domain==='CLAUDE_CODE_ENG').map(n=>'+ '+n.title+': '+n.content.slice(0,110)).join('\n');
  document.getElementById('cc-trace').innerText = '● Read(CLAUDE.md & Brain Nodes):\n' + (eng || 'CLAUDE.md active in memory.');
}


async function runFableReasoning(){
  const g = document.getElementById('cc-task').value.trim() || 'Track all ports, crypto orders, and memory nodes';
  document.getElementById('cc-trace').innerText = '> Thinking (4-Step State Chain)...';
  const r = await fetch('/api/os/reason',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal:g})});
  const d = await r.json();
  document.getElementById('cc-trace').innerText = '[' + d.step_id + ' | ' + d.latency_ms + 'ms]
' + d.trace;
}


async function browseArtifacts(){
  const r = await fetch('/api/os/artifacts');
  const d = await r.json();
  const list = (d.artifacts || []).map(a => `[${a.id}] ${a.title} -> ${a.preview.slice(0,95)}...`).join('\n');
  document.getElementById('cc-trace').innerText = '● Saved Artifacts:\n' + (list || 'No artifacts yet.');
}

function renderLivePreview(){
  const raw = document.getElementById('cc-trace').innerText;
  const frame = document.getElementById('cc-preview-frame');
  frame.srcdoc = '<body style="margin:8px;background:#050a10;color:#39ff14;font-family:monospace;font-size:12px">' + raw.replace(/\n/g,'<br>') + '
<script>
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('button').forEach(b => {
    if (b.innerText.includes('VOICE LINK')) {
      b.onclick = () => {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) { runFableReasoning(); return; }
        const rec = new SR();
        b.innerText = 'LISTENING (FABLE 5.2)...';
        rec.onresult = async (e) => {
          const spoken = e.results[0][0].transcript;
          document.getElementById('cc-task').value = spoken;
          b.innerText = 'INITIATE VOICE LINK';
          await runFableReasoning();
          if ('speechSynthesis' in window) {
            const out = document.getElementById('cc-trace').innerText.slice(0, 260);
            window.speechSynthesis.speak(new SpeechSynthesisUtterance(out));
          }
        };
        rec.onerror = () => { b.innerText = 'INITIATE VOICE LINK'; };
        rec.start();
      };
    }
  });
});
</script>


<section id="astra-workflows-backup" style="margin:10px 0;border:1px solid #39ff1488;background:#05110b;padding:10px;font-family:monospace;color:#e6fff2">
  <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #39ff1444;padding-bottom:5px;margin-bottom:7px">
    <strong style="color:#39ff14">AUTONOMOUS AGENT WORKFLOWS &amp; DAILY SQLITE BACKUPS (PORT 8102)</strong>
    <span style="font-size:10px;color:#00f0ff;border:1px solid #00f0ff;padding:2px 6px">24H AUTO-SNAPSHOT ACTIVE</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:6px">
    <button onclick="triggerAgentWF('WF-01')" style="background:#ffaa0022;border:1px solid #ffaa00;color:#ffaa00;font-weight:bold;font-size:10px;padding:6px;cursor:pointer">WF-01: LEGAL SHIELD</button>
    <button onclick="triggerAgentWF('WF-02')" style="background:#00f0ff22;border:1px solid #00f0ff;color:#00f0ff;font-weight:bold;font-size:10px;padding:6px;cursor:pointer">WF-02: FLEET + BI</button>
    <button onclick="triggerAgentWF('WF-03')" style="background:#ff66ff22;border:1px solid #ff66ff;color:#ff66ff;font-weight:bold;font-size:10px;padding:6px;cursor:pointer">WF-03: FULL SYNC</button>
    <button onclick="triggerHotBackup()" style="background:#39ff1422;border:1px solid #39ff14;color:#39ff14;font-weight:bold;font-size:10px;padding:6px;cursor:pointer">BACKUP NOW</button>
  </div>


  <div style="display:grid;grid-template-columns:1fr 1.2fr 0.7fr 0.7fr;gap:6px;margin-bottom:6px;align-items:center">
    <div id="sys-hw-gauge" style="background:#020805;border:1px solid #00f0ff55;color:#00f0ff;padding:5px;font-size:10px">CPU LOAD: -- | RAM: --</div>
    <input id="alert-hook-url" placeholder="Webhook URL for backup/escrow alerts..." style="background:#020805;border:1px solid #ffaa0055;color:#fff;padding:5px;font-family:monospace;font-size:10px">
    <button onclick="saveAlertHook()" style="background:#ffaa0022;border:1px solid #ffaa00;color:#ffaa00;font-weight:bold;font-size:10px;padding:5px;cursor:pointer">SAVE ALERT</button>
    <button onclick="testAlertHook()" style="background:#39ff1422;border:1px solid #39ff14;color:#39ff14;font-weight:bold;font-size:10px;padding:5px;cursor:pointer">TEST ALERT</button>
  </div>
  <div style="display:grid;grid-template-columns:1.4fr 0.8fr 0.8fr;gap:6px;margin-bottom:6px">
    <select id="wf-snap-select" style="background:#020805;border:1px solid #39ff1455;color:#39ff14;padding:5px;font-family:monospace;font-size:11px">
      <option value="">Loading saved snapshots...</option>
    </select>
    <button onclick="restoreSelectedSnap()" style="background:#ff444422;border:1px solid #ff5555;color:#ff8888;font-weight:bold;font-size:10px;padding:5px;cursor:pointer">RESTORE SNAPSHOT</button>
    <button onclick="triggerGitSyncNow()" style="background:#00f0ff22;border:1px solid #00f0ff;color:#00f0ff;font-weight:bold;font-size:10px;padding:5px;cursor:pointer">GIT SYNC NOW</button>
  </div>
  <div id="wf-output" style="background:#020805;border:1px solid #39ff1433;padding:6px;font-size:11px;color:#a8ffce;white-space:pre-wrap">[WORKFLOWS READY] 7 SQLite WAL ledgers scheduled for automatic 24-hour hot backup.</div>
</section>
<script>
async function triggerAgentWF(wf){
  document.getElementById('wf-output').innerText = '> Executing ' + wf + ' across microservices...';
  const r = await fetch('/api/wf/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workflow:wf})});
  const d = await r.json();
  document.getElementById('wf-output').innerText = '[' + d.workflow + ' ' + d.status + ']\n' + (d.trace||[]).join('\n');
}
async function triggerHotBackup(){
  const r = await fetch('/api/wf/backup',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const d = await r.json();
  document.getElementById('wf-output').innerText = '[' + d.status + '] ' + d.snapshot + ' (' + d.dbs_backed_up + ' SQLite DBs) | PROOF: ' + d.proof_hash;
}

async function loadSnapshots(){
  try {
    const r = await fetch('/api/wf/state');
    const d = await r.json();
    const sel = document.getElementById('wf-snap-select');
    if (sel && d.snapshots && d.snapshots.length) {
      sel.innerHTML = d.snapshots.map(sn => '<option value="' + sn + '">' + sn + '</option>').join('');
    }
  } catch (e) {}
}
async function restoreSelectedSnap(){
  const snap = document.getElementById('wf-snap-select').value;
  if (!snap) return;
  const r = await fetch('/api/wf/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({snapshot:snap})});
  const d = await r.json();
  document.getElementById('wf-output').innerText = '[' + (d.status||'ERROR') + '] ' + (d.snapshot||d.error) + ' (' + (d.dbs_restored||0) + ' DBs restored)';
}
async function triggerGitSyncNow(){
  document.getElementById('wf-output').innerText = '> Pushing code, CLAUDE.md & manifests to GitHub...';
  const r = await fetch('/api/wf/git-sync',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const d = await r.json();
  document.getElementById('wf-output').innerText = '[GITHUB SYNC] ' + d.status;
}

async function pollHwMetrics(){
  try {
    const r = await fetch('/api/wf/metrics');
    const m = await r.json();
    const el = document.getElementById('sys-hw-gauge');
    if (el) el.innerText = 'CPU LOAD: ' + m.cpu_load_1m + ' | RAM: ' + m.ram_used_mb + '/' + m.ram_total_mb + 'MB (' + m.ram_pct + '%)';
  } catch (e) {}
}
async function saveAlertHook(){
  const webhook_url = document.getElementById('alert-hook-url').value.trim();
  const r = await fetch('/api/wf/set-alert',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({webhook_url})});
  const d = await r.json();
  document.getElementById('wf-output').innerText = '[ALERT CONFIG] ' + d.status;
}
async function testAlertHook(){
  const r = await fetch('/api/wf/test-alert',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const d = await r.json();
  document.getElementById('wf-output').innerText = '[ALERT TEST] ' + d.status + ' (Webhook: ' + d.webhook_active + ')';
}
setInterval(pollHwMetrics, 4000);
pollHwMetrics();
loadSnapshots();
</script>


<section id="astra-location-intel" style="margin:10px 0;border:1px solid #00f0ff88;background:#04111c;padding:10px;font-family:monospace;color:#e6f9ff">
  <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #00f0ff44;padding-bottom:5px;margin-bottom:7px">
    <strong style="color:#00f0ff">PREDICTIVE LOCATION INTELLIGENCE // GREENSBORO &amp; PIEDMONT TRIAD (PORT 8103)</strong>
    <span style="font-size:10px;color:#39ff14;border:1px solid #39ff14;padding:2px 6px">SPATIAL GRAVITY MODEL</span>
  </div>
  <div style="display:grid;grid-template-columns:1.2fr 0.6fr 0.6fr 0.7fr 110px;gap:5px;margin-bottom:6px">
    <input id="geo-name" placeholder="Zone / Site Name" value="GSO East Logistics Hub" style="background:#02080f;border:1px solid #00f0ff55;color:#fff;padding:5px;font-size:11px">
    <input id="geo-lat" placeholder="Lat" value="36.0680" style="background:#02080f;border:1px solid #00f0ff55;color:#00f0ff;padding:5px;font-size:11px">
    <input id="geo-lon" placeholder="Lon" value="-79.7450" style="background:#02080f;border:1px solid #00f0ff55;color:#00f0ff;padding:5px;font-size:11px">
    <input id="geo-cap" placeholder="Capital $" value="50000" style="background:#02080f;border:1px solid #39ff1455;color:#39ff14;padding:5px;font-size:11px">
    <button onclick="runGeoPredict()" style="background:#00f0ff22;border:1px solid #00f0ff;color:#00f0ff;font-weight:bold;font-size:10px;cursor:pointer">PREDICT ROI</button>
  </div>
  <div id="geo-output" style="background:#02060b;border:1px solid #00f0ff33;padding:6px;font-size:11px;color:#39ff14;white-space:pre-wrap">[GEO READY] 5 Piedmont Triad nodes indexed around Greensboro, NC (36.0726, -79.7920).</div>
</section>
<script>
async function loadGeoNodes(){
  try {
    const r = await fetch('/api/geo/state');
    const d = await r.json();
    const top = (d.nodes || []).slice(0,3).map(n => n.name + ' [Demand: ' + Math.round(n.demand_idx*100) + '% | ROI: ' + n.predicted_roi + 'x]').join(' | ');
    document.getElementById('geo-output').innerText = '[TOP TRIAD ZONES] ' + top;
    if (window.L && window.map) {
      (d.nodes || []).forEach(n => L.circleMarker([n.lat, n.lon], {radius:6, color:'#39ff14'}).addTo(window.map).bindPopup(n.name + ' (' + Math.round(n.demand_idx*100) + '% Demand)'));
    }
  } catch (e) {}
}
async function runGeoPredict(){
  const payload = {
    name: document.getElementById('geo-name').value.trim(),
    lat: parseFloat(document.getElementById('geo-lat').value),
    lon: parseFloat(document.getElementById('geo-lon').value),
    capital_usd: parseFloat(document.getElementById('geo-cap').value) || 50000
  };
  const r = await fetch('/api/geo/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const out = await r.json();
  document.getElementById('geo-output').innerText = '[' + out.node_id + '] ' + out.name + ' (' + out.distance_from_gso_miles + ' mi from GSO HQ)\nDEMAND SCORE: ' + Math.round(out.demand_score*100) + '% | 30-DAY PROJECTED VALUE: $' + out.projected_30d_value_usd.toLocaleString() + ' | PROOF: ' + out.proof_hash;
  if (window.L && window.map) {
    L.circleMarker([out.lat, out.lon], {radius:8, color:'#ffaa00'}).addTo(window.map).bindPopup(out.name + ': $' + out.projected_30d_value_usd.toLocaleString()).openPopup();
  }
}
loadGeoNodes();
</script>

</body>';
}
</script>

</body>
</html>
"""

class Handler(http.server.SimpleHTTPRequestHandler):

    def _forward_api(self):
        import urllib.request
        routes = {
            "/api/legal/": 8095,
            "/api/brain/": 8096,
            "/api/ooda/": 8097,
            "/api/bi/": 8098,
            "/api/nexus/": 8100,
            "/api/os/": 8101,
            "/api/wf/": 8102,
            "/api/geo/": 8103,
            "/dealership": 8099,
            "/api/state": 8099,
            "/api/acquire": 8099,
            "/api/advance": 8099,
            "/api/reset": 8099,
            "/api/add_vehicle": 8099,
            "/api/set_webhook": 8099,
            "/api/receipt/": 8099
        }
        target_port = next((port for prefix, port in routes.items() if self.path.startswith(prefix)), None)
        if not target_port:
            return False
        sub = self.path.replace("/dealership", "", 1) or "/"
        url = f"http://127.0.0.1:{target_port}{sub}"
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if (self.command == "POST" and length > 0) else (b"{}" if self.command == "POST" else None)
        req = urllib.request.Request(url, data=body, method=self.command)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
            self.send_response(r.status)
            self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(data)
        return True

    def do_POST(self):
        if self._forward_api():
            return
        self.send_error(404, "Endpoint not found")

    def do_GET(self):
        if self._forward_api():
            return
        if self.path.startswith('/api/os/'):
            import urllib.request
            b = self.rfile.read(int(self.headers.get('Content-Length',0))) if self.command=='POST' else None
            rq = urllib.request.Request('http://127.0.0.1:8101'+self.path, data=b, headers={'Content-Type':'application/json'})
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(urllib.request.urlopen(rq, timeout=6).read()); return

        if self.path.startswith('/api/nexus/'):
            import urllib.request
            with urllib.request.urlopen('http://127.0.0.1:8100' + self.path, timeout=4) as r:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(r.read())
            return

        # Serve the main dashboard UI
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode())

if __name__ == "__main__":
    PORT = 8088
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving Astra Command Center on http://localhost:{PORT}")
        httpd.serve_forever()
