#!/usr/bin/env bash
termux-wake-lock 2>/dev/null || true
cd "$HOME"

start_node() {
    local port="$1"
    local script="$2"
    local log="$3"
    if ! nc -z 127.0.0.1 "$port" 2>/dev/null; then
        setsid nohup python3 "$HOME/$script" > "$HOME/$log" 2>&1 < /dev/null &
        sleep 0.4
    fi
}

start_node 8088 dashboard_server.py dashboard.log
start_node 8099 astra_dealership.py dealership.log
start_node 8109 astra_unified_brain.py brain.log
start_node 8111 astra_invoice_agent.py invoice.log
start_node 8113 astra_edge_ml.py edgeml.log
start_node 8115 astra_webhook_listener.py webhook.log
start_node 8117 astra_trust_center.py trust.log
start_node 8119 astra_supercomputer_mesh.py mesh.log
start_node 8121 astra_cinema_mcp.py cinema.log
start_node 8123 astra_durable_saga.py saga.log
start_node 8125 astra_enterprise_gov.py gov.log
start_node 8127 astra_elite_cinema_autopilot.py studio.log
start_node 8129 astra_spatial_assistant.py spatial.log
start_node 8131 astra_quantum_lattice.py quantum.log

echo "[✔] All 14 Astra cluster nodes initialized."
