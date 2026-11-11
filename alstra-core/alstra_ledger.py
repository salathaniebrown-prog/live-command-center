#!/usr/bin/env python3
import sqlite3
import json
import time
import os

DB_NAME = "alstra_core.db"

def init_ledger():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            category TEXT,
            payload TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[LEDGER] SQLite persistence engine initialized successfully.")

def log_event(category, payload_dict, status="COMMITTED"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cursor.execute(
        "INSERT INTO system_ledger (timestamp, category, payload, status) VALUES (?, ?, ?, ?)",
        (timestamp, category, json.dumps(payload_dict), status)
    )
    conn.commit()
    conn.close()
    print(f"[LEDGER] Logged [{category}] -> Status: {status}")

if __name__ == "__main__":
    init_ledger()
    log_event("ROBOT_TELEMETRY", {"model": "AGILE_HUMANOID_V4", "fz": 9.81, "mesh": "SPINE_LEAF_100K"})
    log_event("FINANCIAL_AUDIT", {"source": "COINBASE_DEBIT", "pool_active": 6, "balance_usd": 5009200.00})
