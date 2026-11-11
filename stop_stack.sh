#!/usr/bin/env bash
echo "[*] Terminating all background infrastructure processes..."
fuser -k 3001/tcp 8888/tcp 2>/dev/null
pkill -f server_bridge.py
pkill -f injector.sh
nginx -s stop 2>/dev/null
echo "\033[1;31m[-] Multi-process network stack offline.\033[0m"
