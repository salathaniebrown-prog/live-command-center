#!/data/data/com.termux/files/usr/bin/bash
set -e
VAULT="$HOME/ASTRA_IMMUTABLE_VAULT"
mkdir -p "$VAULT"
TS=$(date +%Y%m%d_%H%M%S)
SNAP="$VAULT/astra_golden_${TS}.tar.gz"

tar -czf "$SNAP" \
  -C "$HOME" \
  dashboard_server.py dashboard.py vserver.py orbital_crypto_spine.py \
  astra_provisioner_8143.py astra_sentinel_8165.py astra_shm_schema.py \
  astra_core3d_hud.html alstra_unified_8090_gateway.py \
  astra_blueprints astra_deploy_blueprint 2>/dev/null || true

sha256sum "$SNAP" > "${SNAP}.sha256"
chmod 444 "$SNAP" "${SNAP}.sha256"
echo "[✔] IMMUTABLE SNAPSHOT LOCKED: $SNAP"
cat "${SNAP}.sha256"
