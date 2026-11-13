import json, urllib.request

def execute_sovereign_telemetry():
    endpoints = [
        ("/api/os/reason", {"goal": "Fable 5.2 multi-step telemetry validation"}),
        ("/api/ooda/execute", {"directive": "Execute elite telemetry sweep", "amount_usd": 0}),
        ("/api/legal/audit", {"query": "Audit Wyler VIN title and crypto escrow ring-fence"})
    ]
    for path, payload in endpoints:
        req = urllib.request.Request(
            f"http://127.0.0.1:8088{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                print(f"[TELEMETRY OK] {path} -> HTTP {res.status}")
        except Exception as e:
            print(f"[TELEMETRY ERR] {path} -> {e}")

if __name__ == "__main__":
    execute_sovereign_telemetry()
