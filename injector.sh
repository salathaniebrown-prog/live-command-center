#!/usr/bin/env bash
# ==============================================================================
# JARVIS HARDWARE TELEMETRY DATA INJECTOR DAEMON
# Periodically reads system files and feeds metrics into the core data layer.
# ==============================================================================

BRIDGE_URL="http://127.0.0"
INTERVAL_SEC=5

while true; do
    # 1. Gather memory statistics safely
    MEM_INFO=$(cat /proc/meminfo)
    TOTAL_MEM=$(echo "$MEM_INFO" | grep MemTotal | awk '{print $2}')
    FREE_MEM=$(echo "$MEM_INFO" | grep MemFree | awk '{print $2}')
    USED_KB=$((TOTAL_MEM - FREE_MEM))
    MEM_USED_MB=$((USED_KB / 1024))

    # 2. Assemble rotating mock telemetry operations events
    CYCLE=$(( ( $(date +%s) / INTERVAL_SEC ) % 3 ))
    case $CYCLE in
        0)
            EVENT="JARVIS_CORE_OPTIMIZED"
            PAYLOAD="HUD engine pipeline synchronized. Memory cache stabilized at ${MEM_USED_MB}MB."
            FIDELITY="0.99845"
            ;;
        1)
            EVENT="MATRIX_THERMAL_CHECK"
            PAYLOAD="Core array background diagnostics checked. Thermal states stable."
            FIDELITY="0.99912"
            ;;
        2)
            EVENT="SOVEREIGN_SYNC"
            PAYLOAD="Local ledger database transaction records reconciled with active endpoints."
            FIDELITY="1.00000"
            ;;
    esac

    # 3. Fire the structured network request straight to your FastAPI bridge
    curl -s -X POST "$BRIDGE_URL" \
      -H "Content-Type: application/json" \
      -d "{
        \"event_type\": \"$EVENT\",
        \"payload\": \"$PAYLOAD\",
        \"quantum_fidelity\": $FIDELITY
      }" > /dev/null

    sleep "$INTERVAL_SEC"
done
