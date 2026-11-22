#!/usr/bin/env python3
import ast, http.server, json, py_compile, shutil, socketserver, subprocess, time
from pathlib import Path

REPO = Path.home() / "live-command-center"
BAK = REPO / "builds" / "self_heal_backups"
BAK.mkdir(parents=True, exist_ok=True)

def verify_and_heal():
    repaired, clean = [], 0
    for f in REPO.rglob("*.py"):
        if "builds" in f.parts or ".git" in f.parts: continue
        try:
            ast.parse(f.read_text(encoding="utf-8"))
            py_compile.compile(str(f), doraise=True)
            shutil.copy2(f, BAK / f"{f.name}.last_good.bak")
            clean += 1
        except Exception:
            b = BAK / f"{f.name}.last_good.bak"
            if b.exists():
                shutil.copy2(b, f)
                repaired.append(f.name)
    return {"clean_files": clean, "auto_repaired": repaired, "ts": time.time()}

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        res = verify_and_heal()
        try:
            procs = json.loads(subprocess.check_output(["pm2", "jlist"], text=True, timeout=2))
            res["services"] = {p["name"]: p["pm2_env"]["status"] for p in procs}
        except Exception as e:
            res["services_err"] = str(e)
        data = json.dumps(res, indent=2).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass

if __name__ == "__main__":
    verify_and_heal()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", 8096), H) as s: s.serve_forever()
