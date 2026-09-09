# Command Deployment Center

Open `/deployment-center.html` from the existing Eagle Eyes workspace. Chronicle
Lab V13, executive council, Scribe, MAX, Shell Catcher and the existing startup
transformations remain part of the same application.

## Run on a Docker host

Docker Engine with the Compose plugin is required. From this repository:

```bash
chmod +x provision.sh deploy.sh
./provision.sh
```

The initializer creates a local `.env` only when absent, with a random Command
Rail token and mode 0600. It builds the complete application and waits for a
successful health check. Open `http://127.0.0.1:8080/deployment-center.html`.
Subsequent updates use `./deploy.sh`. Existing volumes are retained. No global
Docker prune, firewall flush, root daemon, force push or remote shell endpoint
is part of this deployment.

`deployment-center.yml` is the focused hub stack. The existing
`docker-compose.yml` and `telemetry_spine/docker-compose.yml` retain their
physical Power Blueprint and broker/device stacks. They require their own
hardware/configuration and should not be started together on conflicting ports.
Setting a slot count does not provision 32 computers.

## Measurements and stream

| Route | Behavior |
| --- | --- |
| `GET /api/deployment-center/status` | Runtime revision, measured host/feed/market status and 32 slots |
| `GET /api/telemetry` | Alias for the same status document |
| `GET /api/deployment-center/stream` | SSE snapshots with native browser reconnect and bounded clients |
| `POST /api/mobile/telemetry` | Signed device report with timestamp and replay protection |
| `GET /api/deployment-center/network.csv` | Protected log export using Command Rail bearer access |
| `POST /api/deployment-center/deploy` | Protected dispatch of one fixed GitHub workflow and main revision |

Feed and spot-price collection is shared among consumers and cached for 30
seconds; stream clients receive updates every five seconds. API failures return
unavailable/null values. Market prices are prices, not wallet balances,
transaction receipts, or revenue. There is no currency transfer in this module.
The existing Base USDC sandbox remains intact.

Node states start WAITING, become PASS or FAIL only on a signed device report,
and become STALE after 60 seconds. They are self-reported device status, not an
independent hardware test. Node latency is null because a one-way heartbeat
does not measure round-trip time. Server processing duration is recorded under
its own name. Security alerts must not turn every node green or red without
actual device evidence.

Public feed adapters reuse USGS GeoJSON, NOAA/NWS alerts and NASA EONET. Spot
prices use Coinbase's documented `/v2/prices/{pair}/spot` API, validate currency
and numeric amounts, and preserve unavailable state on failure.

Sources: [Coinbase prices](https://docs.cdp.coinbase.com/coinbase-app/track-apis/prices),
[Compose health dependencies](https://docs.docker.com/compose/how-tos/startup-order/),
[Railway deployment API](https://docs.railway.com/integrations/api/manage-services#deploy-a-service).

## Mobile enrollment

Use the same HTTPS Railway domain as the dashboard, with the full
`/api/mobile/telemetry` path. Do not ship secrets inside an APK or publish them in
repository files. Each authorized device requires its own random secret and
unique slot, provisioned separately on the server and device.

Set `MOBILE_DEVICES_JSON` to a JSON object mapping device IDs to `{slot, secret}`.
Generate secrets with `openssl rand -hex 32`; values must be at least 64
characters. No default/shared key is used. No devices are enrolled by default.

The body contains exactly `device_id`, `target_cluster_slot` and `status_flag`
(`PASS` or `FAIL`). Sign the exact UTF-8 body bytes; never serialize a parsed
body a second time to verify a signature.

```
signature = hex(HMAC-SHA256(secret, timestamp + "." + nonce + "." + raw_body))
```

Headers: `X-Eagle-Eyes-Device`, `X-Eagle-Eyes-Timestamp` (13-digit Unix
milliseconds), `X-Eagle-Eyes-Nonce` (16–80 alphanumeric/underscore/hyphen
characters), and `X-Eagle-Eyes-Signature` (lowercase hex). Use a new nonce for
every attempt; clocks must be within 60 seconds. Replays return 409, wrong
signatures 403, expired/malformed envelopes 401, wrong slot/body 400, and an
unenrolled server 503. The packet is authenticated before it updates a slot.

For a provisioned device, set `EAGLE_EYES_DEVICE_SECRET` in its environment and
use `scripts/send-mobile-heartbeat.py --url https://YOUR-HUB --device DEVICE_ID
--slot SLOT --status PASS`. Status must reflect a real check by the sending
device. The current Android app is an Expo client; the supplied standalone
Kotlin snippets are not an Android build or proof of installed device behavior.
Periodic WorkManager jobs are unsuitable for a five-second heartbeat.

Device state and replay history are per process and reset on restart. Deploy
one hub replica for this registry; use shared durable state before scaling it.
The local Compose volume retains CSV logs, rotating at 50 MiB into one prior
file. Railway's default temporary log path is ephemeral; mount storage and set
`DEPLOYMENT_LOG_DIR` to retain logs across deployments. Live mobile enrollment
and durable Railway storage still require configuration.

## Deployment and validation

Production Railway follows `main`. The normal CI pipeline runs the existing
tests and verifies the exact serving SHA on Railway after a main push. The
optional Vercel deploy remains available as a manual workflow with its own
credentials; Vercel's status does not stand in for Railway health. The optional
standalone Android World Data URL no longer blocks backend CI.

For the dashboard's deployment button, configure `DEPLOYMENT_GITHUB_TOKEN` on
the server with repository-only contents:read and actions:write. Configure
`RAILWAY_PROJECT_TOKEN` as a GitHub production environment secret, scoped to the
existing Railway production environment. This setup is not implied by having
the ChatGPT GitHub/Railway connections. Never send either token to the browser.
The button is locked until server configuration is present; a workflow request
is reported as REQUESTED, not completed. The workflow validates/builds the
requested main SHA, uses the production environment's approval settings,
rechecks main before deployment, requests that exact SHA, then verifies health
and the serving revision. No force merge or arbitrary repository execution.

```bash
npm ci
npm run build
python3 main_prober.py --url http://127.0.0.1:8080
python3 test_mesh.py --url http://127.0.0.1:8080
```

The health prober exits nonzero on degraded/unavailable feeds. The network
probe makes ten bounded requests and measures each request independently;
total concurrent wall time divided by ten is not per-request latency. Run it
from the phone's network to measure that path. Neither probe enrolls a fake
device or writes invented price/node values.
