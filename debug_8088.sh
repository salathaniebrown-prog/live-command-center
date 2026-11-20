#!/data/data/com.termux/files/usr/bin/bash
pkill -9 -f dashboard_server.py 2>/dev/null
pm2 stop astra-8088-main 2>/dev/null
sleep 1

echo "=== _proxy implementation (lines 1580-1635) ==="
sed -n '1580,1635p' "$HOME/dashboard_server.py"

echo "=== Starting 8088 with Termux-writable log ==="
python3 -u "$HOME/dashboard_server.py" > "$HOME/8088-crash.log" 2>&1 &
PID=$!
sleep 2

curl -s -o /dev/null -w "8088 root: %{http_code}\n" http://127.0.0.1:8088/
curl -v --max-time 5 http://127.0.0.1:8088/p/8090/ > "$HOME/8088-curl.log" 2>&1
sleep 1

echo "=== Crash Log Output ==="
cat "$HOME/8088-crash.log"
