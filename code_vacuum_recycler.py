import hashlib, json, os, py_compile, shutil, sqlite3, time

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_ai_memory.db")
VAULT_DIR = os.path.join(HOME, "astra-golden-vault")
os.makedirs(VAULT_DIR, exist_ok=True)

SKIP_DIRS = (".git", "astra-backups", "astra-golden-vault", ".astra_snapshots", ".astra_atomic_checkpoints", "__pycache__", ".cache", "node_modules")

def vacuum_and_recycle_codebase():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS golden_code_vault (
        rel_path TEXT PRIMARY KEY,
        sha256_hash TEXT,
        status TEXT,
        timestamp REAL
    )""")

    vacuumed_ok = []
    recycled_fixed = []
    still_broken = []
    now = time.time()

    for root, _, files in os.walk(HOME):
        if any(s in root for s in SKIP_DIRS):
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fpath = os.path.join(root, fn)
            rel = os.path.relpath(fpath, HOME)

            # 1. Test if module already compiles cleanly
            try:
                py_compile.compile(fpath, doraise=True)
                raw = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                dst = os.path.join(VAULT_DIR, rel.replace(os.sep, "__"))
                if os.path.exists(dst): os.chmod(dst, 0o644); os.remove(dst)
                shutil.copyfile(fpath, dst)
                conn.execute("INSERT OR REPLACE INTO golden_code_vault VALUES (?, ?, ?, ?)", (rel, digest, "VACUUMED_VALID", now))
                vacuumed_ok.append(rel)
                continue
            except py_compile.PyCompileError:
                pass

            # 2. Recycle broken module: first try restoring from code_mirrors, then iterative indent repair
            restored = False
            try:
                row = conn.execute("SELECT known_good_code FROM code_mirrors WHERE file_path = ?", (fpath,)).fetchone()
                if row and isinstance(row, (tuple, list)):
                    good_src = next(iter(row), "")
                    if good_src:
                        open(fpath, "w", encoding="utf-8").write(good_src)
                        py_compile.compile(fpath, doraise=True)
                        restored = True
            except Exception:
                restored = False

            if not restored:
                for _ in range(15):
                    try:
                        py_compile.compile(fpath, doraise=True)
                        restored = True
                        break
                    except py_compile.PyCompileError as exc:
                        err = exc.exc_value
                        lno = getattr(err, "lineno", 0) or 0
                        msg = str(err).lower()
                        lines = open(fpath, "r", encoding="utf-8", errors="ignore").readlines()
                        if 1 <= lno <= len(lines) and "indent" in msg:
                            stripped = lines[lno - 1].lstrip()
                            target_ind = "" if lno <= 5 else "        "
                            for back in range(lno - 2, max(0, lno - 25), -1):
                                prev = lines[back]
                                ps = prev.lstrip()
                                if ps and not ps.startswith("#"):
                                    pi = prev[:len(prev) - len(ps)]
                                    target_ind = (pi + "    ") if prev.rstrip().endswith(":") else pi
                                    break
                            lines[lno - 1] = target_ind + stripped
                            open(fpath, "w", encoding="utf-8").writelines(lines)
                        else:
                            break

            if restored:
                raw = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                shutil.copy2(fpath, os.path.join(VAULT_DIR, rel.replace(os.sep, "__")))
                conn.execute("INSERT OR REPLACE INTO golden_code_vault VALUES (?, ?, ?, ?)", (rel, digest, "RECYCLED_AND_VALID", now))
                recycled_fixed.append(rel)
            else:
                still_broken.append(rel)

    conn.commit()
    conn.close()
    return {
        "status": "CODE_VACUUM_AND_RECYCLE_COMPLETE",
        "working_modules_vacuumed": len(vacuumed_ok),
        "broken_modules_recycled": recycled_fixed,
        "unresolved_modules": still_broken
    }

if __name__ == "__main__":
    print(json.dumps(vacuum_and_recycle_codebase(), indent=2))
