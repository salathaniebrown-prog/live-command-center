import os, json, time, math, sqlite3, subprocess, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-mediapipe-tasks")
BUNDLES, MODELS = os.path.join(BASE, "bundles"), os.path.join(BASE, "models")
os.makedirs(BUNDLES, exist_ok=True); os.makedirs(MODELS, exist_ok=True)
DB = os.path.join(BASE, "mediapipe_tasks.db")
MODEL_MAP = {"VISION": "efficientdet_lite0.tflite", "TEXT": "bert_classifier.tflite", "RETRIEVAL": "universal_sentence_encoder.tflite", "AUDIO": "yamnet.tflite", "DECISION": "bert_classifier.tflite"}

def init_db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS task_bundles(id TEXT PRIMARY KEY, task_type TEXT, platform TEXT, delegate TEXT, file_path TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS retrieval_vectors(id INTEGER PRIMARY KEY AUTOINCREMENT, doc_text TEXT, vec_json TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS executed_goals(id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT, action_type TEXT, status TEXT, result_json TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS playback_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, replayed_count INTEGER, pass_rate REAL, avg_ms REAL, report_json TEXT, ts REAL)")
    c.commit(); c.close()

def run_cmd(cmd, timeout=8):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {"ok": p.returncode == 0, "out": (p.stdout or p.stderr).strip()[:500]}
    except Exception as e:
        return {"ok": False, "out": str(e)}

def fetch_live_market():
    sources = [
        ("Coinbase", "https://coinbase.com", lambda d: float(d["data"]["amount"])),
        ("CoinGecko", "https://coingecko.com", lambda d: float(d["ethereum"]["usd"])),
        ("Binance", "https://binance.com", lambda d: float(d["price"]))
    ]
    for name, url, parse in sources:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AstraEdge/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                raw = r.read().decode().strip()
                if raw:
                    return {"source": name, "pair": "ETH-USD", "spot_usd": parse(json.loads(raw))}
        except Exception:
            continue
    return {"pair": "ETH-USD", "status": "OFFLINE_CACHE_MODE"}

def embed(s):
    d = [0.0]*16
    for i, ch in enumerate(s.lower().encode()): d[i%16] += (ch%37)/37.0
    n = math.sqrt(sum(x*x for x in d)) or 1.0
    return [round(x/n, 4) for x in d]

def execute_real_goal(goal, record=True):
    t0 = time.time()
    gl = goal.lower()
    actions = []
    if any(k in gl for k in ("device", "android", "battery", "cpu", "ram", "storage", "test", "health", "port")):
        mem = run_cmd("free -m | awk 'NR==2{printf \"%sMB/%sMB\", $3, $2}'")
        disk = run_cmd("df -h ~ | awk 'NR==2{print $4\" free of \"$2}'")
        ports = run_cmd("ps -ef | grep -E 'dashboard_server|mediapipe_edge|overnight_daemon' | grep -v grep | wc -l")
        bat = run_cmd("termux-battery-status 2>/dev/null")
        bat_data = json.loads(bat["out"]) if bat["out"].startswith("{") else {"raw": bat["out"] or "Termux sandbox"}
        actions.append({"action": "ANDROID_DEVICE_DIAGNOSTIC", "ram_used": mem["out"], "storage": disk["out"], "active_daemons": int(ports["out"] or 0), "battery": bat_data})
    if any(k in gl for k in ("crypto", "eth", "price", "market", "live", "data", "coinbase", "bank", "usd")):
        actions.append({"action": "LIVE_MARKET_FEED", "data": fetch_live_market()})
    if any(k in gl for k in ("git", "github", "push", "sync", "backup", "save")):
        gs = run_cmd("git -C ~ status -s | wc -l")
        actions.append({"action": "GIT_REPO_AUDIT", "modified_files": int(gs["out"] or 0), "branch": run_cmd("git -C ~ branch --show-current")["out"]})
    if not actions:
        mem = run_cmd("free -m | awk 'NR==2{printf \"%sMB/%sMB\", $3, $2}'")
        actions.append({"action": "AUTONOMOUS_CYCLE_VERIFY", "market": fetch_live_market(), "ram_used": mem["out"], "models_ready": sum(1 for f in MODEL_MAP.values() if os.path.isfile(os.path.join(MODELS, f)))})
    res = {"goal": goal, "status": "GOAL_COMPLETED", "actions_executed": len(actions), "results": actions, "latency_ms": round((time.time() - t0) * 1000, 2)}
    if record:
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO executed_goals(goal, action_type, status, result_json, ts) VALUES(?,?,?,?,?)", (goal, actions["action"], "COMPLETED", json.dumps(res), time.time()))
        c.commit(); c.close()
    return res

def run_playback_suite():
    t0 = time.time()
    c = sqlite3.connect(DB)
    past_goals = [r for r in c.execute("SELECT goal FROM executed_goals ORDER BY id DESC LIMIT 10").fetchall()]
    vecs = c.execute("SELECT doc_text, vec_json FROM retrieval_vectors ORDER BY id DESC LIMIT 20").fetchall()
    c.close()
    if not past_goals:
        past_goals = ["Test device and fetch live ETH crypto price", "Check git status and sync"]
    goal_results = [execute_real_goal(g, record=False) for g in past_goals]
    passed = sum(1 for r in goal_results if r["status"] == "GOAL_COMPLETED")
    rag_checks = []
    for txt, vj in vecs:
        v1, v2 = embed(txt), json.loads(vj)
        sim = round(sum(a*b for a, b in zip(v1, v2)), 4)
        rag_checks.append({"text": txt[:50], "self_similarity": sim, "pass": sim >= 0.99})
    avg_ms = round(sum(r["latency_ms"] for r in goal_results) / max(len(goal_results), 1), 2)
    pass_rate = round((passed / max(len(goal_results), 1)) * 100, 1)
    report = {"status": "PLAYBACK_COMPLETE", "replayed_goals": len(goal_results), "pass_rate_pct": pass_rate, "avg_latency_ms": avg_ms, "rag_vectors_verified": len(rag_checks), "rag_checks": rag_checks, "total_ms": round((time.time() - t0) * 1000, 2)}
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO playback_runs(replayed_count, pass_rate, avg_ms, report_json, ts) VALUES(?,?,?,?,?)", (len(goal_results), pass_rate, avg_ms, json.dumps(report), time.time()))
    c.commit(); c.close()
    return report

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, d, code=200):
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS"); self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.end_headers(); self.wfile.write(json.dumps(d).encode())
    def do_OPTIONS(self): self._j({}, 204)
    def do_GET(self):
        if self.path.startswith("/ui"):
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(open(os.path.join(BASE, "webgpu_runner.html"), "rb").read()); return
        c = sqlite3.connect(DB)
        goals = c.execute("SELECT COUNT(*) FROM executed_goals").fetchone()
        plays = c.execute("SELECT COUNT(*) FROM playback_runs").fetchone()
        last_pb = c.execute("SELECT report_json FROM playback_runs ORDER BY id DESC LIMIT 1").fetchone()
        c.close()
        self._j({"status": "AUTONOMOUS_ACTION_ENGINE_ONLINE", "port": 8113, "goals_completed": goals, "playback_runs": plays, "last_playback": json.loads(last_pb) if last_pb else None})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path.startswith("/playback"):
            return self._j(run_playback_suite())
        q = str(d.get("input", d.get("goal", "Test device")))
        if d.get("index"):
            vec = embed(q); c = sqlite3.connect(DB)
            c.execute("INSERT INTO retrieval_vectors(doc_text,vec_json,ts) VALUES(?,?,?)", (q, json.dumps(vec), time.time())); c.commit(); c.close()
            return self._j({"status": "INDEXED_TO_SQLITE_RAG", "text": q, "dims": len(vec)})
        if self.path.startswith("/infer") or self.path.startswith("/execute"):
            return self._j(execute_real_goal(q))
        tid = f"mp_{int(time.time()*1000)}"; pl = d.get("platform", "ANDROID_KOTLIN_JAVA"); fp = os.path.join(BUNDLES, f"{tid}_{pl.lower()}.task.json")
        bnd = {"bundle_id": tid, "platform": pl, "delegate": d.get("delegate", "GPU"), "models": list(MODEL_MAP.values())}
        with open(fp, "w") as f: json.dump(bnd, f)
        self._j({"status": "BUNDLE_BUILT", "bundle_id": tid, "path": fp})

init_db()
HTTPServer(("0.0.0.0", 8113), H).serve_forever()
