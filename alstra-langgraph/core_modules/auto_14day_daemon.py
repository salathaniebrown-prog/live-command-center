import time
import json
import urllib.request
import os

GATEWAY_URL = "http://127.0.0.1:8099/api/v1/bioscience/lab"
LOG_FILE = os.path.expanduser("~/alstra-langgraph/ledger/auto_persistence_daemon.log")

def run_daemon_pulse():
    print("[*] Starting Background 14-Day Sovereign Persistence Loop...")
    while True:
        payload = {
            "sample_id": "BIO-GENOMIC-14DAY-AUTOMATED-LOCK",
            "assay": "CONTINUOUS_BACKGROUND_PERSISTENCE"
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(GATEWAY_URL, data=data, headers={"Content-Type": "application/json", "X-API-Key": "ALSTRA-ADMIN-TOKEN-bc_iqr25ias-SECURE"}, method="POST")
        
        try:
            with urllib.request.urlopen(req) as resp:
                res = json.loads(resp.read().decode())
                log_data = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "status": "DAEMON_PULSE_OK",
                    "response": res
                }
                with open(LOG_FILE, "a") as f:
                    f.write(json.dumps(log_data) + "\n")
                print(f"[+] [{log_data['timestamp']}] Background Persistence Pulse Locked.")
        except Exception as e:
            print(f"[!] Daemon Pulse Error: {e}")
        
        time.sleep(30) # Continuous pulse every 30 seconds

if __name__ == "__main__":
    run_daemon_pulse()
