#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

command -v docker >/dev/null || { echo 'Docker is required. See https://docs.docker.com/engine/install/'; exit 1; }
docker compose version >/dev/null
docker info >/dev/null
test -f .env || { echo 'Run ./provision.sh to create local configuration first.'; exit 1; }

echo '[1/3] Validating deployment configuration'
docker compose -f deployment-center.yml config --quiet
echo '[2/3] Building and waiting for application health'
docker compose -f deployment-center.yml up --detach --build --wait --wait-timeout 180
echo '[3/3] Verifying health inside the running application'
docker compose -f deployment-center.yml exec -T command-hub node -e "fetch('http://127.0.0.1:8080/api/health').then(async r=>{if(!r.ok || (await r.json()).ok!==true)process.exit(1)}).catch(()=>process.exit(1))"
echo 'Application health passed. Open http://127.0.0.1:8080/deployment-center.html'
echo 'Feed availability and device enrollment are reported separately in the dashboard.'
