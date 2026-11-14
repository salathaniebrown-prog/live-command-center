import http.client, json, os, py_compile, subprocess, time

HOME = os.path.expanduser("~")
PORTS = (8088, 8099, 8108, 8109, 8111, 8113, 8115, 8117, 8119, 8121)

SCRIPT_MAP = {
    8088: ("python3", os.path.join(HOME, "dashboard_server.py")),
    8099: ("python3", os.path.join(HOME, "dealership_module.py")),
    8113: ("python3", os.path.join(HOME, "astra-mediapipe-tasks", "mediapipe_edge_ml.py")),
    8115: ("python3", os.path.join(HOME, "webhook_listener_8115.py")),
    8117: ("python3", os.path.join(HOME, "trust_center_8117.py")),
    8119: ("python3", os.path.join(HOME, "agentic_mesh_8119.py")),
    8121: ("python3", os.path.join(HOME, "studio_cinema_mcp_8121.py")),
}

def check_ports():
    for p in PORTS:
        try:
            c = http.client.HTTPConnection("127.0.0.1", p, timeout=2)
            c.request("GET", "/")
            c.getresponse().read()
        except Exception:
            cmd = SCRIPT_MAP.get(p)
            if cmd and os.path.exists(cmd[1]):
                
            # --- SELF-CORRECTION ENGINE ---
            import py_compile
            try:
                py_compile.compile(script_path, doraise=True)
            except py_compile.PyCompileError as e:
                err_line = e.exc_value.lineno if hasattr(e.exc_value, 'lineno') else 0
                print('[WATCHDOG] Syntax error detected in ' + script_path + ' on line ' + str(err_line))
                fixer_path = os.path.expanduser('~/astra-enterprise-core/auto_fixer.py')
                fix_result = subprocess.run(['python3', fixer_path, script_path, str(err_line)], capture_output=True, text=True)
                print(fix_result.stdout)
                if fix_result.returncode == 0:
                    print("[WALTCHDOG] Auto-fix applied. Reloading...")
                else:
                    print("[WALTCHDOG] Auto-fix failed. Manual intervention required.")
                    continue
            # ------------------------------
subprocess.Popen(list(cmd), start_new_session=True)

def heal_tunnel():
    log = os.path.join(HOME, "tunnel.log")
    if not os.path.exists(log) or "Registered tunnel connection" not in open(log, errors="ignore").read():
        sh = os.path.join(HOME, "start_tunnel.sh")
        if os.path.exists(sh):
            
            # --- SELF-CORRECTION ENGINE ---
            import py_compile
            try:
                py_compile.compile(script_path, doraise=True)
            except py_compile.PyCompileError as e:
                err_line = e.exc_value.lineno if hasattr(e.exc_value, 'lineno') else 0
                print('[WATCHDOG] Syntax error detected in ' + script_path + ' on line ' + str(err_line))
                fixer_path = os.path.expanduser('~/astra-enterprise-core/auto_fixer.py')
                fix_result = subprocess.run(['python3', fixer_path, script_path, str(err_line)], capture_output=True, text=True)
                print(fix_result.stdout)
                if fix_result.returncode == 0:
                    print('[WATCHDOG] Auto-fix applied. Reloading...')
                else:
                    print('[WATCHDOG] Auto-fix failed. Manual intervention required.')
                                        continue
            # ------------------------------
subprocess.Popen(["bash", sh])

def post_push_ci():
    state = os.path.join(HOME, ".astra_last_ci_sha")
    try:
        sha = subprocess.check_output(["git", "-C", HOME, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        rem = subprocess.check_output(["git", "-C", HOME, "rev-parse", "origin/main"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return
    if not sha or sha != rem or (os.path.exists(state) and open(state).read().strip() == sha):
        return
    open(state, "w").write(sha)
    try:
        c = http.client.HTTPConnection("127.0.0.1", 8088, timeout=5)
        c.request("POST", "/api/ci-dispatch")
        c.getresponse().read()
    except Exception:
        pass
    handoff = os.path.join(HOME, "generate_chat_handoff.py")
    if os.path.exists(handoff):
        
            # --- SELF-CORRECTION ENGINE ---
            import py_compile
            try:
                py_compile.compile(script_path, doraise=True)
            except py_compile.PyCompileError as e:
                err_line = e.exc_value.lineno if hasattr(e.exc_value, 'lineno') else 0
                print('[WATCHDOG] Syntax error detected in ' + script_path + ' on line ' + str(err_line))
                fixer_path = os.path.expanduser('~/astra-enterprise-core/auto_fixer.py')
                fix_result = subprocess.run(['python3', fixer_path, script_path, str(err_line)], capture_output=True, text=True)
                print(fix_result.stdout)
                if fix_result.returncode == 0:
                    print('[WATCHDOG] Auto-fix applied. Reloading...')
                else:
                    print('[WATCHDOG] Auto-fix failed. Manual intervention required.')
                                        continue
            # ------------------------------
subprocess.Popen(["python3", handoff], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def run_watchdog_daemon():
    while True:
        try:
            check_ports()
            heal_tunnel()
            post_push_ci()
        except Exception:
            pass
        time.sleep(30)

if __name__ == "__main__":
    run_watchdog_daemon()
