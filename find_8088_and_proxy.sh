#!/data/data/com.termux/files/usr/bin/bash
echo "=== 1. Exact PID holding port 8088 (hex 1F98) ==="
INODE=$(awk '$2 ~ /:1F98$/ {print $10}' /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -n 1)
echo "Socket inode: ${INODE:-NONE}"
if [ -n "$INODE" ]; then
  for fd in /proc/[0-9]*/fd/*; do
    if readlink "$fd" 2>/dev/null | grep -q "socket:\[$INODE\]"; then
      PID=$(echo "$fd" | cut -d/ -f3)
      echo "Owner PID: $PID -> $(tr '\0' ' ' < /proc/$PID/cmdline)"
    fi
  done
fi
pm2 jlist 2>/dev/null | python3 -c "import sys,json; [print(p['name'], p['pid'], p['pm2_env']['pm_exec_path']) for p in json.load(sys.stdin) if '8088' in str(p)]" 2>/dev/null

echo "=== 2. _proxy code (lines around def _proxy) ==="
grep -n -A 55 "def _proxy(" "$HOME/dashboard_server.py"
