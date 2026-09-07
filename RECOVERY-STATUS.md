# Eagle Eyes consolidation status

Date: 2026-09-07. Base: main at 85b5265.

## Recovered work

| Source | Preserved capability |
| --- | --- |
| #19 | World Data Workers and Android configuration |
| #32, #33, #34 | Observation gate, Unified V1, Chronicle Lab V13, Scribe, signed telemetry |
| #35 | VR baseline with truthful native-XR limitations |
| #36 | NASA EONET imagery resolver and preview |
| #37 | Real NVIDIA telemetry collector |
| #38 | Isolated Power Blueprint storage API and Docker stack |
| #39 | Provider health registry and deployment manifest |
| assm-phase2 | Observation-only worker pool and tests |
| reality-engine-phase1 | Real-frame contracts, motion derivation, XR metadata |

## Local validation

- Backend: 48 passing tests; ASSM: 7 passing tests.
- Signed telemetry: 8 passing tests; GPU parser: 5 passing tests.
- Reality Engine: 3 passing tests.
- Android JavaScript export succeeded (587 modules).
- Fixture HTTP tests verified 120 satellite records and 50 records per world feed.
- V13 identity, navigation markers, MAX and NO FLIGHT AUTHORITY checks passed.
- Both existing Railway `/api/health` endpoints returned HTTP 200 with `ok:true`.
  This verifies existing service health only, not this branch or its upstream feeds.

## Corrections

Preserved scoped backend tests while merging startup transformations; repaired
Docker's missing source files; kept dashboard and Power Blueprint APIs separate;
added missing MQTT config/database schema; wired and persisted signed ingest;
locked Android dependencies; corrected manifest health path; added V13 regression,
container-startup, and browser CI gates.

## Remaining verification and access

- Production CI run 34071954940 failed because VERCEL_TOKEN was empty.
  Configure the token and target organization/project secrets; the new workflow
  reports missing values before running Vercel. No credentials were created.
- Production remains isolated. Consolidated CI and staging verification must pass
  before production promotion. Existing source PRs have not been closed.
- Docker is unavailable locally; container validation is delegated to GitHub CI.
- Local browser could not start and Chromium download failed; browser verification
  and screenshots are included in CI. Do not claim a local visual pass.
- GPU/PX4 hardware, physical-server persistence, and headset rendering require
  their actual hosts. VR remains a baseline, not completed native headset rendering.
- Provider health selection is a tested module, not an implemented Anthropic API
  adapter. Imagery remains a separate preview. ASSM/Reality Engine remain isolated
  modules rather than silently changing the production ingestion path.

## GitHub verification update

The consolidated container builds, starts, and serves the V13 identity in CI.
Backend, mobile bundle, GPU image, telemetry security, Power Blueprint, ASSM,
Reality Engine, satellite recovery, recovery smoke, and existing-live-service
checks passed. Browser verification exposed a mobile status badge overlapping
MAX; its layout is corrected and desktop/mobile browser verification now passes
(CI run 34078969734).
Railway staging currently follows main and must be switched to this recovery
branch for staging verification.

A separate Railway staging service was attempted but rejected with:
"Free plan resource provision limit exceeded." No new service was deployed.
The existing staging service remains on main. Reusing it requires changing its
source branch; the available direct configuration tool does not support that
field. Production Vercel still needs the missing deployment credentials.

Standalone Android APK compilation is running in workflow 34078833102; the
JavaScript bundle export already passed. Check that workflow before distributing
an APK.

## MCP / UDP integration checkpoint

The recovery branch now includes a local-only MCP/UDP integration layer:

- `server-mcp.js` exposes `get_cluster_metrics` and guarded
  `tune_udp_backplane` over MCP-compatible stdio JSON-RPC.
- `src/security/mcpFirewall.js` enforces strict numeric 0-250 ms bounds,
  rejects extra fields, and applies a 5-second execution cooldown.
- `server-udp.js` separates telemetry ingress (`127.0.0.1:5050`) from the
  control socket (`127.0.0.1:5051`) and independently validates tuning commands.
- Tuning is acknowledgement-based; a sent UDP packet is not reported as applied
  unless the daemon confirms it.
- `src/database/analytics.js` reports observed runtime/backplane state without
  pretending that the presence of `DATABASE_URL` proves database connectivity.
- `scripts/simulate-load.js` labels all synthetic traffic with `simulated: true`,
  and live/simulated node counts remain separate.
- Focused local validation for the new layer: 8 tests passed plus Node syntax
  checks before repository write.

This layer is not a production deployment authorization and does not change the
existing PX4 observation-only rule, payment execution safeguards, or PR #40's
staging-before-main requirement.
