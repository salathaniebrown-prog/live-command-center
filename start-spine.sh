#!/data/data/com.termux/files/usr/bin/bash

cd ~/astra-enterprise-core || exit 1

echo "[*] Acquiring Termux wake lock..."
termux-wake-lock 2>/dev/null || true

echo "[*] Stopping any existing telemetry processes..."
pkill -f "telemetry-spine.js" 2>/dev/null || true
pkill -f "python_worker.py" 2>/dev/null || true
pkill -f "SpineLogger" 2>/dev/null || true
pkill -f "web-dashboard.js" 2>/dev/null || true

echo "[*] Verifying Java 21 compilation..."
if [ ! -f "SpineLogger.class" ] || [ "SpineLogger.java" -nt "SpineLogger.class" ]; then
  javac SpineLogger.java
fi

echo "[*] Launching Node.js hardware telemetry spine..."
node telemetry-spine.js > /dev/null 2>&1 &

echo "[*] Launching Python telemetry worker..."
python python_worker.py > /dev/null 2>&1 &

echo "[*] Launching Java 21 telemetry worker..."
java SpineLogger > /dev/null 2>&1 &

echo "[*] Launching Web Dashboard on http://127.0.0.1:8080..."
node web-dashboard.js > /dev/null 2>&1 &

sleep 2
echo "[+] All 4 telemetry services online."
echo "[+] Web UI : http://127.0.0.1:8080"
echo "[+] CLI UI : node dashboard.js"
