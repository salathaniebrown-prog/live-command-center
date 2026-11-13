import sys; sys.path.insert(0, os.path.expanduser('~/astra-jev-system1'))
import jev_feeds
import os, re, json, time, socket, sqlite3, hashlib, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-jev-system1")
DB = f"{BASE}/jev_system1.db"
H = ".".join(["127","0","0","1"])

UPSTREAM_ENDPOINTS = {
    "VAULT_QUERY": (8096, "/api/brain/route"),
    "TOOL_ACTION": (8097, "/api/ooda/execute"),
    "AGENT_TASK": (8108, "/api/pro/app"),
    "DEALERSHIP": (8099, "/api/state"),
    "GEO_INTEL": (8103, "/api/geo/route"),
    "OSINT_FEED": (8104, "/api/osint/harvest"),
    "AUTO_COMPUTE": (8109, "/api/auto/run")
}

TEMPLATES = {
    "medical": "# CLINICAL & MEDICAL PROTOCOL TEMPLATE\n- Patient Triage & Differential Matrix\n- Evidence-Based Intervention & Contraindication Audit\n- HIPAA & Encrypted At-Rest Record Compliance\n",
    "legal": "# COMMERCIAL & CRYPTO ASSET SHIELD AGREEMENT\n- Governing Law: State of North Carolina & UCC Articles 2, 9 & 12\n- Atomic Escrow Release upon Cryptographic Proof & Clean Title\n- IP Carve-Out: Contractor retains 100% ownership of pre-existing AI/Astra tools\n",
    "patent": "# PROVISIONAL PATENT & INVENTION DISCLOSURE\n- Title: Multi-Agent Reflex Decision Layer & Tiered Persistent Memory OS\n- Technical Field & Claims: Deterministic intent classification, zero-trust state routing, and self-installing knowledge ingestion\n"
}

