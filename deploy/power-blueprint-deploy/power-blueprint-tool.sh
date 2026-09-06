#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${POWER_BLUEPRINT_LOG_FILE:-/var/log/power-blueprint-deployer.log}"

usage() {
  cat <<'EOF'
Power Blueprint operator tool

Usage:
  ./power-blueprint-tool.sh check
  ./power-blueprint-tool.sh env-status
  ./power-blueprint-tool.sh download-map-data [output-file]
  ./power-blueprint-tool.sh deploy
  ./power-blueprint-tool.sh cleanup-review

Runtime environment variables:
  MAPTILER_DATA_URL       Signed/private download URL. Never commit its value.
  H_TOKEN                 Deployment token consumed by deploy_script.py.
  SLACK_WEBHOOK_URL       Optional deployment notification webhook.
  DEPLOY_SCRIPT           Deployment script path (default: /app/deploy_script.py).
  POWER_BLUEPRINT_LOG_FILE Log path (default: /var/log/power-blueprint-deployer.log).
  REVIEW_FILE             File removed only by the cleanup-review command.
EOF
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Required environment variable is not set: ${name}" >&2
    exit 2
  fi
}

check() {
  command -v node >/dev/null 2>&1 || { echo "node is required" >&2; exit 2; }
  node --check "${ROOT_DIR}/server.js"
  node -e "JSON.parse(require('fs').readFileSync('${ROOT_DIR}/package.json','utf8')); console.log('package.json: valid')"
  bash -n "${ROOT_DIR}/power-blueprint-tool.sh"
  echo "Power Blueprint checks passed."
}

env_status() {
  for name in MAPTILER_DATA_URL H_TOKEN SLACK_WEBHOOK_URL REVIEW_FILE; do
    if [[ -n "${!name:-}" ]]; then
      echo "${name}=SET"
    else
      echo "${name}=NOT_SET"
    fi
  done
}

download_map_data() {
  require_env MAPTILER_DATA_URL
  command -v wget >/dev/null 2>&1 || { echo "wget is required" >&2; exit 2; }
  local output="${1:-maptiler-geocoding-index.tar.gz}"
  wget -c -- "${MAPTILER_DATA_URL}" -O "${output}"
}

deploy() {
  require_env H_TOKEN
  local script="${DEPLOY_SCRIPT:-/app/deploy_script.py}"
  [[ -f "${script}" ]] || { echo "Deployment script not found: ${script}" >&2; exit 2; }
  command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 2; }

  mkdir -p "$(dirname "${LOG_FILE}")"
  echo "Starting Power Blueprint deployment; output -> ${LOG_FILE}"
  /usr/bin/python3 "${script}" >> "${LOG_FILE}" 2>&1
  echo "Deployment command completed."
}

cleanup_review() {
  require_env REVIEW_FILE
  if [[ "${REVIEW_FILE}" == "/" || -d "${REVIEW_FILE}" ]]; then
    echo "Refusing unsafe REVIEW_FILE target: ${REVIEW_FILE}" >&2
    exit 2
  fi
  rm -f -- "${REVIEW_FILE}"
  echo "Review file removed: ${REVIEW_FILE}"
}

case "${1:-}" in
  check)
    check
    ;;
  env-status)
    env_status
    ;;
  download-map-data)
    shift
    download_map_data "${1:-}"
    ;;
  deploy)
    deploy
    ;;
  cleanup-review)
    cleanup_review
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    echo "Unknown command: $1" >&2
    usage >&2
    exit 2
    ;;
esac
