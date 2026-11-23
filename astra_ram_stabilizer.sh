#!/data/data/com.termux/files/usr/bin/bash

# ASTRA // ALSTRA // SALATHANIE AI - BASH RAM STABILIZER
# Direct Integration: predictive_kernel_8154.py & On-Demand Nodes (8096-8100)

TARGET_CEILING=77
CRITICAL_CEILING=82
POLL_INTERVAL=2

STATE_FILE="$HOME/.astra_ram_state.dat"
LOG_FILE="$HOME/astra_ram_stabilizer.log"

MANAGED_NODES=("node_8096.py" "node_8097.py" "node_8098.py" "node_8100.py")
CORE_KERNEL="predictive_kernel_8154.py"

# Initialize persistent state counters
CYCLES=0
RECLAIMED_TOTAL=0
[ -f "$STATE_FILE" ] && source "$STATE_FILE"

save_state() {
    cat << STATE > "$STATE_FILE"
CYCLES=$CYCLES
RECLAIMED_TOTAL=$RECLAIMED_TOTAL
STATE
}

cleanup() {
    save_state
    tput cnorm
    echo -e "\n[ASTRA STABILIZER] State persisted to $STATE_FILE. Exiting cleanly."
    exit 0
}
trap cleanup SIGINT SIGTERM

get_mem_stats() {
    MEM_TOTAL_KB=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
    MEM_AVAIL_KB=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    [ -z "$MEM_AVAIL_KB" ] && MEM_AVAIL_KB=$(awk '/^MemFree:/ {print $2}' /proc/meminfo)

    MEM_USED_KB=$((MEM_TOTAL_KB - MEM_AVAIL_KB))
    MEM_TOTAL_MB=$((MEM_TOTAL_KB / 1024))
    MEM_USED_MB=$((MEM_USED_KB / 1024))
    MEM_AVAIL_MB=$((MEM_AVAIL_KB / 1024))
    MEM_PCT=$(( (MEM_USED_KB * 100) / MEM_TOTAL_KB ))
}

stabilize_nodes() {
    local mode="$1"
    local before_mb=$MEM_AVAIL_MB
    local action_log=""

    # 1. Drop kernel caches if root is active
    if [ "$(id -u)" -eq 0 ]; then
        sync
        echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
    fi

    # 2. Enforce ceiling across on-demand worker stubs while shielding port 8154
    for node in "${MANAGED_NODES[@]}"; do
        PID=$(pgrep -f "$node" | head -n 1)
        if [ -n "$PID" ]; then
            if [ "$mode" == "CRITICAL" ]; then
                # Trigger clean hibernation shutdown on idle/excess nodes
                kill -TERM "$PID" 2>/dev/null
                action_log="$action_log [HIBERNATED:$node]"
            elif [ "$mode" == "TARGET" ]; then
                # Signal node to flush buffers / compact state
                kill -USR1 "$PID" 2>/dev/null
                action_log="$action_log [COMPACTED:$node]"
            fi
        fi
    done

    sleep 0.5
    get_mem_stats
    local reclaimed=$((MEM_AVAIL_MB - before_mb))
    [ "$reclaimed" -lt 0 ] && reclaimed=0

    CYCLES=$((CYCLES + 1))
    RECLAIMED_TOTAL=$((RECLAIMED_TOTAL + reclaimed))
    save_state

    STATUS_MSG="$mode CEILING -> +${reclaimed}MB freed${action_log}"
    echo "CYCLE=$CYCLES | PCT=${MEM_PCT}% | RECLAIMED=+${reclaimed}MB | $STATUS_MSG" >> "$LOG_FILE"
}

draw_bar() {
    local pct=$1
    local width=32
    local filled=$(( (pct * width) / 100 ))
    local empty=$((width - filled))
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
}

tput civis
while true; do
    get_mem_stats

    KERNEL_PID=$(pgrep -f "$CORE_KERNEL" | head -n 1)
    [ -n "$KERNEL_PID" ] && KERNEL_STAT="ONLINE (PID $KERNEL_PID)" || KERNEL_STAT="STANDBY / OFFLINE"

    if [ "$MEM_PCT" -ge "$CRITICAL_CEILING" ]; then
        stabilize_nodes "CRITICAL"
    elif [ "$MEM_PCT" -ge "$TARGET_CEILING" ]; then
        stabilize_nodes "TARGET"
    else
        STATUS_MSG="NOMINAL -> Memory ceiling locked under ${TARGET_CEILING}%"
    fi

    # Single-screen zero-scroll HUD
    printf "\033[2J\033[H"
    echo "=================================================================="
    echo " ASTRA // ALSTRA // SALATHANIE AI - BASH RAM STABILIZER (TERMUX)  "
    echo "=================================================================="
    printf " RAM LOAD    : [%s] %d%%\n" "$(draw_bar "$MEM_PCT")" "$MEM_PCT"
    printf " MEMORY POOL : %d MB Used / %d MB Total (%d MB Free)\n" "$MEM_USED_MB" "$MEM_TOTAL_MB" "$MEM_AVAIL_MB"
    printf " KERNEL 8154 : %s\n" "$KERNEL_STAT"
    printf " STABILIZER  : Cycles: %d | Total Reclaimed: %d MB\n" "$CYCLES" "$RECLAIMED_TOTAL"
    echo "------------------------------------------------------------------"
    echo " ACTIVE WORKER NODES (8096 - 8100):"
    for node in "${MANAGED_NODES[@]}"; do
        NPID=$(pgrep -f "$node" | head -n 1)
        if [ -n "$NPID" ]; then
            NRSS=$(awk '/VmRSS:/ {print int($2/1024)" MB"}' /proc/"$NPID"/status 2>/dev/null)
            printf "  • %-14s : ACTIVE (PID %-6s | RSS: %s)\n" "$node" "$NPID" "${NRSS:-N/A}"
        else
            printf "  • %-14s : HIBERNATING (0 MB)\n" "$node"
        fi
    done
    echo "------------------------------------------------------------------"
    printf " STATUS: %s\n" "$STATUS_MSG"
    echo "=================================================================="

    sleep "$POLL_INTERVAL"
done
