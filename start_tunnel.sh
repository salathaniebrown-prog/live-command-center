#!/data/data/com.termux/files/usr/bin/bash
pkill -f "cloudflared tunnel" || true
rm -f ~/cloudflared.log
setsid nohup cloudflared tunnel --protocol http2 --url http://127.0.0.1:8088 > ~/cloudflared.log 2>&1 < /dev/null &
sleep 5
TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' ~/cloudflared.log | head -n 1)
echo "$TUNNEL_URL" > ~/active_tunnel_url.txt
echo "[LIVE HTTP2 TUNNEL]: ${TUNNEL_URL}"
