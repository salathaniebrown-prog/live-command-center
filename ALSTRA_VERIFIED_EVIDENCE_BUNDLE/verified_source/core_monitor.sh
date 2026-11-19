#!/data/data/com.termux/files/usr/bin/bash

CORE_SCRIPT="$HOME/core_engine.py"
LOG_FILE="$HOME/core_runtime.log"

while true; do
    if ! pgrep -f "python3 $CORE_SCRIPT" > /dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [MONITOR] Core offline. Restoring loop..." >> "$LOG_FILE"
        python3 "$CORE_SCRIPT" >> "$LOG_FILE" 2>&1 &
    fi
    sleep 5
done
