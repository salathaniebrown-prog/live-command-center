#!/usr/bin/env bash
# ==============================================================================
# MASTER STACK CONTROLLER SEQUENCE
# Boots the backend bridge, telemetry loop, and secure proxy simultaneously.
# ==============================================================================

echo "[*] Initializing sovereign multi-process network infrastructure..."

# 1. Clear old lingering network bindings cleanly
echo "[*] Scanning network interfaces for old ports..."
fuser -k 3001/tcp 8888/tcp 2>/dev/null
python ~/_gpu_daemon.py > /dev/null 2>&1 &
nginx -s stop 2>/dev/null

# 2. Fire up the FastAPI Log Bridge Component
echo "[*] Spawning FastAPI Core Engine on port 3001..."
cd ~/freellmapi
python server_bridge.py > /dev/null 2>&1 &
BRIDGE_PID=$!

# Wait briefly to ensure port 3001 is listening properly
sleep 2

# 3. Fire up the Background Data Injector Daemon
if [ -f ~/injector.sh ]; then
    echo "[*] Spawning Automated Telemetry Loop Injector Daemon..."
    ~/injector.sh > /dev/null 2>&1 &
    INJECTOR_PID=$!
else
    echo "[!] Warning: ~/injector.sh not found. Skipping data background loop."
fi

# 4. Spin up the Encrypted HTTPS Nginx Proxy Gateway
echo "[*] Launching Secure HTTPS Nginx Reverse Proxy Core on port 8888..."
python ~/_gpu_daemon.py > /dev/null 2>&1 &
nginx

echo -e "\n\033[1;32m[+] STACK STARTUP RUNTIME COMPLETE!\033[0m"
echo "--------------------------------------------------------"
echo "FastAPI Bridge PID: $BRIDGE_PID"
echo "Proxy Endpoint Node: https://127.0.0.1:8888"
echo "--------------------------------------------------------"
echo "To check active network listeners, run: ss -tlnp"
echo "To stop this entire background stack stack later, run: stopstack"
