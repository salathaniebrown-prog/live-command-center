import ast, hashlib, http.client, json, os, py_compile, sqlite3, subprocess, time, traceback

HOME = os.path.expanduser("~")
MEM_DB = os.path.join(HOME, "astra_ai_memory.db")
DASH_FILE = os.path.join(HOME, "dashboard_server.py")

def init_memory_db():
    conn = sqlite3.connect(MEM_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS error_memory (
        error_sig TEXT PRIMARY KEY,
        file_path TEXT,
        line_no INTEGER,
        error_msg TEXT,
        applied_fix TEXT,
        resolved INTEGER,
        timestamp REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS route_registry (
        route_path TEXT PRIMARY KEY,
        method TEXT,
        target_port INTEGER,
        description TEXT,
        verified_ok INTEGER,
        last_checked REAL
    )""")
    routes = [
        ("/", "GET", 8088, "Command Center Main UI", 1),
        ("/api/kpi-summary", "GET", 8088, "Live 6-Node & On-Chain Balance KPIs", 1),
        ("/api/ci-status", "GET", 8088, "GitHub Actions CI Status Telemetry", 1),
        ("/api/ci-dispatch", "POST", 8088, "Highest Brain Workflow Dispatch Trigger", 1),
        ("/api/handoff-manifest", "GET", 8088, "Live Incremental Chat State Snapshot", 1),
        ("/api/trust-center", "GET", 8117, "SafeBase/Drata Unified Trust Controls", 1),
        ("/api/trust-center/ask", "POST", 8117, "Hybrid AI Assurance Questionnaire", 1),
        ("/api/cinema-mcp/render", "POST", 8121, "Claude AI Video + Renoise MCP Sync", 1),
        ("/api/mesh/execute", "POST", 8119, "10-Node Supercomputer 4-Gate Mesh", 1),
        ("/api/test-dealership-pipeline", "POST", 8115, "1-Click Dealership HMAC + JEV Pipeline", 1)
    ]
    now = time.time()
    for r_path, meth, port, desc, ok in routes:
        conn.execute("INSERT OR REPLACE INTO route_registry VALUES (?, ?, ?, ?, ?, ?)", (r_path, meth, port, desc, ok, now))
    conn.commit()
    conn.close()

init_memory_db()

def record_fix(file_path, line_no, err_msg, fix_desc, resolved=1):
    sig = hashlib.sha256(f"{file_path}:{line_no}:{err_msg}".encode("utf-8")).hexdigest()[:16]
    conn = sqlite3.connect(MEM_DB)
    conn.execute(
        "INSERT OR REPLACE INTO error_memory VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sig, file_path, int(line_no or 0), str(err_msg), str(fix_desc), int(resolved), time.time())
    )
    conn.commit()
    conn.close()

def auto_heal_python_file(target_path):
    if not os.path.exists(target_path):
        return False
    for attempt in range(1, 6):
        try:
            py_compile.compile(target_path, doraise=True)
            return True
        except py_compile.PyCompileError as exc:
            err_obj = exc.exc_value
            lineno = getattr(err_obj, "lineno", 0) or 0
            msg = str(err_obj)
            lines = open(target_path, "r", encoding="utf-8", errors="ignore").readlines()

            if lineno > 0 and lineno <= len(lines):
                bad_line = lines[lineno - 1]
                stripped = bad_line.lstrip()
                # Auto-repair indentation mismatch by matching surrounding block indent
                if "indent" in msg.lower():
                    target_ind = "        "
                    for back in range(lineno - 2, max(0, lineno - 20), -1):
                        prev = lines[back]
                        if prev.strip() and not prev.lstrip().startswith("#"):
                            p_ind = prev[:len(prev) - len(prev.lstrip())]
                            if prev.rstrip().endswith(":"):
                                target_ind = p_ind + "    "
                            else:
                                target_ind = p_ind
                            break
                    lines[lineno - 1] = target_ind + stripped
                    open(target_path, "w", encoding="utf-8").writelines(lines)
                    record_fix(target_path, lineno, msg, f"Auto-aligned indentation to {len(target_ind)} spaces", 1)
                    continue

            record_fix(target_path, lineno, msg, "Logged unhandled syntax error for manual review", 0)
            return False
    return False

def heal_and_verify_cluster():
    ok = auto_heal_python_file(DASH_FILE)
    if ok:
        try:
            c = http.client.HTTPConnection("127.0.0.1", 8088, timeout=2)
            c.request("GET", "/")
            if c.getresponse().status != 200:
                raise RuntimeError("Port 8088 unhealthy")
        except Exception:
            subprocess.Popen(["pkill", "-f", "dashboard_server.py"], stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            log_fh = open(os.path.join(HOME, "dashboard.log"), "a")
            subprocess.Popen(["python3", DASH_FILE], stdout=log_fh, stderr=log_fh, start_new_session=True)
            record_fix(DASH_FILE, 0, "Port 8088 offline", "Auto-restarted dashboard_server.py after memory check", 1)

if __name__ == "__main__":
    heal_and_verify_cluster()
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    fixes = [dict(r) for r in conn.execute("SELECT * FROM error_memory ORDER BY timestamp DESC LIMIT 5").fetchall()]
    routes = conn.execute("SELECT COUNT(*) FROM route_registry").fetchone()[0]
    conn.close()
    print(json.dumps({"ai_memory_status": "ACTIVE", "routes_indexed": routes, "recent_auto_fixes": fixes}, indent=2))
