#!/data/data/com.termux/files/usr/bin/bash
set -u
CORES=$(nproc 2>/dev/null || echo 4)
CORE_8088=$((CORES - 1))
CORE_8090=$((CORES > 1 ? CORES - 2 : 0))

echo "=== ASTRA RT / PINNING BOOTSTRAP (Cores: $CORES) ==="
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock && echo "[✔] Termux wake-lock acquired"

P8088=$(pgrep -f "astra_ingress_8088.py" | head -n 1)
P8090=$(pgrep -f "alstra_unified_8090_gateway.py" | head -n 1)

if command -v taskset >/dev/null 2>&1; then
  [ -n "${P8088:-}" ] && taskset -cp "$CORE_8088" "$P8088" 2>/dev/null && echo "[✔] Pinned :8088 (PID $P8088) -> Core $CORE_8088"
  [ -n "${P8090:-}" ] && taskset -cp "$CORE_8090" "$P8090" 2>/dev/null && echo "[✔] Pinned :8090 (PID $P8090) -> Core $CORE_8090"
fi

if [ "$(id -u)" -eq 0 ]; then
  echo "[*] Root detected -> applying kernel sysctl & SCHED_FIFO RT priorities"
  sysctl -w net.core.rmem_max=16777216 net.core.wmem_max=16777216 \
            net.ipv4.tcp_low_latency=1 vm.swappiness=10 2>/dev/null || true
  if command -v chrt >/dev/null 2>&1; then
    [ -n "${P8088:-}" ] && chrt -f -p 50 "$P8088" 2>/dev/null || true
    [ -n "${P8090:-}" ] && chrt -f -p 45 "$P8090" 2>/dev/null || true
  fi
else
  echo "[!] Non-root Termux shell: skipping kernel sysctl/chrt (requires root); user-space mmap + pinning active."
fi
