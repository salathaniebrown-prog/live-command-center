# Eagle Eyes Unified Recovery

Recovery branch: `recovery/eagle-eyes-unified-20260902`

The recovery rule is **real inputs only**. Old code is not imported just because
it existed.

## Current `live-command-center` capabilities preserved

The current mainline already contains the merged production work from PRs #8-#17:
free command mode, operations intelligence, executive mission brief, World OS,
free world-knowledge routing, global weather fixes, Command Center V2, Data
Spine, Live Global Operations Map, and PX4 Telemetry Spine.

## Recovered from older repositories

### `eagle-eyes-mobile`

Recovered into `clients/mobile/` as the Android/Expo client. It keeps the live
Railway backend, live status, World OS, web-search surface, and EAS project
configuration. Backend command-mode status wiring was corrected during import.

### `eagle-eyes-telemetry`

The useful part was the real MAVLink/PX4 reader. The old automatic simulation
fallback was intentionally **not** imported. The recovered bridge is
`bridges/px4-mavlink-bridge.py` and only forwards observed MAVLink telemetry to
the protected current ingest API.

### `psychic-adventure`

The useful part was the physical Ubuntu/systemd deployment procedure. It is
recovered as `deploy/install-systemd.sh` and now validates the current code and
checks the real health endpoint before reporting success.

## Audited but not merged into runtime

- `real-time`: separate Next.js/v0 application; no NWS/USGS/EONET/Railway
  telemetry implementation was found to improve the current production backend.
- `botdefense`: unrelated bot-defense code, not part of Eagle Eyes runtime.
- `ddp-security-fixes`: no runtime implementation to merge.
- `cfworker`: separate Cloudflare Worker project; not required by the current
  Railway/Expo architecture.

These repositories remain intact in GitHub history. Excluding them from the
runtime avoids fake capability claims and dependency conflicts.
