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

## Live deployment note

A separate Railway test service could not be provisioned because the account is at the free-plan resource limit. The existing Railway `deploy` environment already tracks `recovery/complete-eagle-eyes-20260907`, so the live test path is to integrate Shell Catcher into that recovery branch while keeping production on `main`.
