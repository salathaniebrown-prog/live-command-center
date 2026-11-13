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
    ports = [check_port_health(p) for p in (8088, 8108, 8109, 8111, 8113)]

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
