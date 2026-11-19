#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
pm2 resurrect
pm2 status
curl -s http://127.0.0.1:3001/v1/telemetry | jq '.status'
