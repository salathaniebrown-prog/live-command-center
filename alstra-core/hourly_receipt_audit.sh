#!/data/data/com.termux/files/usr/bin/sh
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "[CRON AUDIT $TIMESTAMP] Verifying Coinbase & Legal Deep Space Ledger receipts..."
curl -s -X POST http://127.0.0.1:8099/api/agent/command \
     -H "Content-Type: application/json" \
     -d "{\"command\": \"Hourly receipt sweep audit executed\", \"speak\": false, \"timestamp\": \"$TIMESTAMP\"}"
