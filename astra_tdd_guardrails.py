import hashlib, http.client, json, os, py_compile, sqlite3, subprocess, sys, time, unittest, uuid

HOME = os.path.expanduser("~")
MEM_DB = os.path.join(HOME, "astra_ai_memory.db")
PORTS = (8088, 8099, 8108, 8109, 8111, 8113, 8115, 8117, 8119, 8121)

START_MAP = {
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

# Formal Contract Specifications for Critical Supercomputer Endpoints
CONTRACT_SPECS = {
    "KPI_SUMMARY_8088": {
        "port": 8088, "method": "GET", "path": "/api/kpi-summary", "payload": None,
        "required_keys": ("uptime_pct", "nodes_online", "probe_latency_ms")
    },
    "TRUST_CENTER_8117": {
        "port": 8117, "method": "POST", "path": "/ask",
        "payload": {"question": "TDD contract verification"},
        "required_keys": ("query_id", "answer", "attestation_hash")
    },
    "MESH_CONSENSUS_8119": {
        "port": 8119, "method": "POST", "path": "/execute",
        "payload": {"goal": "TDD contract specification check"},
        "required_keys": ("exec_id", "status", "validation_score_pct", "attestation_hash")
    },
    "CINEMA_MCP_8121": {
        "port": 8121, "method": "POST", "path": "/render",
        "payload": {"prompt": "TDD cinema beat check", "bpm": 128, "fps": 24},
        "required_keys": ("project_id", "status", "storyboard", "attestation_hash")
    }
}

def port_up(port):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
        c.request("GET", "/")
        return c.getresponse().status == 200
    except Exception:
        return False

def auto_heal_and_boot():
    sys.path.insert(0, HOME)
    try:
        from astra_ai_memory_healer import iterative_self_correct
    except Exception:
        iterative_self_correct = None

    for root, _, files in os.walk(HOME):
        if any(s in root for s in (".git", "astra-backups", "astra-enterprise-core", "nexus-brown", "__pycache__", ".cache", "node_modules")):
            continue
        for fn in files:
            if fn.endswith(".py") and iterative_self_correct:
                iterative_self_correct(os.path.join(root, fn))

    for port, (script_path, log_path) in START_MAP.items():
        if not port_up(port) and os.path.exists(script_path):
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            lf = open(log_path, "a")
            subprocess.Popen(["python3", script_path], stdout=lf, stderr=lf, start_new_session=True)
            time.sleep(1.5)

def record_tdd_telemetry(passed, total, duration_ms, details):
    conn = sqlite3.connect(MEM_DB, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS tdd_telemetry (
        run_id TEXT PRIMARY KEY,
        tests_passed INTEGER,
        tests_total INTEGER,
        duration_ms REAL,
        status TEXT,
        details_json TEXT,
        timestamp REAL
    )""")
    run_id = "TDD-" + uuid.uuid4().hex[:8].upper()
    st = "GREEN_PASS" if passed == total else "RED_FAIL"
    conn.execute("INSERT INTO tdd_telemetry VALUES (?, ?, ?, ?, ?, ?, ?)", (run_id, passed, total, duration_ms, st, json.dumps(details), time.time()))
    conn.commit()
    conn.close()
    return run_id, st

class AstraTddContractSuite(unittest.TestCase):
    def test_01_static_syntax_hygiene(self):
        failures = []
        for root, _, files in os.walk(HOME):
            if any(s in root for s in (".git", "astra-backups", "astra-enterprise-core", "nexus-brown", "__pycache__", ".cache", "node_modules")):
                continue
            for fn in files:
                if fn.endswith(".py"):
                    p = os.path.join(root, fn)
                    try:
                        py_compile.compile(p, doraise=True)
                    except py_compile.PyCompileError as e:
                        failures.append(f"{os.path.relpath(p, HOME)}: {e.exc_value}")
        self.assertEqual(failures, [], f"Syntax failures: {failures}")

    def test_02_zero_secret_exposure(self):
        p1, p2 = "AI" + "za", "Astra" + "CS:"
        leaks = []
        for root, _, files in os.walk(HOME):
            if any(s in root for s in (".git", "astra-backups", "astra-enterprise-core", "nexus-brown", "__pycache__", ".cache", "node_modules")):
                continue
            for fn in files:
                if fn.endswith((".py", ".sh", ".yml", ".yaml", ".json")):
                    p = os.path.join(root, fn)
                    txt = open(p, encoding="utf-8", errors="ignore").read()
                    if p1 in txt or p2 in txt:
                        leaks.append(os.path.relpath(p, HOME))
        self.assertEqual(leaks, [], f"Secret leaks: {leaks}")

    def test_03_all_10_cluster_ports_live(self):
        offline = [p for p in PORTS if not port_up(p)]
        self.assertEqual(offline, [], f"Offline ports: {offline}")

    def test_04_formal_api_contract_specifications(self):
        for name, spec in CONTRACT_SPECS.items():
            c = http.client.HTTPConnection("127.0.0.1", spec["port"], timeout=8)
            if spec["payload"] is not None:
                body = json.dumps(spec["payload"]).encode("utf-8")
                c.request(spec["method"], spec["path"], body=body, headers={"Content-Type": "application/json"})
            else:
                c.request(spec["method"], spec["path"])
            r = c.getresponse()
            self.assertEqual(r.status, 200, f"{name} returned HTTP {r.status}")
            data = json.loads(r.read().decode())
            for req_key in spec["required_keys"]:
                self.assertIn(req_key, data, f"{name} missing contract key: {req_key}")

if __name__ == "__main__":
    t0 = time.time()
    auto_heal_and_boot()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AstraTddContractSuite)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    dur_ms = round((time.time() - t0) * 1000.0, 1)
    passed = res.testsRun - len(res.failures) - len(res.errors)
    run_id, status = record_tdd_telemetry(passed, res.testsRun, dur_ms, {"failures": len(res.failures), "errors": len(res.errors)})
    print(f"=== [TDD TELEMETRY] {run_id} | {status} ({passed}/{res.testsRun}) in {dur_ms}ms ===")
    sys.exit(0 if res.wasSuccessful() else 1)
