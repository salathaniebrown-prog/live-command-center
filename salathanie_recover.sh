#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="/data/data/com.termux/files/home/live-command-center"
export ASTRA_HOST="0.0.0.0"
export ASTRA_LOCATION="Greensboro, NC"

termux-wake-lock >/dev/null 2>&1 || true

ensure_pm2() {
  local name="$1"; shift
  if pm2 describe "$name" >/dev/null 2>&1; then
    local status
    status=$(pm2 jlist | python3 -c "import sys,json; d=json.load(sys.stdin); print(next((p['pm2_env']['status'] for p in d if p['name']=='$name'), ''))")
    if [ "$status" != "online" ]; then
      echo "[*] Restarting $name..."
      pm2 restart "$name" --update-env
    else
      echo "[OK] $name already online"
    fi
  else
    echo "[*] Starting $name..."
    pm2 start "$@" --name "$name"
  fi
}

# 1. Gateway (:8090) — only start under PM2 if port 8090 is not already bound
if ! curl -s --max-time 2 "http://127.0.0.1:8090/" >/dev/null 2>&1; then
  if [ -f "$HOME/alstra_unified_8090_gateway.py" ]; then
    ensure_pm2 "salathanie-gw-8090" "$HOME/alstra_unified_8090_gateway.py" --interpreter python3
  fi
else
  echo "[OK] Port 8090 gateway already responding"
fi

# 2. Core WAL Spine (:8182) & Project PULSAR (10k-bit HDC)
ensure_pm2 "salathanie-wal-8182" "$REPO/astra_svc_8182.py" --interpreter python3
ensure_pm2 "salathanie-pulsar-10k" "$REPO/project_pulsar.js"
ensure_pm2 "salathanie-causal-shadow" "$REPO/causal_shadow.py" --interpreter python3

# 3. Quick Tunnel -> :8090
GW_PORT=$(python3 "$REPO/hdc_shm_bus.py" --get-port salathanie-gw-8090 --default 8090)
ensure_pm2 "salathanie-tunnel" cloudflared -- tunnel --no-autoupdate --url "http://127.0.0.1:${GW_PORT}"

pm2 save --force >/dev/null 2>&1 || true
sleep 3

echo "=== SALATHANIE A.I HEALTH ==="
curl -s --max-time 3 "http://127.0.0.1:8182/health" ; echo
for p in 8090 8182 8108 8109 8111 8113 8115; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:$p/" || echo "000")
  echo "Port $p -> HTTP $code"
done

TUNNEL_URL=$(grep -hoE "https://[a-zA-Z0-9.-]+\.trycloudflare\.com" ~/.pm2/logs/salathanie-tunnel-*.log 2>/dev/null | tail -n 1 || true)
echo "LIVE TUNNEL: ${TUNNEL_URL:-INITIALIZING}"
