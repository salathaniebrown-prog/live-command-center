#!/data/data/com.termux/files/usr/bin/bash
echo "=== 1. Process holding port 8088 ==="
ps -ef | grep -E "8088|dashboard_server" | grep -v grep

echo "=== 2. Exact _proxy definition ==="
PROXY_LINE=$(grep -n "def _proxy(" "$HOME/dashboard_server.py" | cut -d: -f1)
echo "_proxy starts at line: $PROXY_LINE"
if [ -n "$PROXY_LINE" ]; then
  sed -n "${PROXY_LINE},$((PROXY_LINE + 65))p" "$HOME/dashboard_server.py"
fi

echo "=== 3. Stop existing 8088 owner & test /p/8090/ ==="
pm2 stop astra-8088-main 2>/dev/null
fuser -k 8088/tcp 2>/dev/null || pkill -9 -f "dashboard_server.py" 2>/dev/null
sleep 1

python3 -u "$HOME/dashboard_server.py" > "$HOME/8088-real-crash.log" 2>&1 &
TEST_PID=$!
sleep 2

curl -v --max-time 5 http://127.0.0.1:8088/p/8090/ > "$HOME/8088-curl-trace.log" 2>&1
sleep 1
kill -9 $TEST_PID 2>/dev/null

echo "=== 4. Real Python Traceback ==="
cat "$HOME/8088-real-crash.log"
