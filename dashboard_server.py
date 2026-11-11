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
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
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

</body>
</html>
"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
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
    PORT = 8888
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving Astra Command Center on http://localhost:{PORT}")
        httpd.serve_forever()
