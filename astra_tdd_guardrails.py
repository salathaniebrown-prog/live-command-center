import http.client, json, os, py_compile, subprocess, sys, time, unittest

HOME = os.path.expanduser("~")
PORTS = (8088, 8099, 8108, 8109, 8111, 8113, 8115, 8117, 8119, 8121)

START_MAP = {
    8088: (["python3", os.path.join(HOME, "dashboard_server.py")], os.path.join(HOME, "dashboard.log")),
    8099: (["python3", os.path.join(HOME, "dealership_module.py")], os.path.join(HOME, "dealership_8099.log")),
    8108: (["python3", os.path.join(HOME, "astra-unified-brain", "compute_router_8108_8109.py")], os.path.join(HOME, "astra-unified-brain", "router_8108_8109.log")),
    8109: (["python3", os.path.join(HOME, "astra-unified-brain", "compute_router_8108_8109.py")], os.path.join(HOME, "astra-unified-brain", "router_8108_8109.log")),
    8111: (["python3", os.path.join(HOME, "invoice_agent_8111.py")], os.path.join(HOME, "invoice_8111.log")),
    8113: (["python3", os.path.join(HOME, "astra-mediapipe-tasks", "mediapipe_edge_ml.py")], os.path.join(HOME, "astra-mediapipe-tasks", "mp.log")),
    8115: (["python3", os.path.join(HOME, "webhook_listener_8115.py")], os.path.join(HOME, "webhook_8115.log")),
    8117: (["python3", os.path.join(HOME, "trust_center_8117.py")], os.path.join(HOME, "trust_8117.log")),
    8119: (["python3", os.path.join(HOME, "agentic_mesh_8119.py")], os.path.join(HOME, "mesh_8119.log")),
    8121: (["python3", os.path.join(HOME, "studio_cinema_mcp_8121.py")], os.path.join(HOME, "cinema_8121.log")),
}

def auto_heal_all_python():
    sys.path.insert(0, HOME)
    try:
        from astra_ai_memory_healer import iterative_self_correct
    except Exception:
        iterative_self_correct = None

    for root, _, files in os.walk(HOME):
        if any(s in root for s in (".git", "astra-backups", "__pycache__", ".cache", "node_modules")):
            continue
        for fn in files:
            if fn.endswith(".py"):
                fpath = os.path.join(root, fn)
                if iterative_self_correct:
                    iterative_self_correct(fpath)

def ensure_services_running():
    for port, (cmd, log_file) in START_MAP.items():
        if not port_up(port) and os.path.exists(cmd):
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            lf = open(log_file, "a")
            subprocess.Popen(cmd, stdout=lf, stderr=lf, start_new_session=True)
            time.sleep(1.5)

def port_up(port):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.request("GET", "/")
        return c.getresponse().status == 200
    except Exception:
        return False

class AstraTddGuardrailSuite(unittest.TestCase):
    def test_01_all_python_modules_compile(self):
        failures = []
        for root, _, files in os.walk(HOME):
            if any(s in root for s in (".git", "astra-backups", "__pycache__", ".cache", "node_modules")):
                continue
            for fn in files:
                if fn.endswith(".py"):
                    p = os.path.join(root, fn)
                    try:
                        py_compile.compile(p, doraise=True)
                    except py_compile.PyCompileError as e:
                        failures.append(f"{os.path.relpath(p, HOME)}: {e.exc_value}")
        self.assertEqual(failures, [], f"Syntax compilation failures: {failures}")

    def test_02_zero_hardcoded_secrets(self):
        p1, p2 = "AI" + "za", "Astra" + "CS:"
        leaks = []
        for root, _, files in os.walk(HOME):
            if any(s in root for s in (".git", "astra-backups", "__pycache__", ".cache", "node_modules")):
                continue
            for fn in files:
                if fn.endswith((".py", ".sh", ".yml", ".yaml", ".json")):
                    p = os.path.join(root, fn)
                    txt = open(p, encoding="utf-8", errors="ignore").read()
                    if p1 in txt or p2 in txt:
                        leaks.append(os.path.relpath(p, HOME))
        self.assertEqual(leaks, [], f"Secret tokens detected in: {leaks}")

    def test_03_all_10_cluster_ports_online(self):
        offline = [p for p in PORTS if not port_up(p)]
        self.assertEqual(offline, [], f"Offline cluster ports: {offline}")

    def test_04_end_to_end_mesh_and_trust_contracts(self):
        c = http.client.HTTPConnection("127.0.0.1", 8119, timeout=8)
        body = json.dumps({"goal": "TDD Red-Green-Refactor guardrail contract check"}).encode("utf-8")
        c.request("POST", "/execute", body=body, headers={"Content-Type": "application/json"})
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        data = json.loads(r.read().decode())
        self.assertEqual(data.get("status"), "VALIDATED_MESH_OUTPUT")
        self.assertTrue(str(data.get("attestation_hash") or "").startswith("0x"))

if __name__ == "__main__":
    print("=== [TDD GUARDRAIL] PHASE 1: AUTO-HEALING & SERVICE BOOT ===")
    auto_heal_all_python()
    ensure_services_running()
    print("=== [TDD GUARDRAIL] PHASE 2: EXECUTING UNITTEST SUITE ===")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AstraTddGuardrailSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
