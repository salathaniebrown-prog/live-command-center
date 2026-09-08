# Eagle Eyes Live Command Center

Eagle Eyes is a live, read-only command rail and World Command Operating System running on Railway.

Project identity: Eagle Eyes Command OS by Salathaniel Brown Sr, used here with
explicit project permission.

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
The provider health registry also recognizes Moonshot/Kimi with `MOONSHOT_API_KEY`
and `MOONSHOT_MODEL=kimi-k3` using the OpenAI-compatible
`/v1/chat/completions` shape. Kimi is tracked as a configured provider option
with tool-call metadata, but runtime routing remains explicit and does not store
API keys, private keys, wallet secrets, or live execution authority in the repo.

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

## BCI telemetry lane

Eagle Eyes now reserves a read-only BCI telemetry lane for future validated
observations. It is scoped to single self-candidate mode for Salathaniel Brown
Sr and is not open enrollment. It starts as `UNCONFIGURED` until
`BCI_TELEMETRY_INGEST_TOKEN` is set, then reports `WAITING` until real
observations are wired in. This lane is not a medical device, does not diagnose
or treat anything, and has no control output or command authority.

## Project Future Command Lab

Project Future Command Lab tracks the next Eagle Eyes action layers without
mixing them into the live observation system. It keeps project-builder,
GitHub-operator, deployment-operator, BCI telemetry, and Supercomputer
NexusBrown Command Center work visible as planned or registered capabilities
while preserving Chronicle Lab V13, requiring
authenticated scope, and blocking live execution by default.

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
- `GET /api/eagle-eyes/bci/status`
- `GET /api/eagle-eyes/future-command-lab`
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

## Consolidated recovery — September 7, 2026

The consolidation preserves Chronicle Lab V13 and its WORLD/LIVE/LAB/INTEL/LINKS/MAX
navigation. `npm run ci` now checks the V13 identity as well as backend behavior.
The recovered histories include PRs #19 and #32–#39, ASSM phase 2, and Reality
Engine phase 1. See `RECOVERY-STATUS.md` for verification and remaining deployment gates.

For a local physical-server stack, set `POSTGRES_PASSWORD` in `.env`, then run
`docker compose up -d --build`. The V13 dashboard is on `127.0.0.1:3000`; the
separate Power Blueprint storage API is on `127.0.0.1:3001`. PostgreSQL initializes
its telemetry table on first volume creation. MQTT is anonymous for local testing
and bound to loopback port 1883. These services require a configured reverse proxy
and authentication before external exposure. Existing database volumes need the
initialization SQL applied separately. Keep credential files out of Git.

GitHub Vercel deployment requires `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and
`VERCEL_PROJECT_ID` in repository or production-environment secrets. An existing
Railway health response does not establish that a new Git revision is deployed.

## MCP / UDP supercomputer hub

Eagle Eyes now has an isolated local MCP control plane for cluster observation and
guarded UDP backplane tuning. It is intentionally separate from the production web
command rail.

```text
MCP host/client
     |
     | stdio JSON-RPC
     v
server-mcp.js
     |
     +--> get_cluster_metrics --> runtime + data/v1 UDP state
     |
     +--> tune_udp_backplane
              |
              v
       McpToolFirewall
       0-250 ms / 5 s cooldown
              |
              | loopback UDP + acknowledgement
              v
        127.0.0.1:5051
         server-udp.js
              |
              +--> telemetry ingress: 127.0.0.1:5050
```

The MCP broker uses the standard newline-delimited JSON-RPC stdio transport and
advertises only two tools. `get_cluster_metrics` is read-only. `tune_udp_backplane`
changes only the local UDP processing throttle and cannot address remote hosts,
vehicles, payment systems, or hardware actuators.

Safety boundaries:

- MCP tuning accepts only finite numeric values from 0 through 250 ms.
- A 5-second firewall cooldown blocks rapid AI command loops.
- The MCP broker sends control packets only to `127.0.0.1`.
- The UDP daemon independently revalidates every control command.
- A tuning call is reported successful only after the UDP daemon acknowledges it.
- Load-test packets carry `simulated: true`; analytics keeps simulated and live
  packet/node counts separate.
- `DATABASE_URL` being present is reported only as configuration state. The MCP
  analytics module does not claim a successful database query unless one is
  actually implemented and observed.

Run the local backplane and an explicitly simulated 50-node load pass:

```bash
npm run udp &
UDP_PID=$!
npm run simulate-load
kill "$UDP_PID"
```

An MCP host should spawn the broker itself rather than backgrounding it manually:

```json
{
  "mcpServers": {
    "supercomputer-hub": {
      "command": "node",
      "args": ["/absolute/path/to/live-command-center/server-mcp.js"],
      "env": {
        "UDP_CONTROL_HOST": "127.0.0.1",
        "UDP_CONTROL_PORT": "5051"
      }
    }
  }
}
```

Do not commit database passwords, API keys, wallet material, or other credentials
into MCP configuration files. Inject secrets through the host environment or the
platform's secret manager.
