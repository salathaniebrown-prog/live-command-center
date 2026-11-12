#!/data/data/com.termux/files/usr/bin/bash
echo "=== ASTRA SOVEREIGN OS STATUS (ALL 11 PORTS + TOR) ==="
for p in 8088 8095 8096 8097 8098 8099 8100 8101 8102 8103 8104 8105 9050; do
  if python3 -c "import socket; s=socket.create_connection(('127.0.0.1', ${p}), 1); s.close()" 2>/dev/null; then
    echo "[ONLINE]  Port ${p}"
  else
    echo "[OFFLINE] Port ${p}"
  fi
done
echo "LOCAL COMMAND CENTER : http://127.0.0.1:8088"
echo "LOCAL DEALERSHIP HUB : http://127.0.0.1:8099"
echo "EXTERNAL HTTPS TUNNEL: $(cat ~/active_tunnel_url.txt 2>/dev/null || echo 'Not started')"
