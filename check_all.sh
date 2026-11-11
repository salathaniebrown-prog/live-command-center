#!/data/data/com.termux/files/usr/bin/bash
echo "=== AI STUDIO INFINITE BRAIN STATUS ==="
for p in 8088 8095 8096 8097 8098 8099 8100; do
  if curl -sI "http://127.0.0.1:${p}" >/dev/null 2>&1 || curl -s "http://127.0.0.1:${p}/api/state" >/dev/null 2>&1 || curl -s "http://127.0.0.1:${p}/api/legal/state" >/dev/null 2>&1 || curl -s "http://127.0.0.1:${p}/api/brain/graph" >/dev/null 2>&1 || curl -s "http://127.0.0.1:${p}/api/ooda/state" >/dev/null 2>&1 || curl -s "http://127.0.0.1:${p}/api/bi/refine" >/dev/null 2>&1 || curl -s "http://127.0.0.1:${p}/api/nexus/state" >/dev/null 2>&1; then
    echo "[ONLINE]  Port ${p}"
  else
    echo "[OFFLINE] Port ${p}"
  fi
done
echo "LOCAL COMMAND CENTER : http://127.0.0.1:8088"
echo "LOCAL DEALERSHIP HUB : http://127.0.0.1:8099"
echo "EXTERNAL HTTPS TUNNEL: $(cat ~/active_tunnel_url.txt 2>/dev/null || echo 'Not started')"
