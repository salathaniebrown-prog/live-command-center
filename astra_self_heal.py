#!/usr/bin/env python3
import ast, json, os, py_compile, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path.home() / "live-command-center"
BACKUP_DIR = REPO / "builds" / "self_heal_backups"
TELEMETRY_LOG = REPO / "builds" / "self_heal_telemetry.jsonl"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

SYS_PATH_HEADER = "import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"

def log_event(event: dict):
    event["ts"] = time.time()
    with open(TELEMETRY_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event), flush=True)

def verify_python_file(target: Path) -> tuple[bool, str]:
    try:
        src = target.read_text(encoding="utf-8")
        ast.parse(src)
        py_compile.compile(str(target), doraise=True)
        return True, "ast_parse + py_compile passed"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def atomic_patch(target: Path, new_src: str, reason: str) -> bool:
    stamp = int(time.time())
    backup = BACKUP_DIR / f"{target.name}.{stamp}.bak"
    shutil.copy2(target, backup)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(new_src, encoding="utf-8")
    ok, msg = verify_python_file(tmp)
    if not ok:
        tmp.unlink(missing_ok=True)
        log_event({"action": "PATCH_REJECTED", "file": str(target), "reason": reason, "error": msg})
        return False
    os.replace(tmp, target)
    log_event({"action": "PATCH_PROMOTED", "file": str(target), "reason": reason, "backup": str(backup)})
    return True

def scan_and_repair():
    # 1. Enforce sys.path root resolution across all nodes/*.py
    for node_py in (REPO / "nodes").glob("*.py"):
        src = node_py.read_text(encoding="utf-8")
        if "parents[1]" not in src:
            atomic_patch(node_py, SYS_PATH_HEADER + src, "inject_repo_sys_path")

    # 2. Verify syntax integrity across all repo Python files & rollback from latest backup if corrupted
    for py_file in REPO.rglob("*.py"):
        if "builds" in py_file.parts or ".git" in py_file.parts:
            continue
        ok, err = verify_python_file(py_file)
        if not ok:
            backups = sorted(BACKUP_DIR.glob(f"{py_file.name}.*.bak"), reverse=True)
            if backups:
                shutil.copy2(backups[0], py_file)
                log_event({"action": "AUTO_ROLLBACK", "file": str(py_file), "error": err, "restored": str(backups[0])})
            else:
                log_event({"action": "SYNTAX_ALERT_NO_BACKUP", "file": str(py_file), "error": err})

    # 3. Check PM2 stopped processes and attempt verified recovery
    raw = subprocess.check_output(["pm2", "jlist"], text=True)
    for proc in json.loads(raw):
        name = proc.get("name")
        status = proc.get("pm2_env", {}).get("status")
        if status != "online":
            subprocess.run(["pm2", "restart", name], check=False)
            log_event({"action": "PM2_AUTO_RECOVER", "service": name, "prev_status": status})

if __name__ == "__main__":
    while True:
        try:
            scan_and_repair()
        except Exception as exc:
            log_event({"action": "LOOP_ERROR", "error": str(exc)})
        time.sleep(15)