def init(); jev_feeds.init_feeds(); jev_feeds.start_feed_daemon():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS session_state(id INT PRIMARY KEY, last_lane TEXT, last_goal TEXT, next_best TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS learned_rules(rule_id TEXT PRIMARY KEY, keyword TEXT, target_lane TEXT, source_file TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS cfg(k TEXT PRIMARY KEY, v TEXT)")
    c.commit(); c.close()

def check_endpoint(port):
    try:
        with socket.create_connection((H, port), 0.5): return True
    except Exception: return False

def self_install_from_file(file_path):
    fp = os.path.expanduser(file_path.strip())
    if not os.path.exists(fp): return {"error": f"File not found: {fp}"}
    raw = open(fp, "rb").read(200000)
    # Extract readable ASCII/UTF-8 text from PDF streams or plain text/MD/JSON files
    txt = " ".join(re.findall(r"[A-Za-z0-9_.,:/-]{4,}", raw.decode("utf-8", "ignore")))[:12000]
    words = [w.lower() for w in re.findall(r"[a-zA-Z]{5,}", txt)]
    top_kw = list(dict.fromkeys(words))[:8]
    c = sqlite3.connect(DB)
    for kw in top_kw:
        lane = "TOOL_ACTION" if kw in ("email","calendar","buy","fleet","send","backup") else ("WORLD_LIBRARY" if kw in ("medical","doctor","legal","lawyer","patent","chronicle") else "VAULT_QUERY")
        rid = "RUL-" + hashlib.sha256(f"{kw}{fp}".encode()).hexdigest()[:5].upper()
        c.execute("INSERT OR REPLACE INTO learned_rules VALUES(?,?,?,?,?)", (rid, kw, lane, os.path.basename(fp), time.time()))
    c.commit(); c.close()
    try:
        rq = urllib.request.Request(f"http://{H}:8096/api/brain/remember", data=json.dumps({"domain":"JEV_SELF_INSTALL","title":f"Guide: {os.path.basename(fp)}","content":txt[:900]}).encode(), headers={"Content-Type":"application/json"})
        urllib.request.urlopen(rq, timeout=2)
    except Exception: pass
    return {"status": "SELF_INSTALLED", "file": os.path.basename(fp), "installed_keywords": top_kw, "chars_indexed": len(txt)}

def reflex_decide(prompt):
    q = prompt.lower()
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    prev = c.execute("SELECT * FROM session_state WHERE id=1").fetchone()
    learned = {r["keyword"]: r["target_lane"] for r in c.execute("SELECT keyword, target_lane FROM learned_rules")}

    lane = "VAULT_QUERY"
    for kw, t_lane in learned.items():
        if kw in q: lane = t_lane; break
    if any(w in q for w in ["car", "wyler", "buy", "vehicle", "evening"]): lane = "DEALERSHIP"
    elif any(w in q for w in ["greensboro", "route", "triad", "weather", "location"]): lane = "GEO_INTEL"
    elif any(w in q for w in ["news", "feed", "search", "osint", "tor", "web"]): lane = "OSINT_FEED"
    elif any(w in q for w in ["email", "calendar", "schedule", "backup", "alert"]): lane = "TOOL_ACTION"
    elif any(w in q for w in ["invoice", "build", "app", "contract", "create"]): lane = "AGENT_TASK"
    elif any(w in q for w in ["doctor", "medical", "lawyer", "patent", "chronicle", "library"]): lane = "WORLD_LIBRARY"

    port, ep = UPSTREAM_ENDPOINTS.get(lane, (8096, "/api/brain/route"))
    solid = check_endpoint(port)
    next_best = "Verify Crypto Escrow & Print Bill of Sale" if lane == "DEALERSHIP" else ("Run Triad Route Manifest & Weather Check" if lane == "GEO_INTEL" else "Commit Output to 45M Vault & Trigger Hot Backup")
    prev_note = f"Continuing from [{prev['last_lane']}: {prev['last_goal'][:32]}]" if prev else "Fresh Reflex Session"

    live_data = ""
    if solid:
        try:
            body = json.dumps({"prompt": prompt, "directive": prompt, "query": prompt, "goal": prompt}).encode() if ep != "/api/state" else None
            rq = urllib.request.Request(f"http://{H}:{port}{ep}", data=body, headers={"Content-Type":"application/json"})
            live_data = urllib.request.urlopen(rq, timeout=5).read().decode("utf-8", "ignore")[:260]
        except Exception as e:
            live_data = f"Upstream handled ({e})"
    else:
        live_data = f"Port {port} standby — Jev Reflex held state safely."

    c.execute("INSERT OR REPLACE INTO session_state VALUES(1,?,?,?,?)", (lane, prompt[:80], next_best, time.time()))
    c.commit(); c.close()

    jid = "JEV-" + hashlib.sha256(f"{prompt}{time.time()}".encode()).hexdigest()[:6].upper()
    summary = f"[{jid} // JEV REFLEX LAYER] LANE: {lane} -> PORT :{port} ({'SOLID' if solid else 'STANDBY'})\nCONTEXT: {prev_note}\nRECOMMENDED NEXT ACTION: {next_best}\nASTRA/ALSTRA RESPONSE: {live_data}"
    return {"id": jid, "lane": lane, "target_port": port, "endpoint_solid": solid, "continuity": prev_note, "next_best_action": next_best, "output": summary}

class Handler(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path == "/api/jev/feeds":
            self._j({"feeds": jev_feeds.sync_all_feeds()}); return

        if self.path.startswith("/api/jev/template/"):
            kind = self.path.split("/")[-1].lower()
            txt = TEMPLATES.get(kind, TEMPLATES["legal"]).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type","text/markdown; charset=utf-8"); self.send_header("Content-Disposition",f"attachment; filename=astra_{kind}_template.md"); self.end_headers()
            self.wfile.write(txt); return
        health = {k: {"port": p, "solid": check_endpoint(p)} for k, (p, _) in UPSTREAM_ENDPOINTS.items()}
        self._j({"status": "JEV_REFLEX_ONLINE", "openai_compat_endpoint": "/v1/chat/completions", "endpoints": health})
    def do_POST(self):
        if self.path == "/api/jev/add-feed":
            nm = d.get("name", "Custom External Feed")
            u = d.get("url", "https://algolia.com")
            fid = "FEED-" + hashlib.sha256(f"{u}{time.time()}".encode()).hexdigest()[:5].upper()
            self._j(jev_feeds.pull_single_feed(fid, nm, u)); return

        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/jev/ingest-file":
            self._j(self_install_from_file(d.get("file_path", "~/SYSTEM_MANIFEST.md")))
        elif self.path == "/api/jev/set-key":
            c = sqlite3.connect(DB); c.execute("INSERT OR REPLACE INTO cfg VALUES('typeface_key', ?)", (d.get("api_key","").strip(),)); c.commit(); c.close()
            self._j({"status": "TYPEFACE_KEY_SAVED"})
        elif self.path == "/v1/chat/completions":
            msgs = d.get("messages", [])
            prompt = msgs[-1].get("content", "") if msgs else d.get("prompt", "Status")
            res = reflex_decide(prompt)
            self._j({"id": res["id"], "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": res["output"]}, "finish_reason": "stop"}]})
        else:
            self._j(reflex_decide(d.get("prompt", "What should I do next across my system?")))

init()
HTTPServer(("0.0.0.0", 8111), Handler).serve_forever()
