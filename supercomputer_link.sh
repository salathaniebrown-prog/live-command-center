#!/data/data/com.termux/files/usr/bin/bash
REMOTE_HOST="${1:-100.64.0.5}"
REMOTE_USER="${2:-ubuntu}"
autossh -M 0 -o "ServerAliveInterval 15" -o "ServerAliveCountMax 3" \
  -L 8100:127.0.0.1:8100 \
  -t "${REMOTE_USER}@${REMOTE_HOST}" "tmux new-session -A -s sovereign_supercomputer"
