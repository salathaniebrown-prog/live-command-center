#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$HOME/live-command-center"
MSG="${1:-feat: verified incremental upgrade}"
BRANCH="upgrade/auto-$(date +%Y%m%d-%H%M%S)"

echo "=== [1/4] RUNNING CODE VACUUM & ZERO-ERROR SYNTAX GATE ==="
python3 "$HOME/live-command-center/code_vacuum_recycler.py"
[ -f "$HOME/live-command-center/tdd_error_gate.py" ] && python3 "$HOME/live-command-center/tdd_error_gate.py"

echo "=== [2/4] STAGING ON PROTECTED BRANCH: $BRANCH ==="
git checkout -B "$BRANCH"
git add -A
git diff --cached --quiet || git commit -m "$MSG"

echo "=== [3/4] PROMOTING VERIFIED UPGRADE TO MAIN ==="
if [ -x "./protect_main.sh" ]; then
  bash ./protect_main.sh promote
else
  git checkout main
  git merge --no-ff "$BRANCH" -m "promote: $MSG"
fi

echo "=== [4/4] PUSHING GOLDEN MAIN TO GITHUB ==="
git push -u origin main
echo "[✔] SHIPPED & VERIFIED ON MAIN"
