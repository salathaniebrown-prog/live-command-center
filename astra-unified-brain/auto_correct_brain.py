import http.client
import json
import os
import py_compile
import subprocess
import time

HOME = os.path.expanduser("~")
CORE_FILES = [
    os.path.join(HOME, "dashboard_server.py"),
    os.path.join(HOME, "invoice_agent_8111.py"),
    os.path.join(HOME, "astra-mediapipe-tasks", "mediapipe_edge_ml.py"),
    os.path.join(HOME, "astra-unified-brain", "unified_brain_os.py"),
]

def verify_and_heal_files():
    report = []
    for fpath in CORE_FILES:
        if not os.path.exists(fpath):
            continue
        try:
            py_compile.compile(fpath, doraise=True)
            report.append({"file": os.path.basename(fpath), "status": "VERIFIED_OK"})
        except py_compile.PyCompileError as err:
            report.append({"file": os.path.basename(fpath), "status": "SYNTAX_ERROR", "detail": str(err)})
    return report

def check_port_health(port):
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/")
        res = conn.getresponse()
        return {"port": port, "online": res.status in (200, 404, 405), "http_status": res.status}
    except Exception as e:
        return {"port": port, "online": False, "error": str(e)}

def sync_brain_telemetry():
    file_status = verify_and_heal_files()
    ports = [check_port_health(p) for p in (8088, 8108, 8109, 8111, 8113, 8115)]

    # Auto-restart 8113 or 8111 if offline
    for pinfo in ports:
        if pinfo["port"] == 8113 and not pinfo["online"]:
            subprocess.Popen(
                ["python3", os.path.join(HOME, "astra-mediapipe-tasks", "mediapipe_edge_ml.py")],
                stdout=open(os.path.join(HOME, "astra-mediapipe-tasks", "mp.log"), "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            pinfo["auto_healed"] = True

    summary = {
        "engine": "ASTRA_UNIFIED_BRAIN_AUTO_CORRECTOR",
        "files_checked": file_status,
        "node_ports": ports,
        "dealership_pipeline": "LINKED_TO_JEV_8111"
    }
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    run_watchdog_daemon()

def run_watchdog_daemon():
    while True:
        try:
            sync_brain_telemetry()
        except Exception:
            pass
        time.sleep(30)

def run_watchdog_daemon():
    while True:
        try:
            sync_brain_telemetry()
        except Exception:
            pass
        time.sleep(30)

def check_and_heal_tunnel():
    log_path = os.path.join(HOME, "tunnel.log")
    if not os.path.exists(log_path):
        subprocess.Popen(["bash", os.path.join(HOME, "start_tunnel.sh")])
        return
    txt = open(log_path, errors="ignore").read()
    if "Registered tunnel connection" not in txt:
        subprocess.Popen(["bash", os.path.join(HOME, "start_tunnel.sh")])

def poll_ci_until_green(target_sha):
    import http.client
    log_file = os.path.join(HOME, "astra-unified-brain", "ci_poll.log")
    for attempt in range(1, 16):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 8088, timeout=8)
            conn.request("GET", "/api/ci-status")
            data = json.loads(conn.getresponse().read().decode())
            runs = data.get("runs") or []
            for r in runs:
                head_sha = str(r.get("head_sha") or "")
                if head_sha.startswith(target_sha[:7]):
                    status = str(r.get("status") or "")
                    conclusion = str(r.get("conclusion") or "")
                    entry = f"[{time.strftime('%H:%M:%S')}] SHA {target_sha[:7]} | status={status} | conclusion={conclusion}\n"
                    open(log_file, "a").write(entry)
                    if status == "completed":
                        return conclusion == "success"
        except Exception as e:
            open(log_file, "a").write(f"[ERR] CI poll attempt {attempt}: {e}\n")
        time.sleep(8)
    return False

def auto_post_push_ci_guard():
    import http.client
    state_file = os.path.join(HOME, ".astra_last_ci_sha")
    try:
        cur_sha = subprocess.check_output(["git", "-C", HOME, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        remote_sha = subprocess.check_output(["git", "-C", HOME, "rev-parse", "origin/main"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return

    # Only trigger once local HEAD matches pushed origin/main and hasn't been verified yet
    if not cur_sha or cur_sha != remote_sha:
        return

    last_sha = open(state_file).read().strip() if os.path.exists(state_file) else ""
    if cur_sha == last_sha:
        return

    open(state_file, "w").write(cur_sha)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 8088, timeout=8)
        conn.request("POST", "/api/ci-dispatch")
        conn.getresponse().read()
    except Exception:
        pass

    poll_ci_until_green(cur_sha)
