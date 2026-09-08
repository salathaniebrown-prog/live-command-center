# Eagle Eyes Shell Catcher — Live Test Record

## Purpose

Shell Catcher is a defensive observation API. It accepts authenticated security and environmental events, analyzes them, records a bounded finding ledger, and exposes status/results to Eagle Eyes. It never executes an arbitrary shell command.

## Covered domains

- API request/security observations
- Shell-related suspicious-string observations
- Air telemetry alerts supplied by an upstream source
- Water telemetry alerts supplied by an upstream source
- Ground telemetry, including M4+ earthquake observations
- General system observations

## Safety boundary

- `arbitraryShellExecution=false`
- `commandAuthority=false`
- Ingest is locked unless `SHELL_CATCHER_INGEST_TOKEN` is configured.
- Read/status/event routes use the existing Command Center access guard.
- Raw payload bodies are not retained in the in-memory ledger; records contain a SHA-256 payload fingerprint and normalized finding metadata.
- Environmental alerts are only raised from explicit upstream severity/threshold state, except ground M4+ magnitude which follows Eagle Eyes' existing operational monitoring threshold.

## API surface

- `GET /api/eagle-eyes/shell-catcher/health` — minimal operational state
- `GET /api/eagle-eyes/shell-catcher/status` — protected detailed state + built-in corpus result
- `GET /api/eagle-eyes/shell-catcher/events?limit=50` — protected recent finding ledger
- `POST /api/eagle-eyes/shell-catcher/ingest` — dedicated bearer-token ingest
- `POST /api/eagle-eyes/shell-catcher/self-test` — protected non-destructive built-in corpus

## Upgrade loop

1. Run the built-in corpus and deployment health check.
2. Feed controlled, non-destructive observations through `/ingest`.
3. Record expected vs. actual detection.
4. A reproducible false negative becomes a new regression test before adding a rule.
5. A reproducible false positive becomes a regression test before reducing a rule.
6. Re-run `npm run ci` after every detector change.
7. Promote only when the corpus has zero misses and the recovery baseline still passes.

## Initial controlled corpus

The module ships with benign API, shell-chain marker, command-substitution marker, path-traversal marker, air threshold alert, water critical alert, M4+ ground observation, and small-ground-event controls. These are strings/objects only; the self-test does not invoke a shell.

## CI validation — September 8, 2026

Branch head `a47dd482dd1996ee323fd28b398e8c42c012a7a7` completed these GitHub checks successfully before recovery-branch integration:

- Shell Catcher Validate
- Eagle Eyes Golden Baseline Preservation
- Satellite Recovery Validation
- Consolidated Container Validation

The dedicated Shell Catcher workflow also completed syntax validation, the Shell Catcher regression suite, and the full Eagle Eyes recovery CI gate successfully.

Railway's staging build then ran the recovered application CI gate with 76 tests: 76 passed and 0 failed.

## Live staging verification — September 8, 2026

Shell Catcher was integrated into `recovery/complete-eagle-eyes-20260907`, which is the source branch for the separate Railway `deploy` environment. Production remains on `main`.

Railway staging deployment `2c3273c7-c15c-4987-ab59-9df041a52ed1` completed successfully from recovery commit `154292cd8fdefbf26e489f1eb65835ba2744b8a5`.

Independent GitHub Actions smoke run `34224639466` reached the deployed staging API and passed. The live response reported:

- `ok=true`
- `service=eagle-eyes-shell-catcher`
- `mode=LIVE_DEFENSIVE_OBSERVATION`
- `operational=true`
- `arbitraryShellExecution=false`
- `commandAuthority=false`
- domains: `api`, `shell`, `air`, `water`, `ground`, `system`
- bounded ledger capacity: 500 records

The same live response reported `ingestConfigured=false`. Therefore the Shell Catcher service and detector are operational on staging, while the authenticated external ingest lane remains intentionally locked until `SHELL_CATCHER_INGEST_TOKEN` is configured in the staging environment.

## Resource note

A separate fourth Railway test service could not be provisioned because the account is at the free-plan resource limit. The existing isolated `deploy` environment is therefore the live Shell Catcher staging lane; production is not used for detector experiments.
