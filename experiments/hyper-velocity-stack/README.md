# Eagle Eyes Hyper-Velocity Observation Stack (Experimental)

This directory is intentionally isolated from the production Node.js Command Center.

## Safety boundary

- Observation authority is forced at the final payload merge position.
- Command-capable tools are not accepted by the positive allowlist.
- Hypersonic tracks are explicitly synthetic (`dataClass: simulation`, `synthetic: true`).
- Simulation traffic uses the separate Kafka topic `planetary-simulation-stream`.
- This stack does not replace `server.js`, deploy production, or modify PR #32.

## Local validation

```bash
python -m py_compile main.py hyper_velocity_spine.py test_security.py
docker compose config
docker compose build
docker compose run --rm eagle-eyes-engine python -m unittest -v test_security.py
docker compose up
```

Endpoints after startup:

- Engine health: `http://localhost:8000/health`
- Prometheus metrics: `http://localhost:8000/metrics`
- NASA GIBS configuration: `http://localhost:8000/api/v1/nasa/config`
- Prometheus UI: `http://localhost:9090`

The NASA endpoint provides a NASA GIBS imagery template. It does not imply spacecraft or target tracking.
