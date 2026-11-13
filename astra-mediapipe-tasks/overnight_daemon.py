import os, time, json, subprocess, urllib.request

HOME = os.path.expanduser("~")
LOG = os.path.join(HOME, "astra-mediapipe-tasks", "overnight.log")

def ensure_service(proc_name, script_path, log_path, port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
            if r.status == 200:
                return True
    except Exception:
        subprocess.Popen(f"setsid nohup python3 {script_path} > {log_path} 2>&1 < /dev/null &", shell=True)
        time.sleep(2)
        return False

def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

while True:
    try:
        ensure_service("dashboard_server.py", os.path.join(HOME, "dashboard_server.py"), os.path.join(HOME, "dashboard.log"), 8088)
        ensure_service("mediapipe_edge_ml.py", os.path.join(HOME, "astra-mediapipe-tasks", "mediapipe_edge_ml.py"), os.path.join(HOME, "astra-mediapipe-tasks", "mp.log"), 8113)
        goal_res = post_json("http://127.0.0", {"goal": "Test device and fetch live ETH crypto price"})
        pb_res = post_json("http://127.0.0", {})
        with open(LOG, "a") as f:
            f.write(json.dumps({"cycle": "OK", "goal_status": goal_res.get("status"), "actions": goal_res.get("results"), "playback_pass_pct": pb_res.get("pass_rate_pct"), "avg_ms": pb_res.get("avg_latency_ms")}) + "\n")
    except Exception as e:
        with open(LOG, "a") as f:
            f.write(json.dumps({"cycle": "ERROR", "detail": str(e)}) + "\n")
    time.sleep(300)
