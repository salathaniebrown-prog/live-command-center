#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
REPO="/data/data/com.termux/files/home/live-command-center"
cd "$REPO"

CMD="${1:-verify}"

verify_all() {
  echo "[SHIELD] Auditing Python syntax across repo..."
  python3 - << 'PY'
import json, py_compile, sys
from pathlib import Path

bad = []
for f in sorted(Path(".").glob("*.py")):
    try:
        py_compile.compile(str(f), doraise=True)
    except Exception as e:
        bad.append(f"PY FAIL: {f.name} -> {e}")

for f in sorted(Path(".").glob("*.json")):
    try:
        json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        bad.append(f"JSON FAIL: {f.name} -> {e}")

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("[SHIELD OK] Zero Python or JSON errors.")
PY
}

case "$CMD" in
  branch)
    NAME="${2:?Usage: ./protect_main.sh branch <upgrade-name>}"
    git checkout -b "upgrade/${NAME}"
    echo "[SHIELD] Working safely on branch upgrade/${NAME}. main is untouched."
    ;;
  verify)
    verify_all
    ;;
  promote)
    CUR="$(git rev-parse --abbrev-ref HEAD)"
    if [ "$CUR" = "main" ]; then
      echo "[SHIELD BLOCKED] Already on main. Build upgrades on an upgrade/* branch first."
      exit 1
    fi
    verify_all
    git checkout main
    git merge --no-ff "$CUR" -m "shield-promote: verified ${CUR} into main"
    git tag -f "main-verified-$(date +%Y%m%d-%H%M)"
    echo "[SHIELD] Promoted ${CUR} -> main cleanly."
    ;;
  rollback)
    LAST_TAG="$(git tag --sort=-creatordate | grep '^main-' | head -n 1)"
    echo "[SHIELD] Latest verified main tag: ${LAST_TAG}"
    echo "Run to restore without losing history: git checkout -b recovery && git reset --hard ${LAST_TAG}"
    ;;
  *)
    echo "Usage: ./protect_main.sh {branch <name>|verify|promote|rollback}"
    ;;
esac
