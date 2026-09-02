# Real PX4 / MAVLink bridge

This is the recovered real-hardware path from the older `eagle-eyes-telemetry`
repository, adapted to the current Eagle Eyes telemetry schema.

There is **no simulation mode** in this recovered bridge.

## What it does

- Reads MAVLink telemetry from a PX4 endpoint on a protected/local network.
- Never sends arming, navigation, actuator, mission-write, or flight-control commands.
- Converts real MAVLink observations into `eagle-eyes.px4-telemetry.v1`.
- Sends snapshots by HTTPS to `/api/eagle-eyes/px4/ingest`.
- If telemetry stops, it stops posting. The server then changes the vehicle state to
  `STALE` instead of inventing data.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r bridges/requirements.txt
```

## Required environment

```text
MAVLINK_ENDPOINT=udpin:0.0.0.0:14550
PX4_TELEMETRY_INGEST_TOKEN=<same secret configured on the Eagle Eyes server>
EAGLE_EYES_INGEST_URL=https://live-command-center-production-31ed.up.railway.app/api/eagle-eyes/px4/ingest
PX4_VEHICLE_ID=eagle-1
```

Run while the flight controller is on a trusted/local network:

```bash
python bridges/px4-mavlink-bridge.py
```

Railway's normal public HTTP domain is not an inbound MAVLink/UDP endpoint. The
bridge should run beside the real PX4/MAVLink source and make an outbound HTTPS
connection to Eagle Eyes.
