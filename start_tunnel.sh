#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock >/dev/null 2>&1 || true
pkill -f "cloudflared tunnel" || true
pkill -f "astra_tunnel_supervisor" || true
rm -f "$HOME/tunnel.log"

nohup bash -c '
exec -a astra_tunnel_supervisor bash -c "
while true; do
  cloudflared tunnel --config \"$HOME/.cloudflared/config.yml\" run astra-command-center >> \"$HOME/tunnel.log\" 2>&1
  sleep 3
done
"' >/dev/null 2>&1 &
disown
sleep 6
tail -n 12 "$HOME/tunnel.log"
