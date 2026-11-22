#!/data/data/com.termux/files/usr/bin/bash
REPO="/data/data/com.termux/files/home/live-command-center"
LOG="$REPO/boot_restore.log"

# Fast-path check: if Universal Pilot (:8125) is already responding, skip heavy restore
if curl -sf --max-time 1 http://127.0.0.1:8125/api/pilot/status >/dev/null 2>&1; then
  echo "[MEMORY SPINE] Stack online (:8125) — WAL ledger active."
  exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restoring SalathanieAI cross-session memory..." | tee -a "$LOG"
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
python3 "$REPO/astra_memory_spine.py" --restore >> "$LOG" 2>&1
sleep 2
if curl -sf --max-time 3 http://127.0.0.1:8125/api/pilot/status >/dev/null 2>&1; then
  echo "[MEMORY SPINE] Recovery complete — Universal Pilot (:8125) restored."
else
  echo "[MEMORY SPINE] Check $LOG for recovery details."
fi
