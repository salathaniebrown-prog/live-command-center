import ast, hashlib, http.client, json, os, py_compile, sqlite3, subprocess, sys, time, uuid

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_ai_memory.db")

SERVICES = [
    (8088, "COMMAND_CENTER_UI", ["python3", os.path.join(HOME, "dashboard_server.py")], os.path.join(HOME, "dashboard.log")),
    (8099, "DEALERSHIP_MODULE", ["python3", os.path.join(HOME, "dealership_module.py")], os.path.join(HOME, "dealership_8099.log")),
    (8108, "STUDIO_PRO_COMPUTE", ["python3", os.path.join(HOME, "astra-unified-brain", "compute_router_8108_8109.py")], os.path.join(HOME, "astra-unified-brain", "router_8108_8109.log")),
    (8109, "UNIFIED_BRAIN_ROUTER", ["python3", os.path.join(HOME, "astra-unified-brain", "compute_router_8108_8109.py")], os.path.join(HOME, "astra-unified-brain", "router_8108_8109.log")),
    (8111, "JEV_INVOICE_AGENT", ["python3", os.path.join(HOME, "invoice_agent_8111.py")], os.path.join(HOME, "invoice_8111.log")),
    (8113, "EDGE_ML_MARKET", ["python3", os.path.join(HOME, "astra-mediapipe-tasks", "mediapipe_edge_ml.py")], os.path.join(HOME, "astra-mediapipe-tasks", "mp.log")),
    (8115, "CRYPTO_CARD_WEBHOOKS", ["python3", os.path.join(HOME, "webhook_listener_8115.py")], os.path.join(HOME, "webhook_8115.log")),
    (8117, "AGENTIC_TRUST_CENTER", ["python3", os.path.join(HOME, "trust_center_8117.py")], os.path.join(HOME, "trust_8117.log")),
    (8119, "SUPERCOMPUTER_MESH", ["python3", os.path.join(HOME, "agentic_mesh_8119.py")], os.path.join(HOME, "mesh_8119.log")),
    (8121, "CINEMA_RENOISE_MCP", ["python3", os.path.join(HOME, "studio_cinema_mcp_8121.py")], os.path.join(HOME, "cinema_8121.log")),
]

def init_validation_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS e2e_validation_runs (
        run_id TEXT PRIMARY KEY,
        static_passed INTEGER,
        ports_online TEXT,
        functional_tests_passed INTEGER,
        overall_score_pct REAL,
        report_json TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()

init_validation_db()

def stage_1_static_and_secret_audit():
    p1 = "AI" + "za"
    p2 = "Astra" + "CS:"
    compiled = 0
    errors = []
    for root, _, files in os.walk(HOME):
        if any(skip in root for skip in (".git", "astra-backups", "__pycache__", ".cache", "node_modules")):
            continue
        for fn in files:
            path = os.path.join(root, fn)
            if fn.endswith(".py"):
                try:
                    py_compile.compile(path, doraise=True)
                    compiled += 1
                except py_compile.PyCompileError as e:
                    errors.append(f"COMPILE_FAIL: {os.path.relpath(path, HOME)} -> {e.exc_value}")
            if fn.endswith((".py", ".sh", ".yml", ".yaml", ".json")):
                try:
                    txt = open(path, encoding="utf-8", errors="ignore").read()
                    if p1 in txt or p2 in txt:
                        errors.append(f"SECRET_LEAK: {os.path.relpath(path, HOME)}")
                except Exception:
                    pass
    return {"passed": len(errors) == 0, "modules_compiled": compiled, "errors": errors}

def probe_http(port, method="GET", path="/", body=None):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
        if body is not None:
            raw = json.dumps(body).encode("utf-8")
            c.request(method, path, body=raw, headers={"Content-Type": "application/json"})
        else:
            c.request(method, path)
        r = c.getresponse()
        data = r.read().decode("utf-8", errors="ignore")
        return r.status == 200, data
    except Exception as e:
        return False, str(e)

def stage_2_cluster_self_heal():
    online = 0
    details = []
    for port, name, cmd, log_path in SERVICES:
        ok, _ = probe_http(port)
        if not ok and os.path.exists(cmd[1]):
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            lf = open(log_path, "a")
            subprocess.Popen(cmd, stdout=lf, stderr=lf, start_new_session=True)
            time.sleep(1.5)
            ok, _ = probe_http(port)
        if ok:
            online += 1
        details.append({"port": port, "service": name, "online": ok})
    return {"online_count": online, "total": len(SERVICES), "nodes": details}

def stage_3_functional_e2e_smoke():
    tests = [
        ("KPI_SUMMARY_8088", 8088, "GET", "/api/kpi-summary", None),
        ("TRUST_AI_ASK_8117", 8117, "POST", "/ask", {"question": "Verify SOC 2 encryption"}),
        ("MESH_CONSENSUS_8119", 8119, "POST", "/execute", {"goal": "E2E meta-command validation"}),
        ("CINEMA_MCP_8121", 8121, "POST", "/render", {"prompt": "E2E beat sync check", "bpm": 128})
    ]
    passed = 0
    results = []
    for label, port, meth, path, payload in tests:
        ok, resp = probe_http(port, meth, path, payload)
        if ok:
            passed += 1
        results.append({"test": label, "port": port, "passed": ok})
    return {"passed_count": passed, "total": len(tests), "tests": results}

def execute_meta_validation_cycle():
    run_id = "E2E-" + uuid.uuid4().hex[:8].upper()
    s1 = stage_1_static_and_secret_audit()
    s2 = stage_2_cluster_self_heal()
    s3 = stage_3_functional_e2e_smoke()

    total_checks = 1 + s2["total"] + s3["total"]
    passed_checks = (1 if s1["passed"] else 0) + s2["online_count"] + s3["passed_count"]
    score = round((passed_checks / max(1, total_checks)) * 100.0, 1)

    report = {
        "run_id": run_id,
        "overall_score_pct": score,
        "stage_1_static_audit": s1,
        "stage_2_cluster_nodes": f"{s2['online_count']}/{s2['total']}",
        "stage_3_e2e_smoke": f"{s3['passed_count']}/{s3['total']}",
        "offline_or_failing": [n for n in s2["nodes"] if not n["online"]] + [t for t in s3["tests"] if not t["passed"]]
    }

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO e2e_validation_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, 1 if s1["passed"] else 0, report["stage_2_cluster_nodes"], s3["passed_count"], score, json.dumps(report), time.time())
    )
    conn.commit()
    conn.close()
    return report

if __name__ == "__main__":
    print(json.dumps(execute_meta_validation_cycle(), indent=2))
