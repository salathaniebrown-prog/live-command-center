#!/usr/bin/env bash
set -uo pipefail

MIN_RAM_MIB=520.0
mkdir -p ~/tmp

avail_mib() { awk '/^MemAvailable:/ {printf "%.1f", $2/1024}' /proc/meminfo; }
ram_ok() { awk -v floor="$MIN_RAM_MIB" '/^MemAvailable:/ {exit !($2/1024 >= floor)}' /proc/meminfo; }
port_up() { local rc=0; curl -sS --connect-timeout 0.3 --max-time 0.8 "http://127.0.0.1:$1/" >/dev/null 2>&1 || rc=$?; [ "$rc" -ne 7 ]; }

if ! pgrep -f "astra_ram70.py" >/dev/null 2>&1 && [ -f ~/astra_ram70.py ]; then
  nohup python3 ~/astra_ram70.py >>~/tmp/astra_ram70.log 2>&1 </dev/null &
  echo "[START] astra_ram70.py watchdog"
fi

start_svc() {
  local port="$1" script="$2" workdir="$3" logf="$4"
  if port_up "$port"; then echo "  [OK] :$port already listening"; return 0; fi
  [ -f "$script" ] || { echo "  [MISS] :$port ($script)"; return 0; }
  if ! ram_ok; then echo "  [HOLD] :$port skipped ($(avail_mib) MiB < $MIN_RAM_MIB MiB)"; return 0; fi
  printf '\n=== BOOT %s ===\n' "$(date +%H:%M:%S)" >> "$logf"
  (cd "$workdir" && nohup python3 -u "$script" >>"$logf" 2>&1 </dev/null &)
  for _ in $(seq 1 18); do port_up "$port" && break; sleep 0.3; done
  echo "  [START] :$port $(basename "$script") up=$(port_up "$port" && echo true || echo false) (free=$(avail_mib) MiB)"
}

assist=~/astra-enterprise-core/astra-reverse-supercomputer/telemetry_assistant.py
[ -f "$assist" ] || assist=~/live-command-center/astra-reverse-supercomputer/telemetry_assistant.py

echo "=== ASTRA + ALSTRA 7-PORT BOOT (free=$(avail_mib) MiB, floor=${MIN_RAM_MIB} MiB) ==="
start_svc 8088 ~/dashboard_server.py ~ ~/dashboard.log
start_svc 8095 ~/alstra_master_spine_8095.py ~ ~/tmp/spine_8095.log
start_svc 8099 ~/alstra_genius_brain_8099.py ~ ~/tmp/brain_8099.log
start_svc 8110 "$assist" "$(dirname "$assist")" ~/telemetry_assistant.log
start_svc 8125 ~/tmp/astra_live_backend.py ~ ~/astra_live_backend.log
start_svc 8170 ~/local_shm_monitor/shm_port_monitor.py ~/local_shm_monitor ~/local_shm_monitor/shm_8170.log

echo "=== 7-PORT HEALTH CHECK (free=$(avail_mib) MiB) ==="
for u in \
  http://127.0.0.1:8088/api/telemetry/chronicle \
  http://127.0.0.1:8090/api/telemetry/chronicle \
  http://127.0.0.1:8095/ \
  http://127.0.0.1:8099/ \
  http://127.0.0.1:8110/api/telemetry/status \
  http://127.0.0.1:8125/api/telemetry/iot-process \
  http://127.0.0.1:8170/; do
  code=$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' "$u" 2>/dev/null || true)
  printf "  %-46s -> HTTP %s\n" "$u" "${code:-000}"
done
