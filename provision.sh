#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
command -v docker >/dev/null || { echo 'Install Docker Engine and Compose: https://docs.docker.com/engine/install/'; exit 1; }
docker compose version >/dev/null
docker info >/dev/null

if [ ! -f .env ]; then
  umask 077
  command -v od >/dev/null
  command -v tr >/dev/null
  deployment_token="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  test "${#deployment_token}" -eq 64
  # Exclusive creation prevents replacing configuration from another setup process.
  (set -o noclobber; printf 'COMMAND_CENTER_ACCESS_TOKEN=%s\nMOBILE_DEVICES_JSON=\nDEPLOYMENT_GITHUB_TOKEN=\n' "$deployment_token" > .env)
  unset deployment_token
  chmod 600 .env
  echo 'Created local configuration with a random Command Rail access token.'
fi
exec bash ./deploy.sh
