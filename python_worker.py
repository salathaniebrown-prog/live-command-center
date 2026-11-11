import json
import time
from datetime import datetime, timezone

def log_to_spine(worker_name, status, payload):
    entry = {
        "source": worker_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "data": payload
    }
    with open("telemetry_spine.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    print("[PYTHON-WORKER] Feeding telemetry into spine...")
    count = 1
    while True:
        log_to_spine("python-worker", "ACTIVE", {"tasks_completed": count})
        count += 1
        time.sleep(2)
