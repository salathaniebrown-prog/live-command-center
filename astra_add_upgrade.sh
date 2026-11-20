#!/data/data/com.termux/files/usr/bin/bash
set -e
NAME="${1:?Usage: astra_add_upgrade.sh <name> <port> <script_path>}"
PORT="${2:?Usage: astra_add_upgrade.sh <name> <port> <script_path>}"
SCRIPT="${3:?Usage: astra_add_upgrade.sh <name> <port> <script_path>}"

# Lock snapshot before adding upgrade
bash "$HOME/astra_lock_snapshot.sh" 2>/dev/null || true

# Register as additive upgrade in :8143 (blocks overwriting foundation files)
curl -s -X POST http://127.0.0.1:8143/api/upgrade/register \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${NAME}\",\"kind\":\"additive_module\",\"port\":${PORT},\"entry\":\"${SCRIPT}\"}"
echo ""

# Start new upgrade under PM2 without touching existing foundation processes
if [ -f "$SCRIPT" ]; then
  python3 -m py_compile "$SCRIPT"
  pm2 start "$SCRIPT" --name "astra-upg-${NAME}" \
    --interpreter python3 --max-restarts 5 --restart-delay 3000 --max-memory-restart 80M
  pm2 save --force
fi
