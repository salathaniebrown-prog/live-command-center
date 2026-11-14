#!/data/data/com.termux/files/usr/bin/bash
pkill -f "cloudflared tunnel" || true
rm -f "$HOME/tunnel.log"
nohup cloudflared tunnel --edge-ip-version 4 --protocol http2 --url http://127.0.0.1:8088 > "$HOME/tunnel.log" 2>&1 &
disown
sleep 8

python3 -c '
import os, time, urllib.request
log_path = os.path.expanduser("~/tunnel.log")
text = open(log_path, errors="ignore").read()
urls = [w.strip("| ") for w in text.split() if "trycloudflare.com" in w]
if not urls:
    print(text)
else:
    live_url = urls.pop()
    print("[✔] LIVE IPV4 HTTP2 URL:", live_url)
    for i in range(1, 5):
        try:
            req = urllib.request.Request(live_url, headers={"User-Agent": "AstraWatchdog/1.0"})
            print("[✔] EXTERNAL HTTP STATUS:", urllib.request.urlopen(req, timeout=10).status)
            break
        except Exception as e:
            print(f"[...] Waiting for edge route ({i}/4): {e}")
            time.sleep(3)
'
