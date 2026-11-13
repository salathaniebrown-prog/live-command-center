#!/data/data/com.termux/files/usr/bin/bash
pkill -f "cloudflared tunnel" || true
rm -f "$HOME/tunnel.log"
setsid nohup cloudflared tunnel --url http://127.0.0.1:8088 > "$HOME/tunnel.log" 2>&1 < /dev/null &
sleep 6

python3 -c '
import os
log_path = os.path.expanduser("~/tunnel.log")
if os.path.exists(log_path):
    text = open(log_path, errors="ignore").read()
    urls = [w.strip("| ") for w in text.split() if "trycloudflare.com" in w]
    if urls:
        print("[✔] LIVE EXTERNAL URL:", urls.pop())
    else:
        print("[!] Tunnel initializing. Log output:")
        print(text)
'
