#!/data/data/com.termux/files/usr/bin/bash
set -e
REPO_DIR="${1:-$HOME/live-command-center}"
mkdir -p "$REPO_DIR/core3d" "$REPO_DIR/.github/workflows"
cp "$HOME/astra_shm_schema.py" "$HOME/astra_ingress_8088.py" "$HOME/astra_chaos_bench.py" \
   "$HOME/astra_core3d_hud.html" "$HOME/astra_rt_bootstrap.sh" "$HOME/launch_core3d_cockpit.sh" \
   "$REPO_DIR/core3d/"
cp "$HOME/astra_core3d_hud.html" "$REPO_DIR/core3d/index.html"
cd "$REPO_DIR"
if [ -d ".git" ]; then
  git add core3d/ .github/workflows/astra-core3d-ci.yml
  git commit -m "ASTRA Core3D: Chaos Benchmark + GitHub CI/CD Release Bundle" || true
  git push origin HEAD || echo "[!] Push skipped (check remote/auth)"
else
  echo "[✔] Staged Core3D + CI bundle in $REPO_DIR"
fi
