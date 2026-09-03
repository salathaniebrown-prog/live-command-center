# Eagle Eyes World Data Workers Recovery

This recovery branch preserves three Cloudflare Worker layers recovered from prior Eagle Eyes work.

- `workers/world-data-edge/worker.mjs`: original edge Worker. Proxies Railway metrics plus USGS, NASA EONET, and NOAA/NWS.
- `workers/world-data-v2-legacy-proxy/worker.mjs`: intermediate normalized V2 that depends on the V1 edge Worker.
- `workers/world-data-v2/worker.mjs`: preferred recovered V2. Fetches USGS, NASA EONET, and NOAA/NWS directly, normalizes verified events, exposes source health and search, and keeps unavailable values unavailable rather than substituting simulations.

The production `main` branch was not modified by this recovery. The current Railway backend already contains the Data Spine, World OS, PX4 observation-only telemetry, protected Command Rail, and the recovered mobile client with Web Search.

Recommended promotion target after validation: `workers/world-data-v2/worker.mjs`.

No simulated runtime data is introduced by these recovered Worker files.
