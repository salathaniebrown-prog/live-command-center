#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock

setsid nohup python3 "$HOME/dealership_module.py" > "$HOME/dealership_8099.log" 2>&1 < /dev/null &

# 1. Start Core Command Center & Virtual Card Dealership UI (8088)
setsid nohup python3 "$HOME/dashboard_server.py" > "$HOME/dashboard.log" 2>&1 < /dev/null &

# 2. Start Studio Pro & Auto-Astra Model Router (8108 & 8109)
setsid nohup python3 "$HOME/astra-unified-brain/compute_router_8108_8109.py" > "$HOME/astra-unified-brain/router_8108_8109.log" 2>&1 < /dev/null &

# 3. Start JEV Invoice Agent Router (8111)
setsid nohup python3 "$HOME/invoice_agent_8111.py" > "$HOME/invoice_8111.log" 2>&1 < /dev/null &

# 4. Start MediaPipe Edge ML (8113)
setsid nohup python3 "$HOME/astra-mediapipe-tasks/mediapipe_edge_ml.py" > "$HOME/astra-mediapipe-tasks/mp.log" 2>&1 < /dev/null &

# 5. Start Live Crypto & Virtual-Card Webhook Listener (8115)
setsid nohup python3 "$HOME/webhook_listener_8115.py" > "$HOME/webhook_8115.log" 2>&1 < /dev/null &

# 6. Start Named Cloudflare Tunnel & 30s Self-Healing Watchdog
bash "$HOME/start_tunnel.sh"
setsid nohup python3 "$HOME/astra-unified-brain/auto_correct_brain.py" > "$HOME/astra-unified-brain/watchdog.log" 2>&1 < /dev/null &
