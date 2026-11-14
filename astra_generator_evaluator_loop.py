import hashlib, http.client, json, os, py_compile, sqlite3, subprocess, time, uuid

HOME = os.path.expanduser("~")
MEM_DB = os.path.join(HOME, "astra_ai_memory.db")
MAX_RETRIES = 4

SERVICES = {
    8088: (os.path.join(HOME, "dashboard_server.py"), os.path.join(HOME, "dashboard.log")),
    8099: (os.path.join(HOME, "dealership_module.py"), os.path.join(HOME, "dealership_8099.log")),
    8108: (os.path.join(HOME, "astra-unified-brain", "compute_router_8108_8109.py"), os.path.join(HOME, "astra-unified-brain", "router_8108_8109.log")),
    8109: (os.path.join(HOME, "astra-unified-brain", "compute_router_8108_8109.py"), os.path.join(HOME, "astra-unified-brain", "router_8108_8109.log")),
    8111: (os.path.join(HOME, "invoice_agent_8111.py"), os.path.join(HOME, "invoice_8111.log")),
    8113: (os.path.join(HOME, "astra-mediapipe-tasks", "mediapipe_edge_ml.py"), os.path.join(HOME, "astra-mediapipe-tasks", "mp.log")),
    8115: (os.path.join(HOME, "webhook_listener_8115.py"), os.path.join(HOME, "webhook_8115.log")),
    8117: (os.path.join(HOME, "trust_center_8117.py"), os.path.join(HOME, "trust_8117.log")),
    8119: (os.path.join(HOME, "agentic_mesh_8119.py"), os.path.join(HOME, "mesh_8119.log")),
    8121: (os.path.join(HOME, "studio_cinema_mcp_8121.py"), os.path.join(HOME, "cinema_8121.log")),
}

def check_port(port):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.request("GET", "/")
        return c.getresponse().status == 200
    except Exception:
        return False

def read_runtime_traceback(log_path):
    if not os.path.exists(log_path):
        return ""
    txt = open(log_path, "r", encoding="utf-8", errors="ignore").read()[-1200:].strip()
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    return " | ".join(lines[-5:]) if lines else ""

# --- EVALUATOR: STATIC SYNTAX + LIVE PORT + RUNTIME LOG TELEMETRY ---
def evaluate_environment():
    syntax_signals = []
    skip_dirs = (".git", "astra-backups", "astra-enterprise-core", "nexus-brown", "__pycache__", ".cache", "node_modules")
    for root, _, files in os.walk(HOME):
        if any(s in root for s in skip_dirs):
            continue
        for fn in files:
            if fn.endswith(".py"):
                fpath = os.path.join(root, fn)
                try:
                    py_compile.compile(fpath, doraise=True)
                except py_compile.PyCompileError as exc:
                    err = exc.exc_value
                    syntax_signals.append({
                        "file": fpath,
                        "line": getattr(err, "lineno", 0) or 0,
                        "msg": str(err)
                    })

    offline_telemetry = []
    for p in sorted(SERVICES.keys()):
        if not check_port(p):
            script_path, log_path = SERVICES[p]
            offline_telemetry.append({
                "port": p,
                "script": os.path.basename(script_path),
                "runtime_trace": read_runtime_traceback(log_path)
            })

    passed = (len(syntax_signals) == 0) and (len(offline_telemetry) == 0)
    return {"passed": passed, "syntax_signals": syntax_signals, "offline_telemetry": offline_telemetry}

# --- GENERATOR: ACTIONABLE RUNTIME & SYNTAX REPAIR ---
def apply_actionable_patch(eval_report):
    actions = []
    for item in eval_report.get("offline_telemetry") or []:
        port = item["port"]
        script_path, log_path = SERVICES[port]
        if not os.path.exists(script_path):
            continue

        # Ensure SO_REUSEADDR is active before starting
        src = open(script_path, "r", encoding="utf-8").read()
        if "allow_reuse_address = True" not in src:
            src = "import http.server\nhttp.server.HTTPServer.allow_reuse_address = True\n" + src
            open(script_path, "w", encoding="utf-8").write(src)

        subprocess.run(["pkill", "-f", os.path.basename(script_path)], stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        lf = open(log_path, "w")
        subprocess.Popen(["python3", script_path], stdout=lf, stderr=lf, start_new_session=True)
        time.sleep(2.5)
        up = check_port(port)
        trace_after = "" if up else read_runtime_traceback(log_path)
        actions.append({
            "port": port,
            "restarted": os.path.basename(script_path),
            "online_after_patch": up,
            "stderr_if_failed": trace_after
        })
    return actions

def run_generator_evaluator_loop():
    loop_id = "LOOP-" + uuid.uuid4().hex[:8].upper()
    seen_fps = set()
    history = []

    for attempt in range(1, MAX_RETRIES + 1):
        report = evaluate_environment()
        if report["passed"]:
            history.append({"attempt": attempt, "status": "CONVERGED_GREEN", "actions": []})
            break

        fp = hashlib.sha256(json.dumps(report, sort_keys=True).encode("utf-8")).hexdigest()
        if fp in seen_fps:
            history.append({"attempt": attempt, "status": "CIRCUIT_BREAKER_HALT", "report": report})
            break
        seen_fps.add(fp)

        patches = apply_actionable_patch(report)
        history.append({"attempt": attempt, "status": "PATCHED_AND_RETRIED", "actions": patches})

    final_eval = evaluate_environment()
    conn = sqlite3.connect(MEM_DB, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_loop_runs (
        loop_id TEXT PRIMARY KEY,
        converged INTEGER,
        attempts_used INTEGER,
        history_json TEXT,
        timestamp REAL
    )""")
    conn.execute("INSERT INTO agent_loop_runs VALUES (?, ?, ?, ?, ?)", (loop_id, 1 if final_eval["passed"] else 0, len(history), json.dumps(history), time.time()))
    conn.commit()
    conn.close()

    return {
        "loop_id": loop_id,
        "converged_green": final_eval["passed"],
        "attempts_used": len(history),
        "final_evaluation": final_eval,
        "execution_trace": history
    }

if __name__ == "__main__":
    print(json.dumps(run_generator_evaluator_loop(), indent=2))
