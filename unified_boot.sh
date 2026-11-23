#!/data/data/com.termux/files/usr/bin/bash
set -e
REPO="/data/data/com.termux/files/home/live-command-center"
cd "$REPO"

echo "[1/4] Refreshing unified folder profile..."
python3 "$REPO/unified_profile_builder.py"

echo "[2/4] Clearing errored/crash-looping PM2 entries (preserving online non-conflicting workers)..."
python3 - << 'PY'
import json, subprocess
r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=6)
if r.returncode == 0 and r.stdout.strip().startswith("["):
    for p in json.loads(r.stdout):
        nm = p.get("name", "")
        env = p.get("pm2_env") or {}
        st = env.get("status", "")
        rst = int(env.get("restart_time", 0) or 0)
        if nm and (st == "errored" or rst > 100):
            subprocess.run(["pm2", "delete", nm], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  [CLEANED] {nm} (status={st}, restarts={rst})")
PY

for old in astra-8088-main astra-8090-gw astra-8095-spine; do pm2 delete "$old" 2>/dev/null || true; done
echo "[3/4] Starting RAM-safe Unified Core Tier..."
pm2 startOrReload "$REPO/salathanie_unified_ecosystem.config.cjs" --update-env
pm2 save --force
mkdir -p "$HOME/.astra_vault"
cp "$HOME/.pm2/dump.pm2" "$HOME/.astra_vault/dump_GOLDEN.pm2"
sleep 2

echo "[4/4] Health & RAM Verification:"
python3 -c 'import ecosystem_router as e; print(f"HOST RAM -> {e._ram_pct()}% (Guard: {e.RAM_GUARD_PCT}%)")'
for u in \
  "http://127.0.0.1:8088/" \
  "http://127.0.0.1:8090/ecosystem" \
  "http://127.0.0.1:8090/flying-car" \
  "http://127.0.0.1:8090/avatars" \
  "http://127.0.0.1:8132/"; do
  printf "  %-36s -> HTTP %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$u" || echo 000)"
done
