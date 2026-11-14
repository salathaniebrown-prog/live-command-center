import hashlib, http.client, json, os, py_compile, shutil, sqlite3, subprocess, sys, time, uuid

HOME = os.path.expanduser("~")
MEM_DB = os.path.join(HOME, "astra_ai_memory.db")
CKPT_DIR = os.path.join(HOME, ".astra_atomic_checkpoints")
os.makedirs(CKPT_DIR, exist_ok=True)

NON_RETRYABLE_PATTERNS = ("PermissionError", "FileNotFoundError", "InvalidPortSpec")

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

def port_alive(port):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.request("GET", "/")
        return c.getresponse().status == 200
    except Exception:
        return False

# --- ATOMIC CHECKPOINT & ROLLBACK MANAGER ---
def create_atomic_checkpoint(ckpt_id, file_paths):
    snap_dir = os.path.join(CKPT_DIR, ckpt_id)
    os.makedirs(snap_dir, exist_ok=True)
    manifest = {}
    for fp in file_paths:
        if os.path.exists(fp):
            dst = os.path.join(snap_dir, os.path.basename(fp))
            shutil.copy2(fp, dst)
            manifest[fp] = dst
    return manifest

def rollback_checkpoint(manifest):
    restored = []
    for orig, snap in manifest.items():
        if os.path.exists(snap):
            shutil.copy2(snap, orig)
            restored.append(os.path.basename(orig))
    return restored

# --- ROLE 1: ARCHITECT (PLANS TARGET SPECIFICATIONS & NON-RETRYABLE CLASSIFICATION) ---
def role_architect_plan():
    offline = [p for p in sorted(SERVICES.keys()) if not port_alive(p)]
    plan = []
    for p in offline:
        sp, lp = SERVICES[p]
        err_tail = ""
        if os.path.exists(lp):
            err_tail = open(lp, "r", encoding="utf-8", errors="ignore").read()[-800:]
        retryable = not any(pat in err_tail for pat in NON_RETRYABLE_PATTERNS)
        plan.append({
            "port": p,
            "script": sp,
            "log": lp,
            "retryable": retryable,
            "strategy": "SIGKILL_RECLAIM_AND_BOOT" if "Address already in use" in err_tail else "CLEAN_DAEMON_BOOT"
        })
    return plan

# --- ROLE 2: WORKER (EXECUTES ISOLATED PATCH & SERVICE START) ---
def role_worker_execute(plan_items):
    executed = []
    for item in plan_items:
        if not item["retryable"]:
            executed.append({"port": item["port"], "status": "SKIPPED_NON_RETRYABLE"})
            continue
        sp = item["script"]
        lp = item["log"]
        if not os.path.exists(sp):
            executed.append({"port": item["port"], "status": "MISSING_FILE"})
            continue
        py_compile.compile(sp, doraise=True)
        subprocess.run(["pkill", "-9", "-f", os.path.basename(sp)], stderr=subprocess.DEVNULL)
        time.sleep(0.6)
        os.makedirs(os.path.dirname(lp), exist_ok=True)
        lf = open(lp, "w")
        subprocess.Popen(["python3", sp], stdout=lf, stderr=lf, start_new_session=True)
        time.sleep(2.5)
        executed.append({"port": item["port"], "status": "BOOTED", "strategy": item["strategy"]})
    return executed

# --- ROLE 3: TEST RUNNER (DETERMINISTIC HARNESS) ---
def role_test_runner_validate():
    still_offline = [p for p in sorted(SERVICES.keys()) if not port_alive(p)]
    return {"all_10_online": len(still_offline) == 0, "offline_ports": still_offline}

# --- ROLE 4: CRITIC (LOOP DETECTOR & ROLLBACK JUDGE) ---
def run_4agent_autonomous_cycle(max_cycles=3):
    session_id = "AGENT4-" + uuid.uuid4().hex[:8].upper()
    tracked_files = (os.path.join(HOME, "dashboard_server.py"), os.path.join(HOME, "agentic_mesh_8119.py"))
    ckpt = create_atomic_checkpoint(session_id, tracked_files)
    seen_states = set()
    trace = []

    for cycle in range(1, max_cycles + 1):
        plan = role_architect_plan()
        if not plan:
            trace.append({"cycle": cycle, "verdict": "CRITIC_APPROVED_ALL_GREEN"})
            break

        state_sig = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
        if state_sig in seen_states:
            rolled = rollback_checkpoint(ckpt)
            trace.append({"cycle": cycle, "verdict": "CRITIC_HALT_REPEATED_FAILURE_ROLLED_BACK", "restored": rolled})
            break
        seen_states.add(state_sig)

        work_log = role_worker_execute(plan)
        test_res = role_test_runner_validate()
        trace.append({"cycle": cycle, "worker": work_log, "test_runner": test_res})
        if test_res["all_10_online"]:
            break

    final_check = role_test_runner_validate()
    conn = sqlite3.connect(MEM_DB, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS four_agent_sessions (
        session_id TEXT PRIMARY KEY,
        approved INTEGER,
        trace_json TEXT,
        timestamp REAL
    )""")
    conn.execute("INSERT INTO four_agent_sessions VALUES (?, ?, ?, ?)", (session_id, 1 if final_check["all_10_online"] else 0, json.dumps(trace), time.time()))
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "checkpoint_id": session_id,
        "critic_approved": final_check["all_10_online"],
        "final_test_runner": final_check,
        "agent_trace": trace
    }

if __name__ == "__main__":
    print(json.dumps(run_4agent_autonomous_cycle(), indent=2))
