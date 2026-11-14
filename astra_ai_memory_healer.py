import ast, hashlib, http.client, json, os, py_compile, re, sqlite3, subprocess, time

HOME = os.path.expanduser("~")
MEM_DB = os.path.join(HOME, "astra_ai_memory.db")
DASH_FILE = os.path.join(HOME, "dashboard_server.py")

def get_db():
    conn = sqlite3.connect(MEM_DB, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def init_memory_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS error_memory (
        error_sig TEXT PRIMARY KEY,
        file_path TEXT,
        line_no INTEGER,
        error_msg TEXT,
        applied_fix TEXT,
        resolved INTEGER,
        timestamp REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS code_mirrors (
        file_path TEXT PRIMARY KEY,
        sha256_hash TEXT,
        known_good_code TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()

init_memory_db()

def save_good_mirror(file_path):
    if not os.path.exists(file_path):
        return
    try:
        py_compile.compile(file_path, doraise=True)
        code = open(file_path, "r", encoding="utf-8", errors="ignore").read()
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO code_mirrors VALUES (?, ?, ?, ?)", (file_path, digest, code, time.time()))
        conn.commit()
        conn.close()
    except Exception:
        pass

def record_fix(file_path, line_no, err_msg, fix_desc, resolved=1):
    sig = hashlib.sha256(f"{file_path}:{line_no}:{err_msg}".encode("utf-8")).hexdigest()[:16]
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO error_memory VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sig, file_path, int(line_no or 0), str(err_msg), str(fix_desc), int(resolved), time.time())
    )
    conn.commit()
    conn.close()

def parse_stack_traces_and_debug():
    logs = [
        os.path.join(HOME, "dashboard.log"),
        os.path.join(HOME, "dealership_8099.log"),
        os.path.join(HOME, "webhook_8115.log"),
        os.path.join(HOME, "trust_8117.log"),
        os.path.join(HOME, "mesh_8119.log"),
        os.path.join(HOME, "cinema_8121.log"),
        os.path.join(HOME, "astra-unified-brain", "watchdog.log")
    ]
    traces_found = []
    frame_re = re.compile(r'File "([^"]+)", line (\d+)')
    for lf in logs:
        if not os.path.exists(lf):
            continue
        tail = open(lf, "r", encoding="utf-8", errors="ignore").read()[-4000:]
        if "Traceback" in tail or "Error:" in tail:
            frames = frame_re.findall(tail)
            err_lines = [l.strip() for l in tail.splitlines() if "Error:" in l or "Exception:" in l]
            last_err = err_lines[-1] if err_lines else "RuntimeException"
            if frames:
                fpath, lno_str = frames[-1]
                lno = int(lno_str)
                traces_found.append({"log": os.path.basename(lf), "file": fpath, "line": lno, "error": last_err})
                if fpath.startswith(HOME) and os.path.exists(fpath):
                    iterative_self_correct(fpath, hint_line=lno, hint_err=last_err)
    return traces_found

def iterative_self_correct(target_path, hint_line=0, hint_err="", max_iters=30):
    if not os.path.exists(target_path):
        return False
    for step in range(1, max_iters + 1):
        try:
            py_compile.compile(target_path, doraise=True)
            save_good_mirror(target_path)
            return True
        except py_compile.PyCompileError as exc:
            err_obj = exc.exc_value
            lineno = getattr(err_obj, "lineno", 0) or hint_line
            msg = str(err_obj)
            lines = open(target_path, "r", encoding="utf-8", errors="ignore").readlines()

            if lineno <= 0 or lineno > len(lines):
                return False

            bad_line = lines[lineno - 1]
            stripped = bad_line.lstrip()

            if "indent" in msg.lower():
                chosen_ind = "        "
                for back in range(lineno - 2, max(0, lineno - 40), -1):
                    prev = lines[back]
                    p_str = prev.lstrip()
                    if not p_str or p_str.startswith("#"):
                        continue
                    p_ind = prev[:len(prev) - len(p_str)]
                    cand = (p_ind + "    ") if prev.rstrip().endswith(":") else p_ind
                    if len(cand) % 4 == 0:
                        chosen_ind = cand
                        break

                cur_ind = bad_line[:len(bad_line) - len(stripped)]
                delta = len(chosen_ind) - len(cur_ind)
                if stripped.startswith(("if ", "elif ", "else:", "try:", "except", "def ")):
                    for fwd in range(lineno - 1, min(len(lines), lineno + 45)):
                        f_line = lines[fwd]
                        f_str = f_line.lstrip()
                        if not f_str:
                            continue
                        f_ind = f_line[:len(f_line) - len(f_str)]
                        if fwd > lineno - 1 and len(f_ind) <= len(cur_ind):
                            break
                        lines[fwd] = (" " * max(0, len(f_ind) + delta)) + f_str
                else:
                    lines[lineno - 1] = chosen_ind + stripped

                open(target_path, "w", encoding="utf-8").writelines(lines)
                record_fix(target_path, lineno, msg, f"Reverse-traced & re-aligned block at line {lineno} to {len(chosen_ind)} spaces", 1)
                continue

            record_fix(target_path, lineno, msg, f"Unhandled syntax error at line {lineno}", 0)
            return False
    return False

if __name__ == "__main__":
    traces = parse_stack_traces_and_debug()
    dash_ok = iterative_self_correct(DASH_FILE)
    if dash_ok:
        try:
            c = http.client.HTTPConnection("127.0.0.1", 8088, timeout=2)
            c.request("GET", "/")
            if c.getresponse().status != 200:
                raise RuntimeError("8088 down")
        except Exception:
            subprocess.run(["pkill", "-f", "dashboard_server.py"], stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            lf = open(os.path.join(HOME, "dashboard.log"), "w")
            subprocess.Popen(["python3", DASH_FILE], stdout=lf, stderr=lf, start_new_session=True)
            time.sleep(1.5)
            record_fix(DASH_FILE, 0, "Service offline", "Self-restarted dashboard_server.py on port 8088", 1)

    conn = get_db()
    conn.row_factory = sqlite3.Row
    fixes = [dict(r) for r in conn.execute("SELECT line_no, error_msg, applied_fix FROM error_memory ORDER BY timestamp DESC LIMIT 5").fetchall()]
    conn.close()
    print(json.dumps({"dashboard_compiled_and_live": dash_ok, "traces_scanned": len(traces), "applied_fixes": fixes}, indent=2))
