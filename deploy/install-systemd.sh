#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-$(pwd)}"
SERVICE="${EAGLE_EYES_SERVICE:-eagle-eyes}"
PORT="${PORT:-3000}"

cd "$APP_DIR"

command -v node >/dev/null
command -v npm >/dev/null
command -v curl >/dev/null

echo "[1/5] Installing dependencies"
npm install --no-audit --no-fund

echo "[2/5] Validating Eagle Eyes"
npm run check

NODE_BIN="$(command -v node)"
RUN_USER="$(id -un)"
RUN_GROUP="$(id -gn)"

echo "[3/5] Installing systemd service"
sudo tee "/etc/systemd/system/${SERVICE}.service" >/dev/null <<EOF
[Unit]
Description=Eagle Eyes Live Command Center
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${APP_DIR}
Environment=NODE_ENV=production
Environment=PORT=${PORT}
EnvironmentFile=-${APP_DIR}/.env
ExecStart=${NODE_BIN} ${APP_DIR}/server.js
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

echo "[4/5] Starting service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"

echo "[5/5] Verifying real health endpoint"
for i in {1..20}; do
  if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
    echo "Eagle Eyes is live on local port ${PORT}"
    sudo systemctl --no-pager --full status "$SERVICE" || true
    exit 0
  fi
  sleep 1
done

sudo journalctl -u "$SERVICE" -n 80 --no-pager
exit 1
