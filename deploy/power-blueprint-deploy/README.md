# Power Blueprint V1 Deployment Tool

This directory is the isolated Power Blueprint deployment baseline for Eagle Eyes.

## Purpose

- Prepare the persistent physical-server deployment path.
- Keep Power Blueprint work isolated from production `main`.
- Validate changes through GitHub Actions before merging.
- Preserve the existing Eagle Eyes telemetry spine and production services.

## Target stack

- Docker-based persistent compute
- PostgreSQL/PostGIS data layer
- MQTT telemetry transport
- Eagle Eyes application service
- Future physical Power Blueprint server deployment

## Operator tool

```bash
cd deploy/power-blueprint-deploy
chmod +x power-blueprint-tool.sh
./power-blueprint-tool.sh check
./power-blueprint-tool.sh env-status
```

### Download map data

Do not commit a signed MapTiler URL. Supply it only at runtime:

```bash
export MAPTILER_DATA_URL='https://signed-download-url.example/...'
./power-blueprint-tool.sh download-map-data maptiler-geocoding-index.tar.gz
```

The download uses `wget -c`, so interrupted downloads can resume.

### Run the deployment script

Supply credentials through the runtime environment only:

```bash
export H_TOKEN='...'
export SLACK_WEBHOOK_URL='...'
export DEPLOY_SCRIPT='/app/deploy_script.py'
./power-blueprint-tool.sh deploy
```

Deployment output defaults to `/var/log/power-blueprint-deployer.log`. Override it with `POWER_BLUEPRINT_LOG_FILE` when needed.

### Remove a temporary review file

```bash
export REVIEW_FILE='/path/to/review-file'
./power-blueprint-tool.sh cleanup-review
```

The cleanup command refuses `/` and directory targets and only runs when explicitly requested.

## Validation

Local syntax validation:

```bash
npm run check
```

GitHub Actions also validates the shell tool, JavaScript, package metadata, dependencies, and Docker build on the `power-blueprint-v1` branch and relevant pull requests.

## Safety boundary

- This branch does not deploy to production automatically.
- Do not merge until required validation checks pass.
- Real secrets, signed download URLs, and webhook values must never be committed.
- Existing `telemetry_spine` configuration remains unchanged.
