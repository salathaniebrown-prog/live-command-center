#!/data/data/com.termux/files/usr/bin/bash
export HOME="/data/data/com.termux/files/home"
cd "$HOME" || exit 1

# Hold Android CPU wake lock so background supercomputer nodes never sleep
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# Start all core & upgrade nodes idempotently if not already listening
start_if_down() {
  local port="$1"
  local script="$2"
  local logf="$3"
  if ! python3 -c "import socket; s=socket.create_connection(('127.0.0.1', $port), 0.3); s.close()" 2>/dev/null; then
    [ -f "$HOME/$script" ] && setsid nohup python3 "$HOME/$script" > "$HOME/$logf" 2>&1 < /dev/null &
  fi
}

start_if_down 8088 "dashboard_server.py" "dashboard.log"
start_if_down 8099 "dealership_module.py" "dealership_8099.log"
start_if_down 8123 "astra_saga_engine.py" "saga_8123.log"
start_if_down 8125 "astra_governance_engine.py" "gov_8125.log"
start_if_down 8127 "astra_elite_cinema_autopilot.py" "studio_8127.log"

# Run 30s watchdog & auto-upgrade daemon if not running
if ! pgrep -f "auto_correct_brain.py" >/dev/null 2>&1; then
  [ -f "$HOME/auto_correct_brain.py" ] && setsid nohup python3 "$HOME/auto_correct_brain.py" > "$HOME/watchdog.log" 2>&1 < /dev/null &
fi

# Launch Command Center UI automatically in Chrome if termux-open-url is available
if [ "$1" = "--open" ] && command -v termux-open-url >/dev/null 2>&1; then
  sleep 1
  termux-open-url "http://127.0.0.1:8088"
fi
start_if_down 8129 "astra_spatial_assistant.py" "spatial_8129.log"
start_if_down 8131 "astra_quantum_lattice.py" "quantum_8131.log"
