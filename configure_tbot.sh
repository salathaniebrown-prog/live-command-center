#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

log() { printf '[eagle-tbot] %s\n' "$*"; }
die() { printf '[eagle-tbot] ERROR: %s\n' "$*" >&2; exit 1; }

require_root() {
  [[ ${EUID:-$(id -u)} -eq 0 ]] || die "run as root on the remote Linux node"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

validate_endpoint() {
  local value=$1
  [[ -n "$value" ]] || die "empty Teleport endpoint"
  [[ "$value" != *://* ]] || die "endpoint must be host:port, not a URL"
  [[ "$value" =~ ^\[[0-9A-Fa-f:]+\]:[0-9]{1,5}$|^[A-Za-z0-9._-]+:[0-9]{1,5}$ ]] \
    || die "endpoint must be hostname-or-IP:port"
  local port=${value##*:}
  (( port >= 1 && port <= 65535 )) || die "endpoint port out of range"
}

validate_ca_pin() {
  local pin=$1
  [[ "$pin" =~ ^sha256:[[:alnum:]]{64}$ ]] \
    || die "TBOT_CA_PIN must look like sha256:<64-character fingerprint>"
}

validate_absolute_dir() {
  local path=$1
  [[ "$path" == /* ]] || die "directory must be absolute: $path"
  [[ "$path" != "/" ]] || die "refusing to use / as a tbot directory"
}

install_service_user() {
  if ! id "$TBOT_SERVICE_USER" >/dev/null 2>&1; then
    log "creating system user $TBOT_SERVICE_USER"
    useradd --system --home "$TBOT_STATE_DIR" --create-home --shell /usr/sbin/nologin "$TBOT_SERVICE_USER"
  fi
}

install_unit() {
  local unit=/etc/systemd/system/eagle-eyes-tbot.service
  log "writing $unit"
  cat >"$unit" <<UNIT
[Unit]
Description=Eagle Eyes Teleport Machine Identity (tbot)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TBOT_SERVICE_USER}
Group=${TBOT_SERVICE_USER}
UMask=0077
ExecStart=${TBOT_BIN} start \\
  --destination-dir=${TBOT_DESTINATION_DIR} \\
  --token=${TBOT_TOKEN_FILE} \\
  --ca-pin=${TBOT_CA_PIN} \\
  --${TBOT_ENDPOINT_FLAG}=${TBOT_ENDPOINT}
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=${TBOT_STATE_DIR} ${TBOT_DESTINATION_DIR}
LockPersonality=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
UNIT
  chmod 0644 "$unit"
}

main() {
  require_root
  require_command useradd
  require_command systemctl

  : "${TBOT_TOKEN_FILE:?set TBOT_TOKEN_FILE to a file containing the Teleport bot join token}"
  : "${TBOT_CA_PIN:?set TBOT_CA_PIN to the independently verified Teleport CA pin}"

  TBOT_DESTINATION_DIR=${TBOT_DESTINATION_DIR:-/opt/eagle-eyes/tbot-user}
  TBOT_STATE_DIR=${TBOT_STATE_DIR:-/var/lib/teleport/eagle-eyes-tbot}
  TBOT_SERVICE_USER=${TBOT_SERVICE_USER:-eagle-tbot}
  TBOT_BIN=${TBOT_BIN:-$(command -v tbot || true)}

  [[ -n "$TBOT_BIN" && -x "$TBOT_BIN" ]] || die "tbot is not installed or TBOT_BIN is not executable"
  [[ "$TBOT_BIN" == /* ]] || die "TBOT_BIN must resolve to an absolute path"
  [[ -f "$TBOT_TOKEN_FILE" ]] || die "token file does not exist: $TBOT_TOKEN_FILE"
  [[ ! -L "$TBOT_TOKEN_FILE" ]] || die "token file must not be a symlink"
  [[ -s "$TBOT_TOKEN_FILE" ]] || die "token file is empty"
  [[ "$TBOT_TOKEN_FILE" == /* ]] || die "TBOT_TOKEN_FILE must be an absolute path"

  validate_ca_pin "$TBOT_CA_PIN"
  validate_absolute_dir "$TBOT_DESTINATION_DIR"
  validate_absolute_dir "$TBOT_STATE_DIR"

  if [[ -n ${TBOT_PROXY_SERVER:-} && -n ${TBOT_AUTH_SERVER:-} ]]; then
    die "set only one of TBOT_PROXY_SERVER or TBOT_AUTH_SERVER"
  elif [[ -n ${TBOT_PROXY_SERVER:-} ]]; then
    TBOT_ENDPOINT_FLAG=proxy-server
    TBOT_ENDPOINT=$TBOT_PROXY_SERVER
  elif [[ -n ${TBOT_AUTH_SERVER:-} ]]; then
    TBOT_ENDPOINT_FLAG=auth-server
    TBOT_ENDPOINT=$TBOT_AUTH_SERVER
  else
    die "set TBOT_PROXY_SERVER (preferred) or TBOT_AUTH_SERVER"
  fi
  validate_endpoint "$TBOT_ENDPOINT"

  log "using $("$TBOT_BIN" version 2>/dev/null | head -n 1 || printf '%s' "$TBOT_BIN")"
  log "endpoint: $TBOT_ENDPOINT_FLAG=$TBOT_ENDPOINT"
  log "destination: $TBOT_DESTINATION_DIR"
  log "state: $TBOT_STATE_DIR"

  install_service_user

  install -d -m 0700 -o "$TBOT_SERVICE_USER" -g "$TBOT_SERVICE_USER" "$TBOT_STATE_DIR" "$TBOT_DESTINATION_DIR"
  chown "$TBOT_SERVICE_USER:$TBOT_SERVICE_USER" "$TBOT_TOKEN_FILE"
  chmod 0600 "$TBOT_TOKEN_FILE"

  install_unit
  systemctl daemon-reload

  if [[ ${TBOT_ENABLE_NOW:-0} == 1 ]]; then
    log "enabling and starting eagle-eyes-tbot.service"
    systemctl enable --now eagle-eyes-tbot.service
    systemctl --no-pager --full status eagle-eyes-tbot.service
  else
    log "configuration installed but not started"
    log "validate first, then run: sudo systemctl enable --now eagle-eyes-tbot.service"
  fi
}

main "$@"
