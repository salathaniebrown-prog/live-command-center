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
- chainid.network aggregated EVM chain registry

The API marks these results as non-simulated and returns an error instead of inventing missing upstream data.

## EVM chain registry

The EVM registry is observation-only. Eagle Eyes reads the aggregated `https://chainid.network/chains.json` dataset and exposes chain identity and network metadata without connecting a wallet, signing payloads, or submitting transactions.

Returned metadata can include:

- chain name, short name, chain ID, network ID, and CAIP-2 identity
- native currency
- status (`active`, `incubating`, or `deprecated` when supplied upstream)
- RPC URL listings and explorers as reference metadata only
- feature names such as `EIP155` and `EIP1559`
- parent/L2 relationships and bridge URLs when supplied upstream
- upstream red flags such as reused chain-ID warnings

The upstream source repository maintains individual chain records under `_data/chains` and icon metadata under `_data/icons`. Eagle Eyes consumes the automatically aggregated registry and does not modify upstream chain records.

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
- EVM chain registry lookup by chain name or chain ID
- World-source status
- World knowledge lookup
- Global weather
- World OS capability status

When `OPENAI_API_KEY` is available, GPT-5.6 tool routing is added on top of the same read-only tools.

## PX4 telemetry spine

PX4 telemetry is an optional observation-only integration. Eagle Eyes accepts validated snapshots from a companion bridge, keeps unavailable fields as `N/A`, and never substitutes simulated vehicle data.

The companion ingest uses a credential that is separate from Command Rail access:

- `PX4_TELEMETRY_INGEST_TOKEN` — required for telemetry POSTs
- `PX4_TELEMETRY_STALE_MS` — optional freshness threshold; defaults to 15000 ms

The telemetry state is explicit:

- `UNCONFIGURED` — no ingest token is configured
- `WAITING` — ingest is configured but no validated snapshot has arrived
- `LIVE` — the latest receive time and source observation time are both within the freshness threshold
- `STALE` — the retained snapshot is too old to be treated as current vehicle state

The current v1 store is process-local and in-memory. A Railway restart clears the latest snapshot back to `WAITING`; a future persistence layer is required before treating this as shared multi-replica telemetry storage.

The Command Rail exposes PX4 telemetry only as a read-only tool. It has no arm, takeoff, navigation, mission-write, actuator, or other vehicle-control function.

## Core endpoints

Public runtime/dashboard endpoints:

- `GET /api/status`
- `GET /api/metrics`
- `GET /api/workloads`
- `GET /api/deployment`
- `GET /api/health`
- `GET /api/eagle-eyes/sources`
- `GET /api/eagle-eyes/events?source=usgs|nws|eonet&limit=10`
- `GET /api/eagle-eyes/chains?q=ethereum&limit=10`
- `GET /api/assistant/status`

Protected command endpoints require `Authorization: Bearer <COMMAND_CENTER_ACCESS_TOKEN>`:

- `GET /api/eagle-eyes/snapshot`
- `GET /api/eagle-eyes/world-os`
- `GET /api/eagle-eyes/knowledge?q=...`
- `GET /api/eagle-eyes/weather?location=...`
- `GET /api/eagle-eyes/px4`
- `GET /api/assistant/auth-check`
- `POST /api/assistant`
- `POST /api/assistant/stream`

PX4 companion ingest requires `Authorization: Bearer <PX4_TELEMETRY_INGEST_TOKEN>`:

- `POST /api/eagle-eyes/px4/ingest`

## Run locally

Requires Node.js 18+.

```bash
npm install
npm test
npm start
```

Then open `http://localhost:3000`.

## Cloud coding agents

Useful Claude Cloud and Vercel AI Gateway coding-agent commands:

```bash
claude -p "your message" --cloud <session-id>
CCR_FORCE_BUNDLE=1 claude --cloud "Run the test suite and fix any failures"
claude --cloud "Fix the flaky test in auth.spec.ts"
claude --cloud "Update the API documentation"
claude --cloud "Refactor the logger to use structured output"
claude --cloud "Execute the migration plan in docs/migration-plan.md"
claude --permission-mode plan
vercel ai-gateway coding-agents setup
```

## Operational note

`/api/deployment` describes the Railway runtime environment visible to the currently running process. A `RUNNING` stage means the serving container is running; it is not a substitute for Railway's build/deploy job history.
