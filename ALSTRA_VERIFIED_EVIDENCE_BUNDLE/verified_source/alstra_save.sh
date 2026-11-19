#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$HOME"

MSG="${1:-checkpoint(ai-fabric): verified cluster & model-training infrastructure upgrade}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
TAG="v2026.${STAMP}"

echo "=== [1/4] Running 4/4 TDD Contract Guardrails ==="
python3 "$HOME/astra_tdd_guardrails.py"

echo "=== [2/4] Recording Cryptographic State & Port Manifest ==="
curl -s http://127.0.0.1:8090/v1/cluster/unify > "$HOME/ALSTRA_IMMUTABLE_VAULT/state_${STAMP}.json" || true
sha256sum "$HOME"/*.py "$HOME"/*.sh "$HOME"/gnmi_observability_stack/grafana/provisioning/dashboards/*.json 2>/dev/null > "$HOME/ALSTRA_IMMUTABLE_VAULT/manifest_${STAMP}.sha256"

echo "=== [3/4] Committing & Tagging Immutable Milestone ($TAG) ==="
git add -A
git commit -m "$MSG [$TAG]" || echo "[i] Working tree already clean"
git tag -a "$TAG" -m "$MSG"

echo "=== [4/4] Pushing Branch & Permanent Tag to GitHub ==="
git push origin main
git push origin "$TAG"

echo "[✔] PERMANENTLY SAVED & TAGGED: $TAG -> https://github.com/salathaniebrown-prog/live-command-center/releases/tag/$TAG"
