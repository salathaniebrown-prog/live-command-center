#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${EAGLE_EYES_HOME:-$SCRIPT_DIR}"
COMPOSE_FILE="${TARGET_DIR}/deployment-center.yml"
SERVICE="command-hub"
LOCAL_BASE_URL="${EAGLE_EYES_LOCAL_URL:-http://127.0.0.1:8080}"

cd "$TARGET_DIR"

have() { command -v "$1" >/dev/null 2>&1; }
separator() { printf '%s\n' '--------------------------------------------------------------------------'; }
pause_deck() { printf '\n'; read -r -p 'Press Enter to return to Command Center...' _; }

require_file() {
  [[ -f "$1" ]] || { echo "❌ Required file missing: $1"; return 1; }
}

require_docker() {
  have docker || { echo '❌ Docker is not available in PATH.'; return 1; }
  docker compose version >/dev/null 2>&1 || { echo '❌ Docker Compose v2 is unavailable.'; return 1; }
  docker info >/dev/null 2>&1 || { echo '❌ Docker daemon is not reachable.'; return 1; }
}

show_header() {
  clear || true
  echo '=========================================================================='
  echo ' 🦅 EAGLE EYES COMMAND DEPLOYMENT CENTER'
  echo ' SYSTEM OPERATIONS INNER CORE'
  echo " Current System Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo " Repository Root:     $TARGET_DIR"
  echo '=========================================================================='
  echo ' 1) [VALIDATE]  Run repository CI + deployment configuration checks'
  echo ' 2) [DEPLOY]    Build/start the local production Compose stack'
  echo ' 3) [STATUS]    Show command-hub container state and published ports'
  echo ' 4) [HEALTH]    Probe the local health + Deployment Center APIs'
  echo ' 5) [REVISION]  Verify an exact deployed Railway URL + Git SHA'
  echo ' 6) [MOBILE]    Build the standalone Android release APK locally'
  echo ' 7) [STREAM]    Follow live command-hub container logs'
  echo ' 8) [HALT]      Stop the local Compose stack (volumes preserved)'
  echo ' 9) [EXIT]      Disconnect shell control path'
  echo '=========================================================================='
}

validate_stack() {
  echo; echo '🧪 Running Eagle Eyes validation gate...'; separator
  require_file "$COMPOSE_FILE" || return
  have node || { echo '❌ Node.js is required.'; return 1; }
  have npm || { echo '❌ npm is required.'; return 1; }
  npm run ci
  require_docker || return
  docker compose -f "$COMPOSE_FILE" config --quiet
  echo '✅ Repository CI and Compose configuration passed.'
}

deploy_stack() {
  echo; echo '⚡ Running the repository deployment orchestration...'; separator
  require_file "${TARGET_DIR}/deploy.sh" || return
  "${TARGET_DIR}/deploy.sh"
}

show_status() {
  echo; echo '📦 Active Eagle Eyes container state'; separator
  require_docker || return
  docker compose -f "$COMPOSE_FILE" ps
}

probe_health() {
  echo; echo '🩺 Local Eagle Eyes health matrix'; separator
  have curl || { echo '❌ curl is required for API health probing.'; return 1; }

  local health deployment center
  health="$(curl --fail --silent --show-error --max-time 10 "$LOCAL_BASE_URL/api/health")" || return 1
  deployment="$(curl --fail --silent --show-error --max-time 10 "$LOCAL_BASE_URL/api/deployment")" || return 1
  center="$(curl --fail --silent --show-error --max-time 10 "$LOCAL_BASE_URL/api/deployment-center/status")" || return 1

  echo "Health:            $health"
  echo "Deployment:        $deployment"
  echo "Deployment Center: $center"
  echo '✅ Local API probes completed.'
}

verify_revision() {
  echo; echo '🔐 Exact deployed revision verification'; separator
  require_file "${TARGET_DIR}/scripts/verify-deployed-revision.py" || return
  have python3 || { echo '❌ python3 is required.'; return 1; }
  have git || { echo '❌ git is required.'; return 1; }

  local default_sha url sha
  default_sha="$(git -C "$TARGET_DIR" rev-parse HEAD 2>/dev/null || true)"
  read -r -p 'Railway base URL (https://...): ' url
  [[ -n "$url" ]] || { echo '❌ Railway URL is required.'; return 1; }

  if [[ -n "$default_sha" ]]; then
    read -r -p "Expected Git SHA [$default_sha]: " sha
    sha="${sha:-$default_sha}"
  else
    read -r -p 'Expected Git SHA: ' sha
  fi
  [[ -n "$sha" ]] || { echo '❌ Git SHA is required.'; return 1; }

  python3 "${TARGET_DIR}/scripts/verify-deployed-revision.py" --url "$url" --sha "$sha"
}

build_mobile() {
  echo; echo '📱 Building Eagle Eyes standalone Android release APK...'; separator
  local mobile_dir="${TARGET_DIR}/clients/mobile"
  require_file "${mobile_dir}/package.json" || return
  have npm || { echo '❌ npm is required.'; return 1; }
  have java || { echo '❌ Java 17+ is required.'; return 1; }

  (
    cd "$mobile_dir"
    npm ci --no-audit --no-fund
    CI=1 EXPO_NO_TELEMETRY=1 npx expo prebuild --platform android --non-interactive
    cd android
    chmod +x gradlew
    CI=1 EXPO_NO_TELEMETRY=1 ./gradlew assembleRelease
  )

  local apk="${mobile_dir}/android/app/build/outputs/apk/release/app-release.apk"
  [[ -f "$apk" ]] || { echo "❌ APK build finished without expected artifact: $apk"; return 1; }
  echo "✅ APK ready: $apk"
}

stream_logs() {
  echo; echo '📡 Streaming command-hub logs (Ctrl+C to stop)...'; separator
  require_docker || return
  docker compose -f "$COMPOSE_FILE" logs --tail=50 --follow "$SERVICE"
}

halt_stack() {
  echo; echo '⚠️ Stop Eagle Eyes local Compose stack'; separator
  require_docker || return
  read -r -p 'Stop command-hub and remove its Compose network? Volumes stay intact [y/N]: ' confirm
  case "$confirm" in
    y|Y|yes|YES)
      docker compose -f "$COMPOSE_FILE" down --remove-orphans
      echo '✅ Local Compose stack stopped. Named volumes were preserved.'
      ;;
    *) echo 'Shutdown cancelled.' ;;
  esac
}

while true; do
  show_header
  read -r -p 'Select Target Operational Matrix Path [1-9]: ' choice
  case "$choice" in
    1) validate_stack; pause_deck ;;
    2) deploy_stack; pause_deck ;;
    3) show_status; pause_deck ;;
    4) probe_health; pause_deck ;;
    5) verify_revision; pause_deck ;;
    6) build_mobile; pause_deck ;;
    7) stream_logs; pause_deck ;;
    8) halt_stack; pause_deck ;;
    9) echo; echo '🦅 Eagle Eyes Command Center disconnected.'; exit 0 ;;
    *) echo; echo "❌ Invalid operational route: '$choice'"; sleep 1 ;;
  esac
done
