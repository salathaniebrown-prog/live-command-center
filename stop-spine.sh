#!/data/data/com.termux/files/usr/bin/bash

echo "[*] Stopping Astra Enterprise Core telemetry services..."
pkill -f "telemetry-spine.js" 2>/dev/null || true
pkill -f "python_worker.py" 2>/dev/null || true
pkill -f "SpineLogger" 2>/dev/null || true
pkill -f "web-dashboard.js" 2>/dev/null || true
termux-wake-unlock 2>/dev/null || true
echo "[+] All telemetry services stopped and wake lock released."
