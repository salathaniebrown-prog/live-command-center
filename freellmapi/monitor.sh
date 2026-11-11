#!/usr/bin/env bash
# ==============================================================================
# SOVEREIGN HARDWARE TELEMETRY CORE DASHBOARD
# Displays real-time hardware status metrics natively inside Termux.
# ==============================================================================

# High-fidelity cybernetic ANSI styling definitions
BG_BLACK="\033[40m"
TEXT_WHITE="\033[1;37m"
BORDER_CYAN="\033[1;36m"
VAL_GREEN="\033[1;32m"
ALERT_RED="\033[1;31m"
RESET="\033[0m"

# Track baseline telemetry logs
LOG_FILE="/tmp/telemetry_clean.log"
touch "$LOG_FILE"

# Persistent execution engine loop
while true; do
    # Clear the layout frame for a flicker-free visual reload
    clear
    
    # ── 1. GATHER SYSTEM METRICS NATIVELY ─────────────────────────────────────
    # CPU Frequency Evaluation (Termux android native node translation)
    CPU_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "0")
    if [ "$CPU_FREQ" -gt 0 ]; then
        CPU_GHZ=$(awk "BEGIN {print $CPU_FREQ/1000000}")
    else
        CPU_GHZ="UNKNOWN"
    fi

    # Read RAM statistics
    MEM_INFO=$(cat /proc/meminfo)
    TOTAL_MEM=$(echo "$MEM_INFO" | grep MemTotal | awk '{print $2}')
    FREE_MEM=$(echo "$MEM_INFO" | grep MemFree | awk '{print $2}')
    BUFFERS=$(echo "$MEM_INFO" | grep Buffers | awk '{print $2}')
    CACHED=$(echo "$MEM_INFO" | grep -w Cached | awk '{print $2}')
    USED_MEM=$((TOTAL_MEM - FREE_MEM - BUFFERS - CACHED))
    
    MEM_USED_MB=$((USED_MEM / 1024))
    MEM_TOTAL_MB=$((TOTAL_MEM / 1024))
    
    # Calculate disk allocation metrics
    DISK_USAGE=$(df -h /data 2>/dev/null | tail -n 1 | awk '{print $5}' | tr -d '%')
    [ -z "$DISK_USAGE" ] && DISK_USAGE="0"

    # Evaluate battery thermal status (Android hardware translation layer)
    BATT_TEMP=$(termux-battery-status 2>/dev/null | grep -i temperature | awk -F: '{print $2}' | tr -d ' ,')
    if [ -z "$BATT_TEMP" ]; then
        BATT_TEMP="N/A"
    else
        BATT_TEMP=$(awk "BEGIN {print $BATT_TEMP/10}")"°C"
    fi

    # ── 2. RENDER THE INTERACTIVE LIVE MONITOR WIDGET ─────────────────────────
    echo -e "${BORDER_CYAN}+---------------------------------------------------------------+${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE}   NEXUS-BROWN COMMAND CENTER V13 - LOCAL HARDWARE MONITORING  ${BORDER_CYAN}|${RESET}"
    echo -e "${BORDER_CYAN}+---------------------------------------------------------------+${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} RUNTIME SYSTEM ENGINE:${RESET} NATIVE TERMUX ENVIRONMENT           ${BORDER_CYAN}|${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} DATA INTEGRITY ENGINE:${RESET} ETH MEMPOOL PERSISTENCE ACTIVE     ${BORDER_CYAN}|${RESET}"
    echo -e "${BORDER_CYAN}+---------------------------------------------------------------+${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} METRIC PROFILE        | VALUE                                  ${BORDER_CYAN}|${RESET}"
    echo -e "${BORDER_CYAN}+----------------------+----------------------------------------+${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} Core CPU Frequency    | ${VAL_GREEN}${CPU_GHZ} GHz${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} Active Memory Loading | ${VAL_GREEN}${MEM_USED_MB} MB / ${MEM_TOTAL_MB} MB${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} Telemetry Disk Usage  | ${VAL_GREEN}${DISK_USAGE}% Capacity${RESET}"
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} Thermal Core Array    | ${VAL_GREEN}${BATT_TEMP}${RESET}"
    echo -e "${BORDER_CYAN}+---------------------------------------------------------------+${RESET}"
    
    # ── 3. VISUAL STATUS CHECK AND REAL-TIME LOG OVERVIEW ────────────────────
    echo -e "${BORDER_CYAN}|${TEXT_WHITE} RECENT TELEMETRY RECORD LEDGER EVENTS:                         ${BORDER_CYAN}|${RESET}"
    echo -e "${BORDER_CYAN}+---------------------------------------------------------------+${RESET}"
    if [ -s "$LOG_FILE" ]; then
        tail -n 4 "$LOG_FILE" | while read -r line; do
            printf "${BORDER_CYAN}|${RESET} %-61s ${BORDER_CYAN}|\n" "$line"
        done
    else
        printf "${BORDER_CYAN}|${RESET} %-61s ${BORDER_CYAN}|\n" "System ledger idle. Awaiting operational telemetry payload..."
    fi
    echo -e "${BORDER_CYAN}+---------------------------------------------------------------+${RESET}"
    
    # Refresh rate limit window
    sleep 1
done
