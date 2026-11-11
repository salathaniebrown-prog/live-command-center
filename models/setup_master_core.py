import os
import sqlite3
import subprocess

DB_PATH = "/tmp/astra_deepspace_ledger.db"

def verify_and_heal():
    print("[*] Running ROM/TEC Self-Healing Diagnostic...")
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS master_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, payload TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
        conn.close()
        print("[+] Initialized missing deep-space SQLite ledger.")
    
    # Ensure PM2 resurrects processes correctly
    subprocess.run(["pm2", "save"], check=True)
    print("[+] Master Core Architecture stabilized and synced.")

if __name__ == "__main__":
    verify_and_heal()
