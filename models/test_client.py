import urllib.request
import json
import sqlite3
import sys

def test_api_gateway():
    print("[*] 1. Testing FastAPI Gateway (http://127.0.0.1:8000)...")
    try:
        url = "http://127.0.0.1:8000/api/v1/telemetry/metrics"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                print(f"    [✔] SUCCESS: Gateway online. Account: {data.get('account_holder', 'N/A')}")
                return True
    except Exception as e:
        print(f"    [✘] FAILED: Could not reach Gateway on port 8000 ({e})")
        return False

def test_sqlite_ledger():
    print("[*] 2. Testing SQLite Deep-Space Ledger (/tmp/astra_deepspace_ledger.db)...")
    try:
        conn = sqlite3.connect("/tmp/astra_deepspace_ledger.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM master_events;")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT event_type, timestamp FROM master_events ORDER BY id DESC LIMIT 1;")
        latest = cursor.fetchone()
        conn.close()
        print(f"    [✔] SUCCESS: Ledger verified. Total Events: {count} | Latest Event: {latest[0] if latest else 'None'}")
        return True
    except Exception as e:
        print(f"    [✘] FAILED: Ledger connection issue ({e})")
        return False

def test_web_ui():
    print("[*] 3. Testing Web Command UI Server (http://127.0.0.1:8080)...")
    try:
        url = "http://127.0.0.1:8080"
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status == 200:
                print("    [✔] SUCCESS: Web UI Server responding on port 8080")
                return True
    except Exception as e:
        print(f"    [✘] FAILED: Web UI Server not responding ({e})")
        return False

if __name__ == "__main__":
    print("==================================================")
    print("   ROM/TEC AI CORE — LIVE VERIFICATION CLIENT   ")
    print("==================================================")
    g_ok = test_api_gateway()
    db_ok = test_sqlite_ledger()
    ui_ok = test_web_ui()
    print("--------------------------------------------------")
    if g_ok and db_ok and ui_ok:
        print("[★] SYSTEM STATUS: ALL LIVE PIPELINES OPERATIONAL")
    else:
        print("[!] SYSTEM STATUS: PARTIAL DEGRADATION DETECTED")
    print("==================================================")
