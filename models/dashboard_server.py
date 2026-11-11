import http.server
import socketserver
import json
import time
import threading
import random
import urllib.request

# --- Global variables ---
LOG_FILE = "astra_system.log"
VOICE_FILE = "astra_voice_output.txt"

# --- Background Thread: Generate Real Logs ---
def log_generator():
    while True:
        with open(LOG_FILE, "a") as f:
            timestamp = time.strftime("%H:%M:%S")
            node_count = random.randint(10000, 15000)
            f.write(f"[{timestamp}] ASTRA_CORE_01 - {node_count} active nodes. Telemetry synced.\n")
        time.sleep(2)

# Start the log thread
threading.Thread(target=log_generator, daemon=True).start()

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Astra Command Center</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        :root {
            --bg-color: #0a0e17; --panel-bg: rgba(16, 24, 39, 0.85); --border-color: #1f3a5f;
            --text-main: #8bb3e3; --text-highlight: #58a6ff; --text-green: #3fb950;
        }
        body { margin: 0; padding: 10px; background-color: var(--bg-color); color: var(--text-main); font-family: 'Courier New', monospace; height: 100vh; box-sizing: border-box; display: grid; grid-template-columns: 2fr 1fr; grid-template-rows: 1fr 200px; gap: 10px; }
        .panel { background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 6px; padding: 10px; position: relative; overflow: hidden; }
        .panel-header { color: var(--text-highlight); font-size: 14px; text-transform: uppercase; margin-bottom: 10px; border-bottom: 1px solid var(--border-color); padding-bottom: 5px; }
        
        #map-container { grid-column: 1 / 2; grid-row: 1 / 2; padding: 0; }
        #map { width: 100%; height: 100%; border-radius: 6px; z-index: 1; }
        .leaflet-layer { filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%); }

        #avatar-container { grid-column: 2 / 3; grid-row: 1 / 3; display: flex; flex-direction: column; }
        .avatar-display { flex-grow: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .avatar-face { width: 120px; height: 120px; border-radius: 50%; background: linear-gradient(135deg, #1f3a5f, #0a0e17); border: 2px solid var(--text-highlight); box-shadow: 0 0 20px rgba(88, 166, 255, 0.3); position: relative; margin-bottom: 20px; }
        .avatar-eye { width: 15px; height: 15px; background: var(--text-highlight); border-radius: 50%; position: absolute; top: 40%; }
        .eye-left { left: 30%; } .eye-right { right: 30%; }
        
        #log-container { grid-column: 1 / 2; grid-row: 2 / 3; }
        #console-output { font-size: 12px; color: var(--text-green); overflow-y: auto; height: 140px; display: flex; flex-direction: column-reverse;}
        #console-output div { margin-bottom: 3px; }

        @media (max-width: 768px) {
            body { grid-template-columns: 1fr; grid-template-rows: 300px 1fr 150px; }
            #avatar-container { grid-column: 1 / 2; grid-row: 2 / 3; }
            #log-container { grid-row: 3 / 4; }
        }
    </style>
</head>
<body>
    <div class="panel" id="map-container"><div id="map"></div></div>
    <div class="panel" id="avatar-container">
        <div class="panel-header">Astra Avatar (Live AI)</div>
        <div class="avatar-display">
            <div class="avatar-face"><div class="avatar-eye eye-left"></div><div class="avatar-eye eye-right"></div></div>
            <button onclick="speakAI()" style="background: #1f3a5f; color: #58a6ff; border: 1px solid #58a6ff; padding: 10px 20px; border-radius: 4px; cursor: pointer;">SYNC AI VOICE</button>
            <p id="ai-text" style="font-size:10px; color:#888; text-align:center; margin-top:10px;"></p>
        </div>
    </div>
    <div class="panel" id="log-container">
        <div class="panel-header">Real-time System Logs</div>
        <div id="console-output"></div>
    </div>

    <script>
        // --- 1. REAL Live Flight Map (OpenSky API) ---
        const map = L.map('map', {zoomControl: false}).setView([20, 0], 2);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {subdomains: 'abcd', maxZoom: 19}).addTo(map);

        async function fetchFlights() {
            try {
                const response = await fetch('https://opensky-network.org/api/states/all');
                const data = await response.json();
                // Get a sample of planes
                const planes = data.states.slice(0, 30); 
                planes.forEach(plane => {
                    const lat = plane[6]; const lon = plane[5]; const callsign = plane[1] || "UNKNOWN";
                    if(lat && lon) {
                        L.circleMarker([lat, lon], {color: '#58a6ff', radius: 3, fillOpacity: 1})
                         .addTo(map).bindPopup(`Flight: ${callsign}`);
                    }
                });
            } catch (e) { console.log("Map API Error:", e); }
        }
        fetchFlights();

        // --- 2. Real-Time Python Logs (SSE) ---
        const consoleEl = document.getElementById('console-output');
        const evtSource = new EventSource("/stream-logs");
        evtSource.onmessage = function(event) {
            const logLine = document.createElement('div');
            logLine.textContent = event.data;
            consoleEl.appendChild(logLine);
            if(consoleEl.children.length > 20) { consoleEl.removeChild(consoleEl.firstChild); }
        };

        // --- 3. Real AI Voice Integration ---
        async function speakAI() {
            // Fetch the text generated by Ollama
            const response = await fetch('/get-ai-voice');
            const aiText = await response.text();
            document.getElementById('ai-text').innerText = aiText;

            if ('speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(aiText);
                utterance.rate = 0.9; utterance.pitch = 0.8;
                window.speechSynthesis.speak(utterance);
            }
        }
    </script>
</body>
</html>
"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream-logs':
            # Server-Sent Events for real-time logs
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            try:
                with open(LOG_FILE, "r") as f:
                    # Keep streaming the last line
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.5)
                            continue
                        self.wfile.write(f"data: {line.strip()}\n\n".encode())
                        self.wfile.flush()
            except Exception:
                pass
                
        elif self.path == '/get-ai-voice':
            # Return the latest AI thought
            try:
                with open(VOICE_FILE, "r") as f:
                    ai_text = f.read()
            except:
                ai_text = "AI data streaming offline. Standby."
            
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(ai_text.encode())
            
        else:
            # Serve HTML
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())

if __name__ == "__main__":
    PORT = 8888
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving Astra Command Center on http://localhost:{PORT}")
        httpd.serve_forever()
