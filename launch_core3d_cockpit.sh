#!/data/data/com.termux/files/usr/bin/bash
set -e
pm2 restart astra-8088-ingress astra-8090-gw >/dev/null 2>&1 || true
sleep 1
bash "$HOME/astra_rt_bootstrap.sh"
echo "[✔] Opening Core3D Telemetry Cockpit at http://127.0.0.1:8090/hud3d"
command -v termux-open-url >/dev/null 2>&1 && termux-open-url "http://127.0.0.1:8090/hud3d"
