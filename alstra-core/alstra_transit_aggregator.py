#!/usr/bin/env python3
"""
Alstra Long-Term Transit Aggregation Engine
Compiles historical vehicle telemetry into persistent rollup summaries
and outputs verified multi-checkpoint audit timelines.
"""

import os
import sqlite3
import time

DB_PATH = os.path.expanduser("~/alstra-core/alstra_core.db")

def run_aggregation():
    if not os.path.exists(DB_PATH):
        print("[!] Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")

    # Create persistent summary rollup table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_transit_rollups (
            vin_id TEXT PRIMARY KEY,
            total_checkpoints INTEGER,
            first_seen_utc TEXT,
            last_seen_utc TEXT,
            latest_status TEXT,
            latest_coords TEXT,
            aggregated_at_utc TEXT
        )
    """)

    now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Aggregate raw historical logs per VIN
    cursor.execute("""
        SELECT 
            vin_id,
            COUNT(event_id) AS total_pings,
            MIN(recorded_at_utc) AS first_ping,
            MAX(recorded_at_utc) AS last_ping
        FROM asset_transit_history
        GROUP BY vin_id
    """)
    summaries = cursor.fetchall()

    print("\n=======================================================================")
    print("        ALSTRA LONG-TERM TRANSIT AGGREGATION & AUDIT LEDGER")
    print("=======================================================================")

    if not summaries:
        print("  No historical transit records logged yet.")
    else:
        for vin, count, first_ts, last_ts in summaries:
            cursor.execute("""
                SELECT transit_status, gps_coordinates 
                FROM asset_transit_history 
                WHERE vin_id = ? 
                ORDER BY event_id DESC LIMIT 1
            """, (vin,))
            latest = cursor.fetchone()
            latest_status = latest[0] if latest else "UNKNOWN"
            latest_coords = latest[1] if latest else "0.0,0.0"

            cursor.execute("""
                INSERT INTO asset_transit_rollups 
                (vin_id, total_checkpoints, first_seen_utc, last_seen_utc, latest_status, latest_coords, aggregated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vin_id) DO UPDATE SET
                    total_checkpoints=excluded.total_checkpoints,
                    last_seen_utc=excluded.last_seen_utc,
                    latest_status=excluded.latest_status,
                    latest_coords=excluded.latest_coords,
                    aggregated_at_utc=excluded.aggregated_at_utc
            """, (vin, count, first_ts, last_ts, latest_status, latest_coords, now_utc))

            print(f"  VIN: {vin}")
            print(f"    Total Checkpoints : {count}")
            print(f"    First Logged      : {first_ts}")
            print(f"    Last Logged       : {last_ts}")
            print(f"    Current Status    : {latest_status} ({latest_coords})")
            print("-----------------------------------------------------------------------")

    conn.commit()
    conn.close()
    print(f"[⚡] AGGREGATION COMPLETE: Rollup matrix synchronized at {now_utc}\n")

if __name__ == "__main__":
    run_aggregation()
