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

<!-- WYLER CRYPTO DEALERSHIP EMBED MODULE -->
<section id="wyler-dealership-node" style="margin-top:12px; border:1px solid #00f0ff55; background:#03060a; box-shadow:0 0 15px #00f0ff22;">
  <div style="padding:6px 12px; background:#061019; border-bottom:1px solid #00f0ff33; color:#39ff14; font-family:monospace; font-size:12px; display:flex; justify-content:space-between;">
    <span>⚡ WYLER & CRYPTO VEHICLE ACQUISITION NODE (PORT 8099)</span>
    <span>DEEPSPACE LEDGER: SYNCED</span>
  </div>
  <iframe src="/dealership" style="width:100%; height:440px; border:none; display:block;" title="Wyler Crypto Dealership"></iframe>
</section>


<!-- LIVE REAL.LOG TELEMETRY TICKER -->
<div id="live-telemetry-bar" style="position:fixed; bottom:0; left:0; right:0; height:32px; background:#03080fee; border-top:1px solid #39ff1466; color:#39ff14; font-family:monospace; font-size:11px; display:flex; align-items:center; padding:0 12px; z-index:9999; overflow:hidden; white-space:nowrap;">
  <strong style="color:#00f0ff; margin-right:10px;">[LIVE SPINE // REAL.log]</strong>
  <span id="telemetry-stream-text">Connecting to telemetry spine...</span>
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
setInterval(pollTelemetry, 2500);
pollTelemetry();
</script>

</body>
</html>
"""

class Handler(http.server.SimpleHTTPRequestHandler):
    
    def _proxy_dealership(self, method="GET"):
        import urllib.request
        target = "http://127.0.0.1:8099" + (self.path.replace("/dealership", "", 1) or "/")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(target, data=body, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.headers.get("Content-Type", "text/html"))
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        if self.path.startswith('/api/acquire') or self.path.startswith('/api/advance') or self.path.startswith('/api/reset') or self.path.startswith('/api/add_vehicle') or self.path.startswith('/api/acquire_batch') or self.path.startswith('/api/set_webhook'):
            self.path = '/dealership' + self.path
            return self._proxy_dealership('POST')

    def do_GET(self):
        if self.path == '/api/telemetry':
            import json
            log_path = os.path.expanduser('~/telemetry-spine/REAL.log')
            lines = []
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                    lines = [l.strip() for l in lf.readlines()[-8:] if l.strip()]
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'events': lines}).encode('utf-8'))
            return

        if self.path.startswith('/dealership') or self.path.startswith('/api/state') or self.path.startswith('/api/receipt/'):
            if self.path.startswith('/api/state') or self.path.startswith('/api/receipt/'):
                self.path = '/dealership' + self.path
            return self._proxy_dealership('GET')
        # Serve the main dashboard UI
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode())

if __name__ == "__main__":
    PORT = 8088
    socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving Astra Command Center on http://localhost:{PORT}")
        httpd.serve_forever()
