# Power Blueprint Deployment v1

Safe standalone deployment for the Eagle Eyes / Command Center infrastructure. It does not modify the existing production repository.

## Included
- Node.js Command Center API
- MQTT telemetry ingestion
- PostgreSQL + TimescaleDB + PostGIS
- Persistent database and MQTT volumes
- Docker health checks
- No embedded credentials

## Start on Ubuntu / Proxmox VM
1. Install Docker Engine + Docker Compose plugin.
2. Copy `.env.example` to `.env` and replace the password with a long random value.
3. Run: `docker compose up -d --build`
4. Verify: `curl http://127.0.0.1:3000/api/health`

## Telemetry test
POST JSON to `/api/telemetry/test-node` with latitude, longitude and altitude_m. MQTT stores the event in TimescaleDB/PostGIS.

## Security before Internet exposure
The bundled MQTT listener permits anonymous access for first local-network testing only. Do NOT expose port 1883 to the public Internet. Before production, add MQTT authentication/TLS, reverse-proxy HTTPS, firewall rules, private mesh networking, backups, and secrets management.

Flight-critical control must remain on the PX4/ArduPilot flight controller. This stack is for telemetry, storage, monitoring, and non-flight-critical processing.
