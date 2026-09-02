#!/usr/bin/env python3
"""Eagle Eyes PX4/MAVLink observation-only bridge.

Reads telemetry from a local/protected MAVLink endpoint and forwards validated
snapshots over HTTPS to the Eagle Eyes PX4 ingest API. It contains no simulation
mode and sends no vehicle-control commands.
"""

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from urllib import request, error

from pymavlink import mavutil


BRIDGE_VERSION = "eagle-eyes-mavlink-bridge/1.0"
MAVLINK_ENDPOINT = os.getenv("MAVLINK_ENDPOINT", "").strip()
INGEST_URL = os.getenv(
    "EAGLE_EYES_INGEST_URL",
    "https://live-command-center-production-31ed.up.railway.app/api/eagle-eyes/px4/ingest",
).strip()
INGEST_TOKEN = os.getenv("PX4_TELEMETRY_INGEST_TOKEN", "").strip()
VEHICLE_ID = os.getenv("PX4_VEHICLE_ID", "").strip()
POST_INTERVAL = max(0.25, float(os.getenv("PX4_POST_INTERVAL_SECONDS", "1.0")))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def post_snapshot(payload):
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        INGEST_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {INGEST_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": BRIDGE_VERSION,
        },
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        if response.status not in (200, 202):
            raise RuntimeError(f"ingest returned HTTP {response.status}")


def payload_from_state(state, system_id, component_id):
    vehicle_id = VEHICLE_ID or f"px4-{system_id or 'unknown'}"
    payload = {
        "vehicleId": vehicle_id,
        "autopilot": "PX4",
        "transport": "mavlink",
        "observedAt": utc_now(),
        "systemId": system_id,
        "componentId": component_id,
        "bridgeVersion": BRIDGE_VERSION,
    }

    for key in ("flightMode", "armed", "landed"):
        if key in state:
            payload[key] = state[key]

    if "position" in state:
        payload["position"] = state["position"]
    if "gps" in state:
        payload["gps"] = state["gps"]
    if "attitude" in state:
        payload["attitude"] = state["attitude"]
    if "velocity" in state:
        payload["velocity"] = state["velocity"]
    if "battery" in state:
        payload["battery"] = state["battery"]
    if "link" in state:
        payload["link"] = state["link"]

    return payload


def main():
    if not MAVLINK_ENDPOINT:
        sys.exit("MAVLINK_ENDPOINT is required. No simulation fallback is available.")
    if not INGEST_TOKEN:
        sys.exit("PX4_TELEMETRY_INGEST_TOKEN is required.")
    if not INGEST_URL.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        sys.exit("EAGLE_EYES_INGEST_URL must use HTTPS except for localhost testing.")

    print(f"[eagle-eyes] opening MAVLink telemetry at {MAVLINK_ENDPOINT}", flush=True)
    connection = mavutil.mavlink_connection(MAVLINK_ENDPOINT)
    heartbeat = connection.wait_heartbeat(timeout=30)
    if heartbeat is None:
        sys.exit("No MAVLink heartbeat received within 30 seconds.")

    system_id = connection.target_system or heartbeat.get_srcSystem()
    component_id = connection.target_component or heartbeat.get_srcComponent()
    state = {}
    last_post = 0.0
    last_message = 0.0

    print(
        f"[eagle-eyes] telemetry source connected: system={system_id} component={component_id}",
        flush=True,
    )

    while True:
        msg = connection.recv_match(blocking=True, timeout=2)
        now = time.time()

        if msg is None:
            if last_message and now - last_message > 5:
                print("[eagle-eyes] telemetry stream waiting; no synthetic data emitted", flush=True)
            continue

        kind = msg.get_type()
        if kind == "BAD_DATA":
            continue

        last_message = now
        system_id = msg.get_srcSystem() or system_id
        component_id = msg.get_srcComponent() or component_id

        if kind == "HEARTBEAT":
            state["armed"] = bool(
                msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            )
            try:
                mode = mavutil.mode_string_v10(msg)
                if mode and mode != "Mode(0x00000000)":
                    state["flightMode"] = str(mode)
            except Exception:
                pass

        elif kind == "EXTENDED_SYS_STATE":
            if msg.landed_state == mavutil.mavlink.MAV_LANDED_STATE_ON_GROUND:
                state["landed"] = True
            elif msg.landed_state == mavutil.mavlink.MAV_LANDED_STATE_IN_AIR:
                state["landed"] = False
            else:
                state["landed"] = None

        elif kind == "GLOBAL_POSITION_INT":
            state["position"] = {
                "latitude": msg.lat / 1e7,
                "longitude": msg.lon / 1e7,
                "altitudeM": msg.alt / 1000.0,
                "relativeAltitudeM": msg.relative_alt / 1000.0,
            }
            north = msg.vx / 100.0
            east = msg.vy / 100.0
            down = msg.vz / 100.0
            state["velocity"] = {
                "northMps": north,
                "eastMps": east,
                "downMps": down,
                "groundSpeedMps": math.hypot(north, east),
                "verticalSpeedMps": -down,
            }

        elif kind == "ATTITUDE":
            state["attitude"] = {
                "rollDeg": math.degrees(msg.roll),
                "pitchDeg": math.degrees(msg.pitch),
                "yawDeg": math.degrees(msg.yaw),
            }

        elif kind == "SYS_STATUS":
            battery = {}
            if msg.voltage_battery != 65535:
                battery["voltageV"] = msg.voltage_battery / 1000.0
            if msg.current_battery != -1:
                battery["currentA"] = msg.current_battery / 100.0
            if msg.battery_remaining != -1:
                battery["remainingPct"] = msg.battery_remaining
            if battery:
                state["battery"] = battery

        elif kind == "GPS_RAW_INT":
            gps = {
                "fixType": msg.fix_type,
            }
            satellites = getattr(msg, "satellites_visible", 255)
            if 0 <= satellites <= 100:
                gps["satellites"] = satellites
            if getattr(msg, "eph", 65535) != 65535:
                gps["hdop"] = msg.eph / 100.0
            if getattr(msg, "epv", 65535) != 65535:
                gps["vdop"] = msg.epv / 100.0
            state["gps"] = gps

        elif kind == "RADIO_STATUS":
            if msg.rssi != 255:
                state["link"] = {
                    "rssiPct": round(max(0.0, min(100.0, msg.rssi * 100.0 / 254.0)), 1)
                }

        if now - last_post < POST_INTERVAL:
            continue

        if not state:
            continue

        payload = payload_from_state(state, system_id, component_id)
        try:
            post_snapshot(payload)
            last_post = now
            print(
                f"[eagle-eyes] telemetry accepted for {payload['vehicleId']} at {payload['observedAt']}",
                flush=True,
            )
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"[eagle-eyes] ingest HTTP {exc.code}: {detail}", file=sys.stderr, flush=True)
            time.sleep(2)
        except Exception as exc:
            print(f"[eagle-eyes] ingest error: {exc}", file=sys.stderr, flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
