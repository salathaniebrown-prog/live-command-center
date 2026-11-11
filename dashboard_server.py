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
        L.tileLayer('https://{s}://{z}/{x}/{y}{r}.png', {
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


<!-- ALSTRA LEGAL MASTERY & CRYPTO ASSET PROTECTION BRAIN -->
<section id="alstra-legal-brain" style="margin:12px 0; border:1px solid #ffaa0088; background:#050b12; padding:12px; font-family:monospace; color:#e6f9ff; box-shadow:0 0 18px #ffaa0022;">
  <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ffaa0044; padding-bottom:6px; margin-bottom:8px;">
    <strong style="color:#ffaa00;">⚖️ ALSTRA LEGAL MASTERY BRAIN // HARVARD & DUKE DOCTRINE (CRYPTO & BUILD SHIELD)</strong>
    <span style="font-size:11px; color:#39ff14; border:1px solid #39ff14; padding:2px 6px;">PORT 8095 // ACTIVE</span>
  </div>
  <div style="display:grid; grid-template-columns:1fr 140px 160px; gap:6px; margin-bottom:8px;">
    <input id="legal-query" placeholder="Audit crypto escrow, Wyler VIN title, LLC ring-fence, or AI build contract..." onkeydown="if(event.key==='Enter') runLegalAudit()" style="background:#03080e; border:1px solid #ffaa00; color:#fff; padding:6px; font-family:monospace; font-size:12px;" />
    <button onclick="runLegalAudit()" style="background:#ffaa0022; border:1px solid #ffaa00; color:#ffaa00; font-family:monospace; font-weight:bold; cursor:pointer;">RUN DOCTRINE AUDIT</button>
    <button onclick="copyModelDoctrine()" style="background:#00f0ff22; border:1px solid #00f0ff; color:#00f0ff; font-family:monospace; font-weight:bold; cursor:pointer;">COPY AI MODEL BRAIN</button>
  </div>
  <div id="legal-output" style="background:#03070c; border:1px solid #00f0ff33; padding:8px; font-size:11px; color:#39ff14; line-height:1.5;">
    [DOCTRINE READY] Harvard & Duke Commercial, UCC Art. 12 Digital Asset & Corporate Veil Shield loaded.
  </div>
</section>

<script>
let cachedDoctrinePrompt = "";
async function loadLegalState() {
  try {
    const r = await fetch('/api/legal/state');
    const d = await r.json();
    cachedDoctrinePrompt = d.system_prompt || "";
  } catch (e) {}
}

async function runLegalAudit() {
  const q = document.getElementById('legal-query').value.trim() || "Protect crypto escrow and Wyler vehicle title";
  const r = await fetch('/api/legal/audit', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query: q})
  });
  const out = await r.json();
  document.getElementById('legal-output').innerHTML =
    `<strong>[${out.audit_id}] RISK: ${out.risk_score}</strong><br>${out.analysis}<br><span style="color:#00f0ff;">PROOF HASH: ${out.audit_hash}</span>`;
  if ('speechSynthesis' in window) {
    const utter = new SpeechSynthesisUtterance("Alstra Legal Doctrine Audit complete. Risk status: " + out.risk_score);
    window.speechSynthesis.speak(utter);
  }
}

function copyModelDoctrine() {
  if (cachedDoctrinePrompt && navigator.clipboard) {
    navigator.clipboard.writeText(cachedDoctrinePrompt);
    document.getElementById('legal-output').innerText = "[COPIED] Master Harvard/Duke Legal & Crypto Protection Doctrine copied to clipboard for Ollama / Android Assistant.";
  }
}

// Activate Voice Link button for live Android/Browser Voice Assistant commands
document.addEventListener('DOMContentLoaded', () => {
  loadLegalState();
  document.querySelectorAll('button').forEach(btn => {
    if (btn.innerText.includes('VOICE LINK')) {
      btn.onclick = () => {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRec) {
          runLegalAudit();
          return;
        }
        const rec = new SpeechRec();
        btn.innerText = 'LISTENING (ALSTRA LEGAL/CRYPTO)...';
        rec.onresult = (e) => {
          const transcript = e.results[0][0].transcript;
          document.getElementById('legal-query').value = transcript;
          btn.innerText = 'INITIATE VOICE LINK';
          runLegalAudit();
        };
        rec.onerror = () => { btn.innerText = 'INITIATE VOICE LINK'; };
        rec.start();
      };
    }
  });
});
</script>

