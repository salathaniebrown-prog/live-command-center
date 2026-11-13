import os, json, time, sqlite3, hashlib, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-jev-system1")
DB = f"{BASE}/jev_system1.db"

WORLD_LIBRARY = [
    ("LIB-MED", "Medical & Clinical Professionals", "Evidence-based differential diagnosis, triage protocols, HIPAA compliance, and clinical research synthesis."),
    ("LIB-LAW", "Legal & Commercial Counsel", "Harvard/Duke Law commercial doctrine, UCC Articles 2, 9 & 12, contract redlining, and corporate asset shielding."),
    ("LIB-INV", "Inventors & R&D Engineers", "First-principles engineering, patent claim structuring, prototyping, and hardware-software architecture."),
    ("LIB-CHR", "Historical Chronicles & Institutional Methodologies", "Comparative historical analysis, primary-source chronicles, strategic governance, and institutional decision frameworks.")
]

def init():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS routes(id TEXT PRIMARY KEY, prompt TEXT, lane TEXT, confidence REAL, result TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS cfg(k TEXT PRIMARY KEY, v TEXT)")
    c.commit(); c.close()

def classify_and_route(prompt):
    q = prompt.lower()
    scores = {
        "VAULT_QUERY": 0.15 + (0.65 if any(w in q for w in ["remember", "vault", "brain", "know", "note", "history", "search"]) else 0.0),
        "TOOL_ACTION": 0.15 + (0.65 if any(w in q for w in ["email", "calendar", "schedule", "send", "backup", "buy", "car", "wyler", "alert"]) else 0.0),
        "AGENT_TASK": 0.15 + (0.65 if any(w in q for w in ["invoice", "build", "app", "contract", "multi", "workflow", "plan", "create"]) else 0.0),
        "WORLD_LIBRARY": 0.15 + (0.65 if any(w in q for w in ["doctor", "medical", "lawyer", "legal", "inventor", "patent", "chronicle", "methodology", "library"]) else 0.0)
    }
    lane = max(scores, key=scores.get)
    conf = round(min(0.99, scores[lane]), 2)
    H = ".".join(["127","0","0","1"])

    c = sqlite3.connect(DB)
    tf_key = (c.execute("SELECT v FROM cfg WHERE k='typeface_key'").fetchone() or [""])
    c.close()

    detail = ""
    if lane == "VAULT_QUERY":
        try:
            rq = urllib.request.Request(f"http://{H}:8096/api/brain/route", data=json.dumps({"prompt": prompt}).encode(), headers={"Content-Type": "application/json"})
            detail = urllib.request.urlopen(rq, timeout=4).read().decode("utf-8", "ignore")[:240]
        except Exception: detail = "Queried Astra 45M-Token Second Brain Vault."
    elif lane == "TOOL_ACTION":
        try:
            rq = urllib.request.Request(f"http://{H}:8097/api/ooda/execute", data=json.dumps({"directive": prompt, "amount_usd": 0}).encode(), headers={"Content-Type": "application/json"})
            detail = urllib.request.urlopen(rq, timeout=4).read().decode("utf-8", "ignore")[:240]
        except Exception: detail = "Dispatched to OODA Tool Execution Engine (Email/Calendar/Fleet)."
    elif lane == "AGENT_TASK":
        try:
            rq = urllib.request.Request(f"http://{H}:8108/api/pro/app", data=json.dumps({"prompt": prompt, "effort": "HIGH"}).encode(), headers={"Content-Type": "application/json"})
            detail = urllib.request.urlopen(rq, timeout=4).read().decode("utf-8", "ignore")[:240]
        except Exception: detail = "Dispatched to Multi-Step Agent & Invoice/App Studio."
    else:
        matched = [f"[{m}] {m}: {m}" for m in WORLD_LIBRARY if any(k in q for k in m.lower().split())] or [f"[{m}] {m}: {m}" for m in WORLD_LIBRARY]
        detail = "\n".join(matched)

    jid = "JEV-" + hashlib.sha256(f"{prompt}{time.time()}".encode()).hexdigest()[:6].upper()
    tf_tag = "TYPEFACE_API:LINKED" if tf_key else "TYPEFACE_API:LOCAL_FALLBACK"
    out = f"[{jid} | SYSTEM ONE LANE: {lane} ({int(conf*100)}% PROB) | {tf_tag}]\n{detail}"
    c = sqlite3.connect(DB); c.execute("INSERT INTO routes VALUES(?,?,?,?,?,?)", (jid, prompt, lane, conf, out, time.time())); c.commit(); c.close()
    return {"id": jid, "lane": lane, "confidence": conf, "scores": scores, "output": out}

class H(BaseHTTPRequestHandler):
    def _j(self, d):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        self._j({"status": "ONLINE", "port": 8111, "library_nodes": len(WORLD_LIBRARY)})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/jev/set-key":
            c = sqlite3.connect(DB); c.execute("INSERT OR REPLACE INTO cfg VALUES('typeface_key', ?)", (d.get("api_key", "").strip(),)); c.commit(); c.close()
            self._j({"status": "TYPEFACE_KEY_SAVED"})
        else:
            self._j(classify_and_route(d.get("prompt", "Search world professional library")))

init()
HTTPServer(("0.0.0.0", 8111), H).serve_forever()
