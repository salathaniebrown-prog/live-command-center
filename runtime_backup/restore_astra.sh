#!/usr/bin/env bash
set -euo pipefail
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/tmp ~/local_shm_monitor
for rel in \
  dashboard_server.py \
  astra_ram70.py \
  astra_3stream.py \
  astra_stack_boot.sh \
  alstra_master_spine_8095.py \
  alstra_genius_brain_8099.py \
  tmp/astra_live_backend.py \
  local_shm_monitor/shm_port_monitor.py; do
  if [ -f "$SRC_DIR/$rel" ]; then
    cp -p "$SRC_DIR/$rel" "$HOME/$rel"
    echo "[RESTORED] ~/$rel"
  fi
done
chmod +x ~/astra_stack_boot.sh
echo "[READY] Run ~/astra_stack_boot.sh to start the 7-port stack."