<!-- WYLER CRYPTO DEALERSHIP EMBED MODULE -->
<section id="wyler-dealership-node" style="margin-top:12px; border:1px solid #00f0ff55; background:#03060a; box-shadow:0 0 15px #00f0ff22;">
  <div style="padding:6px 12px; background:#061019; border-bottom:1px solid #00f0ff33; color:#39ff14; font-family:monospace; font-size:12px; display:flex; justify-content:space-between;">
    <span>⚡ WYLER & CRYPTO VEHICLE ACQUISITION NODE (PORT 8099)</span>
    <span>DEEPSPACE LEDGER: SYNCED</span>
  </div>
  <iframe src="/dealership" style="width:100%; height:560px; border:none; display:block;" title="Wyler Crypto Dealership"></iframe>
</section>



<!-- INTERACTIVE REAL-TIME TELEMETRY & COMMAND INJECTION BAR -->
<div id="live-telemetry-bar" style="position:fixed; bottom:0; left:0; right:0; background:#03080ff5; border-top:1px solid #39ff1488; color:#39ff14; font-family:monospace; font-size:11px; padding:6px 10px; z-index:9999; display:flex; flex-direction:column; gap:5px; box-shadow:0 -4px 18px #00f0ff22;">
  <div style="display:flex; justify-content:space-between; align-items:center; overflow:hidden; white-space:nowrap;">
    <div><strong style="color:#00f0ff;">[ACTIVE SPINE // REAL.log]</strong> <span id="telemetry-stream-text">Streaming live...</span></div>
    <span id="inject-ack" style="color:#ffaa00; font-size:10px; margin-left:8px;">READY</span>
  </div>
  <div style="display:grid; grid-template-columns:110px 1fr 95px 95px; gap:6px;">
    <select id="inject-tag" style="background:#06121e; border:1px solid #00f0ff; color:#00f0ff; padding:5px; font-family:monospace; font-size:11px;">
      <option value="ASTRA_CORE_01">ASTRA_CORE</option>
      <option value="CRYPTO_NODE">CRYPTO_NODE</option>
      <option value="WYLER_FLEET">WYLER_FLEET</option>
      <option value="BCI_TELEMETRY">BCI_STREAM</option>
    </select>
    <input id="inject-input" placeholder="Enter live telemetry payload, node command, or JSON..." onkeydown="if(event.key==='Enter') sendLiveData()" style="background:#040c14; border:1px solid #39ff14; color:#e6ffff; padding:5px 8px; font-family:monospace; font-size:11px; width:100%;" />
    <button onclick="sendLiveData()" style="background:#39ff1422; border:1px solid #39ff14; color:#39ff14; font-family:monospace; font-weight:bold; font-size:11px; cursor:pointer;">INJECT LIVE</button>
    <button onclick="quickPulse()" style="background:#00f0ff22; border:1px solid #00f0ff; color:#00f0ff; font-family:monospace; font-weight:bold; font-size:11px; cursor:pointer;">PULSE SYNC</button>
  </div>
</div>
<script>
async function pollTelemetry() {
  try {
    const r = await fetch('/api/telemetry');
    const d = await r.json();
    if (d.events && d.events.length) {
      document.getElementById('telemetry-stream-text').innerText = d.events.slice(-2).join('   |   ');
    }
  } catch (e) {}
}

async function sendLiveData() {
  const inp = document.getElementById('inject-input');
  const tag = document.getElementById('inject-tag').value;
  const payload = inp.value.trim();
  if (!payload) return;
  const r = await fetch('/api/inject', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tag, payload})
  });
  const out = await r.json();
  inp.value = '';
  document.getElementById('inject-ack').innerText = '[PUSHED: ' + out.tag + ']';
  pollTelemetry();
}

async function quickPulse() {
  const tag = document.getElementById('inject-tag').value;
  await fetch('/api/inject', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tag, payload: 'LIVE_HEARTBEAT_SYNC_OK // PORT_8088_8099_ACTIVE'})
  });
  document.getElementById('inject-ack').innerText = '[PULSE SENT]';
  pollTelemetry();
}

setInterval(pollTelemetry, 2000);
pollTelemetry();
</script>
</body>

</html>
