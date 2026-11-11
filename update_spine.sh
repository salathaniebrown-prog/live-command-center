#!/bin/bash
echo "[+] Restarting telemetry spine with media handler..."
./start-spine.sh
git add .
git commit -m "feat: integrate local media browser and file upload pipeline"
git push origin main
echo "[v] Push complete and spine active!"
