import ast, hashlib, http.client, json, os, py_compile, sqlite3, subprocess, time

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
    conn.execute("""CREATE TABLE IF NOT EXISTS codebase_index (
        symbol_id TEXT PRIMARY KEY,
        file_path TEXT,
        symbol_type TEXT,
        symbol_name TEXT,
        line_no INTEGER,
        last_indexed REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS route_registry (
        route_path TEXT PRIMARY KEY,
        method TEXT,
        target_port INTEGER,
        description TEXT,
        verified_ok INTEGER,
        last_checked REAL
    )""")
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

def index_codebase_ast():
    conn = sqlite3.connect(MEM_DB)
    now = time.time()
    indexed_files = 0
    indexed_symbols = 0
    for root, _, files in os.walk(HOME):
        if any(skip in root for skip in (".git", "astra-backups", "__pycache__", ".cache", "node_modules")):
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fpath = os.path.join(root, fn)
            rel_path = os.path.relpath(fpath, HOME)
            try:
                src = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                tree = ast.parse(src, filename=rel_path)
                indexed_files += 1
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        stype = "CLASS" if isinstance(node, ast.ClassDef) else "FUNC"
                        sid = hashlib.sha256(f"{rel_path}:{stype}:{node.name}:{node.lineno}".encode()).hexdigest()[:16]
                        conn.execute(
                            "INSERT OR REPLACE INTO codebase_index VALUES (?, ?, ?, ?, ?, ?)",
                            (sid, rel_path, stype, node.name, node.lineno, now)
                        )
                        indexed_symbols += 1
            except Exception:
                continue
    conn.commit()
    conn.close()
    return {"files_indexed": indexed_files, "symbols_indexed": indexed_symbols}

def iterative_self_correct(target_path, max_iters=25):
    if not os.path.exists(target_path):
        return False
    for step in range(1, max_iters + 1):
        try:
            py_compile.compile(target_path, doraise=True)
            return True
        except py_compile.PyCompileError as exc:
            err_obj = exc.exc_value
            lineno = getattr(err_obj, "lineno", 0) or 0
            msg = str(err_obj)
            lines = open(target_path, "r", encoding="utf-8", errors="ignore").readlines()

            if lineno <= 0 or lineno > len(lines):
                record_fix(target_path, lineno, msg, "Unrecoverable line index", 0)
                return False

            bad_line = lines[lineno - 1]
            stripped = bad_line.lstrip()

            if "indent" in msg.lower():
                # Find valid outer indentation from preceding non-empty code lines
                valid_indents = []
                for back in range(lineno - 2, max(0, lineno - 35), -1):
                    prev = lines[back]
                    p_str = prev.lstrip()
                    if not p_str or p_str.startswith("#"):
                        continue
                    p_ind = prev[:len(prev) - len(p_str)]
                    if prev.rstrip().endswith(":"):
                        valid_indents.append(p_ind + "    ")
                    valid_indents.append(p_ind)
                    if len(valid_indents) >= 4:
                        break

                chosen_ind = "        "
                for cand in valid_indents:
                    if len(cand) % 4 == 0:
                        chosen_ind = cand
                        break

                # If this is an 'if self.path' route block, align the entire block cleanly
                if stripped.startswith("if self.path"):
                    cur_ind = bad_line[:len(bad_line) - len(stripped)]
                    delta = len(chosen_ind) - len(cur_ind)
                    for fwd in range(lineno - 1, min(len(lines), lineno + 35)):
                        f_line = lines[fwd]
                        f_str = f_line.lstrip()
                        if not f_str:
                            continue
                        f_ind = f_line[:len(f_line) - len(f_str)]
                        if fwd > lineno - 1 and len(f_ind) <= len(cur_ind):
                            break
                        new_len = max(0, len(f_ind) + delta)
                        lines[fwd] = (" " * new_len) + f_str
                    fix_note = f"Iter {step}: Re-aligned route block at line {lineno} to {len(chosen_ind)} spaces"
                else:
                    lines[lineno - 1] = chosen_ind + stripped
                    fix_note = f"Iter {step}: Aligned line {lineno} to {len(chosen_ind)} spaces"

                open(target_path, "w", encoding="utf-8").writelines(lines)
                record_fix(target_path, lineno, msg, fix_note, 1)
                continue

            record_fix(target_path, lineno, msg, f"Iter {step}: Non-indentation syntax error", 0)
            return False
    return False

def run_self_correction_cycle():
    healed = iterative_self_correct(DASH_FILE)
    idx_stats = index_codebase_ast()
    if healed:
        try:
            c = http.client.HTTPConnection("127.0.0.1", 8088, timeout=2)
            c.request("GET", "/")
            if c.getresponse().status != 200:
                raise RuntimeError("Port 8088 unhealthy")
        except Exception:
            subprocess.run(["pkill", "-f", "dashboard_server.py"], stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            log_fh = open(os.path.join(HOME, "dashboard.log"), "a")
            subprocess.Popen(["python3", DASH_FILE], stdout=log_fh, stderr=log_fh, start_new_session=True)
            record_fix(DASH_FILE, 0, "Service offline", "Self-healed & restarted dashboard_server.py on port 8088", 1)
    return healed, idx_stats

if __name__ == "__main__":
    healed, stats = run_self_correction_cycle()
    time.sleep(1.5)
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    recent = [dict(r) for r in conn.execute("SELECT line_no, error_msg, applied_fix, resolved FROM error_memory ORDER BY timestamp DESC LIMIT 5").fetchall()]
    conn.close()
    print(json.dumps({
        "self_correction_passed": healed,
        "codebase_index": stats,
        "recent_healing_log": recent
    }, indent=2))
