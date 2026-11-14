#!/data/data/com.termux/files/usr/bin/bash
pkill -f "cloudflared tunnel" || true
rm -f "$HOME/tunnel.log"
nohup cloudflared tunnel --config "$HOME/.cloudflared/config.yml" run astra-command-center > "$HOME/tunnel.log" 2>&1 &
disown
sleep 5
tail -n 10 "$HOME/tunnel.log"
