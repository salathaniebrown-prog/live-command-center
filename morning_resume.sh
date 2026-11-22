#!/data/data/com.termux/files/usr/bin/bash
set -e
REPO="/data/data/com.termux/files/home/live-command-center"
cd "$REPO"
python3 "$REPO/model_guard_autopilot.py" --unlock --status
pm2 start salathanie-pulsar-10k 2>/dev/null || true
pm2 restart salathanie-pilot salathanie-agents
pm2 save --force
pm2 status
curl -s "http://127.0.0.1:8125/api/pilot/status" | python3 -m json.tool | grep -E "mem_avail_mb|tunnel_url|attested"
echo "[OK] Salathanie A.I morning resume complete."
