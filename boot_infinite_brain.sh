#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
pkill -f "legal_brain.py|astra_brain.py|ooda_os_core.py|bi_superintelligence.py|dealership_core.py|astra_177b_nexus.py|unified_brain_os.py|autonomous_workflows_backup.py|location_intel_engine.py" || true

setsid nohup python3 ~/ai-studio-legal/legal_brain.py > ~/ai-studio-legal/legal.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-memory-brain/astra_brain.py > ~/astra-memory-brain/brain.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-ooda-os/ooda_os_core.py > ~/astra-ooda-os/ooda.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-bi-engine/bi_superintelligence.py > ~/astra-bi-engine/bi.log 2>&1 < /dev/null &
setsid nohup python3 ~/ai-studio-dealership/dealership_core.py > ~/ai-studio-dealership/server.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-177b-nexus/astra_177b_nexus.py > ~/astra-177b-nexus/nexus.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-unified-brain/unified_brain_os.py > ~/astra-unified-brain/unified.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-workflows/autonomous_workflows_backup.py > ~/astra-workflows/wf.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-location-intel/location_intel_engine.py > ~/astra-location-intel/geo.log 2>&1 < /dev/null &

sleep 2
bash ~/check_all.sh

# --- ALSTRA TELEMETRY (8100) & DUAL-STREAM BRIDGE (8113) ---
if ! nc -z 127.0.0.1 8100 2>/dev/null; then
  nohup python3 -c '
import json, subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
PORTS = [8088, 8095, 8096, 8097, 8098, 8099, 8100, 8113]
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        up = sum(1 for p in PORTS if subprocess.run(["nc","-z","127.0.0.1",str(p)], capture_output=True).returncode == 0)
        body = json.dumps({"online": up, "total": len(PORTS), "status": "NOMINAL"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", 8100), H).serve_forever()
' > ~/telemetry_8100.log 2>&1 < /dev/null &
  echo "[BOOT] Started Telemetry Health Node on Port 8100"
fi

if ! nc -z 127.0.0.1 8113 2>/dev/null; then
  nohup python3 ~/astra-enterprise-core/dual_stream_bridge.py > ~/dual_stream_8113.log 2>&1 < /dev/null &
  echo "[BOOT] Started Alstra Dual-Stream Bridge on Port 8113"
fi
setsid nohup python3 ~/astra-enterprise-core/telemetry_sentinel.py > ~/telemetry_sentinel.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-jev-system1/jev_router.py > ~/astra-jev-system1/jev.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-mediapipe-tasks/mediapipe_edge_ml.py > ~/astra-mediapipe-tasks/mp.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-mediapipe-tasks/overnight_daemon.py > ~/astra-mediapipe-tasks/overnight_boot.log 2>&1 < /dev/null &
