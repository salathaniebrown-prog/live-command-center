#!/data/data/com.termux/files/usr/bin/bash
sed 's/8088/18088/g' "$HOME/dashboard_server.py" > "$HOME/dashboard_18088.py"

python3 -u "$HOME/dashboard_18088.py" > "$HOME/18088-trace.log" 2>&1 &
PID=$!
sleep 2

echo "=== 1. Direct Root Check (18088) ==="
curl -s -o /dev/null -w "18088 root HTTP: %{http_code}\n" http://127.0.0.1:18088/

echo "=== 2. Proxy Route Check (/p/8090/) ==="
curl -v --max-time 5 http://127.0.0.1:18088/p/8090/ > "$HOME/18088-curl.log" 2>&1
grep -E "< HTTP|Empty reply|timed out|Connection" "$HOME/18088-curl.log"
sleep 1

kill -9 $PID 2>/dev/null
rm -f "$HOME/dashboard_18088.py"

echo "=== 3. Captured Python Traceback ==="
cat "$HOME/18088-trace.log"

echo "=== 4. _proxy Method Source ==="
grep -n -A 55 "def _proxy(" "$HOME/dashboard_server.py"
