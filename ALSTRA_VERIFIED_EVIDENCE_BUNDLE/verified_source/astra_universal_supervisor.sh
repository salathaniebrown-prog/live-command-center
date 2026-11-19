#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="$HOME"
cd "$HOME_DIR"
termux-wake-lock 2>/dev/null || true

# 1. Start core 14-node cluster
if [ -f "$HOME_DIR/astra-enterprise-core/astra_start.sh" ]; then
    bash "$HOME_DIR/astra-enterprise-core/astra_start.sh" || true
fi

# 2. Ensure Live Command Center UI on Port 8090
if ! python3 -c "import socket; exit(0 if socket.socket().connect_ex(('127.0.0.1', 8090)) == 0 else 1)" 2>/dev/null; then
    if [ -f "$HOME_DIR/dashboard_server.py" ]; then
        setsid nohup python3 "$HOME_DIR/dashboard_server.py" > "$HOME_DIR/dashboard.log" 2>&1 < /dev/null &
    fi
fi

# 3. Supervise Context-Telemetry + VR (8137), OpenAI Tool Proxy (8139), and GitHub Watchdog (8141)
for svc in astra-8137-context-vr astra-8139-openai-proxy astra-8141-github-watchdog; do
    pm2 delete "$svc" 2>/dev/null || true
done

pm2 start "$HOME_DIR/astra_context_telemetry_monitor.py" \
    --name "astra-8137-context-vr" --restart-delay 2000 --max-restarts 50 -- --serve

pm2 start "$HOME_DIR/astra_openai_tool_proxy.py" \
    --name "astra-8139-openai-proxy" --restart-delay 2000 --max-restarts 50

pm2 start "$HOME_DIR/astra_github_watchdog_daemon.py" \
    --name "astra-8141-github-watchdog" --restart-delay 2000 --max-restarts 50 -- --serve

pm2 save --force
sleep 2
echo "[✔] Unified Supervisor Online: UI(:8090) | Context+VR(:8137) | OpenAI Proxy(:8139) | GitHub Watchdog(:8141)"
