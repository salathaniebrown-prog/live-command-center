import http.client, json, os, py_compile, subprocess, time

HOME = os.path.expanduser("~")
PORTS = (8088, 8099, 8108, 8109, 8111, 8113, 8115)

def check_ports():
    for p in PORTS:
        try:
            c = http.client.HTTPConnection("127.0.0.1", p, timeout=2)
            c.request("GET", "/")
            c.getresponse().read()
        except Exception:
            if p == 8113:
                subprocess.Popen(["python3", f"{HOME}/astra-mediapipe-tasks/mediapipe_edge_ml.py"], start_new_session=True)
            elif p == 8099:
                subprocess.Popen(["python3", f"{HOME}/dealership_module.py"], start_new_session=True)

def heal_tunnel():
    log = f"{HOME}/tunnel.log"
    if not os.path.exists(log) or "Registered tunnel connection" not in open(log, errors="ignore").read():
        subprocess.Popen(["bash", f"{HOME}/start_tunnel.sh"])

def post_push_ci():
    state = f"{HOME}/.astra_last_ci_sha"
    try:
        sha = subprocess.check_output(["git", "-C", HOME, "rev-parse", "HEAD"]).decode().strip()
        rem = subprocess.check_output(["git", "-C", HOME, "rev-parse", "origin/main"]).decode().strip()
    except Exception:
        return
    if not sha or sha != rem or (os.path.exists(state) and open(state).read().strip() == sha):
        return
    open(state, "w").write(sha)
    try:
        c = http.client.HTTPConnection("127.0.0.1", 8088, timeout=5)
        c.request("POST", "/api/ci-dispatch")
        c.getresponse().read()
    except Exception:
        pass
    log = f"{HOME}/astra-unified-brain/ci_poll.log"
    for _ in range(12):
        try:
            c = http.client.HTTPConnection("127.0.0.1", 8088, timeout=5)
            c.request("GET", "/api/ci-status")
            runs = json.loads(c.getresponse().read().decode()).get("runs") or []
            for r in runs:
                if str(r.get("head_sha") or "").startswith(sha[:7]):
                    st, conc = r.get("status"), r.get("conclusion")
                    open(log, "a").write(f"{sha[:7]} status={st} conclusion={conc}\n")
                    if st == "completed":
                        return
        except Exception:
            pass
        time.sleep(8)

def run_watchdog_daemon():
    while True:
        try:
            check_ports()
            heal_tunnel()
            post_push_ci()
        except Exception:
            pass
        time.sleep(30)

if __name__ == "__main__":
    run_watchdog_daemon()
