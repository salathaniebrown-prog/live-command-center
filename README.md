# Eagle Eyes Live Command Center

Eagle Eyes is a live, read-only command rail and World Command Operating System running on Railway.

## What is live

The application reports real runtime/container state from the process that is currently serving the dashboard:

- CPU utilization sampled from the Node.js host/container
- Memory utilization from the running container
- Root filesystem utilization
- GPU utilization when `nvidia-smi` is available; otherwise `N/A`
- Temperature when exposed by the runtime; otherwise `N/A`
- Runtime health, uptime, Railway service/deployment identifiers when Railway exposes them

No demo or simulated telemetry is substituted for unavailable values.

## World intelligence sources

Eagle Eyes reads current public data from:

- NOAA / NWS active weather alerts
- USGS earthquake feeds
- NASA EONET active natural events
- Wikipedia for free encyclopedic world knowledge
- Open-Meteo for global current weather

The API marks these results as non-simulated and returns an error instead of inventing missing upstream data.

## Command modes

The assistant command rail is protected by `COMMAND_CENTER_ACCESS_TOKEN`.

Free command mode works without OpenAI API credits for:

- Executive Mission Brief / operational snapshot
- System health and uptime
- Live container metrics
- Railway runtime/deployment identifiers
- NWS alerts
- USGS earthquakes
- NASA EONET events
- World-source status
- World knowledge lookup
- Global weather
- World OS capability status

When `OPENAI_API_KEY` is available, GPT-5.6 tool routing is added on top of the same read-only tools.

## Core endpoints

Public runtime/dashboard endpoints:

- `GET /api/status`
- `GET /api/metrics`
- `GET /api/workloads`
- `GET /api/deployment`
- `GET /api/health`
- `GET /api/eagle-eyes/sources`
- `GET /api/eagle-eyes/events?source=usgs|nws|eonet&limit=10`
- `GET /api/assistant/status`

Protected command endpoints require `Authorization: Bearer <COMMAND_CENTER_ACCESS_TOKEN>`:

- `GET /api/eagle-eyes/snapshot`
- `GET /api/eagle-eyes/world-os`
- `GET /api/eagle-eyes/knowledge?q=...`
- `GET /api/eagle-eyes/weather?location=...`
- `GET /api/assistant/auth-check`
- `POST /api/assistant`
- `POST /api/assistant/stream`

## Run locally

Requires Node.js 18+.

```bash
npm install
npm test
npm start
```

Then open `http://localhost:3000`.

## Operational note

`/api/deployment` describes the Railway runtime environment visible to the currently running process. A `RUNNING` stage means the serving container is running; it is not a substitute for Railway's build/deploy job history.
