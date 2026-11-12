import os, json, time, sqlite3, hashlib, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-auto-router")
DB = f"{BASE}/auto_router.db"

def init():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY, goal TEXT, model TEXT, agent TEXT, compute TEXT, result TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS clusters(tier TEXT PRIMARY KEY, endpoint TEXT)")
    c.commit(); c.close()

def get_cluster(tier):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT endpoint FROM clusters WHERE tier=?", (tier,)).fetchone()
    c.close()
    return r if (r and r) else ""

def get_hw():
    H = ".".join(["127","0","0","1"])
    try: return json.loads(urllib.request.urlopen(f"http://{H}:8102/api/wf/metrics", timeout=2).read().decode())
    except Exception: return {"ram_pct": 45.0, "cpu_load_1m": "0.50"}

def auto_select_and_run(goal):
    hw = get_hw()
    ram = float(hw.get("ram_pct", 45.0))
    g = goal.lower()
    if any(k in g for k in ["177b", "train", "heavy", "simulation", "supercomputer"]):
        tier, compute, model = "SUPERCOMPUTER", "8-GPU SUPERCOMPUTER CLUSTER", "177B-MoE + DeepSeek-V3"
    elif any(k in g for k in ["code", "app", "reverse", "electron", "build", "pc"]):
        tier, compute, model = "PC", "LOCAL PC / WORKSTATION NODE", "Claude-Code-Clone + Codex"
    else:
        tier, compute, model = "EDGE", ("ANDROID EDGE (LOW-RAM)" if ram > 80 else "ANDROID EDGE + NPU"), "Gemma-4-Local + LiteRT-LM"

    ext_url = get_cluster(tier)
    if any(k in g for k in ["car", "wyler", "buy", "vehicle", "fleet", "evening"]):
        agent, target_port, target_path, payload = "WYLER_DEALERSHIP_AGENT", 8099, "/api/state", None
    elif any(k in g for k in ["law", "contract", "llc", "protect", "legal"]):
        agent, target_port, target_path, payload = "ALSTRA_LEGAL_COUNSEL", 8095, "/api/legal/audit", {"query": goal}
    elif any(k in g for k in ["greensboro", "route", "triad", "location", "weather"]):
        agent, target_port, target_path, payload = "TRIAD_GEO_OPTIMIZER", 8103, "/api/geo/route", {}
    else:
        agent, target_port, target_path, payload = "FABLE_52_REASONER", 8101, "/api/os/reason", {"goal": goal}

    H = ".".join(["127","0","0","1"])
    live_out = ""
    try:
        if ext_url:
            rq = urllib.request.Request(ext_url, data=json.dumps({"goal": goal, "model": model}).encode(), headers={"Content-Type":"application/json"})
            live_out = f"[EXTERNAL {tier} -> {ext_url}] " + urllib.request.urlopen(rq, timeout=5).read().decode("utf-8", "ignore")[:220]
        else:
            rq = urllib.request.Request(f"http://{H}:{target_port}{target_path}", data=json.dumps(payload).encode() if payload is not None else None, headers={"Content-Type":"application/json"})
            live_out = urllib.request.urlopen(rq, timeout=5).read().decode("utf-8", "ignore")[:240]
    except Exception as e:
        live_out = f"Routed to {agent} ({e})"

    gid = "AST-" + hashlib.sha256(f"{goal}{time.time()}".encode()).hexdigest()[:6].upper()
    summary = f"[{gid}] COMPUTE: {compute} ({ext_url or 'LOCAL_MESH'}) | MODEL: {model} | AGENT: {agent}\nLIVE RESULT: {live_out}"
    c = sqlite3.connect(DB); c.execute("INSERT INTO goals VALUES(?,?,?,?,?,?,?)", (gid, goal, model, agent, compute, summary, time.time())); c.commit(); c.close()
    return {"id": gid, "compute": compute, "model": model, "agent": agent, "summary": summary}

class H(BaseHTTPRequestHandler):
    def _j(self, d):
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        cls = {r["tier"]: r["endpoint"] for r in c.execute("SELECT * FROM clusters")}
        c.close(); self._j({"status": "ONLINE", "port": 8109, "clusters": cls})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
        if self.path == "/api/auto/set-cluster":
            c = sqlite3.connect(DB); c.execute("INSERT OR REPLACE INTO clusters VALUES(?,?)", (d.get("tier","PC").upper(), d.get("endpoint","").strip())); c.commit(); c.close()
            self._j({"status": "CLUSTER_ENDPOINT_SAVED", "tier": d.get("tier","PC").upper()})
        else:
            self._j(auto_select_and_run(d.get("goal", "Execute evening vehicle purchase & Triad route check")))

init()
HTTPServer(("0.0.0.0", 8109), H).serve_forever()
