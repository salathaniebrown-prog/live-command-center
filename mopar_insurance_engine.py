import sqlite3
import time
import json
import random

DB_PATH = "/tmp/astra_deepspace_ledger.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS master_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            payload TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def log_event(event_type, payload):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO master_events (event_type, payload) VALUES (?, ?);",
        (event_type, json.dumps(payload))
    )
    conn.commit()
    conn.close()
    print(f"[{time.strftime('%X')}] Ledger Synced: {event_type}")

if __name__ == "__main__":
    init_db()
    
    parts = [
        {"sku": "TR6060-HELLCAT", "amount": 5650.00, "channel": "mopar_transmission"},
        {"sku": "FORG-24-CUBAN", "amount": 3100.00, "channel": "custom_wheels_rims"},
        {"sku": "MOPAR-HEMI-62L", "amount": 9400.00, "channel": "engine_crate"}
    ]
    
    while True:
        choice = random.choice(["MOPAR", "INSURANCE"])
        if choice == "MOPAR":
            item = random.choice(parts)
            payload = {
                "channel": item["channel"],
                "sku": item["sku"],
                "amount": item["amount"],
                "routing": "053100465",
                "account": "8823901421",
                "status": "FULFILLED_PAID"
            }
            log_event("MOPAR_AUTOMOTIVE", payload)
        else:
            payload = {
                "channel": "insurance_auto_agent",
                "policy_id": f"POL-AUTO-2026-{random.randint(800, 999)}",
                "amount": round(random.uniform(150.00, 220.00), 2),
                "routing": "053100465",
                "account": "8823901421",
                "status": "QUOTE_BOUND"
            }
            log_event("INSURANCE_AUTO", payload)
            
        time.sleep(10)
