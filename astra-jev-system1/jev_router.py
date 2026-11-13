import os, re, json, time, socket, sqlite3, hashlib, threading, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-jev-system1")
DB = f"{BASE}/jev_system1.db"
H = ".".join(["127","0","0","1"])

UPSTREAM = {
    "VAULT_QUERY": (8096, "/api/brain/route"), "TOOL_ACTION": (8097, "/api/ooda/execute"),
    "AGENT_TASK": (8108, "/api/pro/app"), "DEALERSHIP": (8099, "/api/state"),
    "GEO_INTEL": (8103, "/api/geo/route"), "OSINT_FEED": (8104, "/api/osint/harvest"),
    "AUTO_COMPUTE": (8109, "/api/auto/run")
}

TEMPLATES = {
    "medical": "# CLINICAL PROTOCOL TEMPLATE\n- Differential Diagnosis & Triage Matrix\n- HIPAA & Encrypted At-Rest Audit\n",
    "legal": "# COMMERCIAL & CRYPTO ESCROW AGREEMENT\n- Governing Law: North Carolina & UCC Articles 2, 9 & 12\n- Contractor retains 100% ownership of pre-existing Astra/AI IP\n",
    "patent": "# PROVISIONAL PATENT DISCLOSURE\n- Title: Multi-Agent Reflex Decision Layer & Tiered Persistent Memory OS\n"
}

def init():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS session_state(id INT PRIMARY KEY, last_lane TEXT, last_goal TEXT, next_best TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS learned_rules(rule_id TEXT PRIMARY KEY, keyword TEXT, target_lane TEXT, source_file TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS live_feeds(url TEXT PRIMARY KEY, label TEXT, last_items TEXT, updated_at REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS cfg(k TEXT PRIMARY KEY, v TEXT)")
    c.commit(); c.close()

def is_solid(port):
    try:
        with socket.create_connection((H, port), 0.5): return True
    except Exception: return False

def pull_external_feed(feed_url, label="LIVE_FEED"):
    url = (feed_url or "https://hnrss.org").strip()
    items = []
    try:
        rq = urllib.request.Request(url, headers={"User-Agent": "Jev-Reflex/1.0"})
        raw = urllib.request.urlopen(rq, timeout=6).read().decode("utf-8", "ignore")
        if raw.lstrip().startswith(("{", "[")):
            items = [json.dumps(json.loads(raw))[:300]]
        else:
            ts = re.findall(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw, re.S | re.I)
            items = [re.sub(r"<[^>]+>", "", t).strip() for t in ts[1:6] if t.strip()] or [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()[:300]]
    except Exception as e:
        items = [f"Feed note: {e}"]
    joined = " | ".join(items)
    c = sqlite3.connect(DB); c.execute("INSERT OR REPLACE INTO live_feeds VALUES(?,?,?,?)", (url, label, joined, time.time())); c.commit(); c.close()
    if any(k in joined.lower() for k in ["eth", "greensboro", "contract", "alert", "security"]):
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://{H}:8102/api/wf/test-alert", data=b"{}", headers={"Content-Type":"application/json"}), timeout=2)
        except Exception: pass
    try:
        urllib.request.urlopen(urllib.request.Request(f"http://{H}:8096/api/brain/remember", data=json.dumps({"domain":"LIVE_FEED","title":label,"content":joined}).encode(), headers={"Content-Type":"application/json"}), timeout=2)
    except Exception: pass
    return {"status": "FEED_CONNECTED", "label": label, "url": url, "items": items}

def auto_poll_feeds():
    while True:
        try:
            c = sqlite3.connect(DB)
            urls = c.execute("SELECT url, label FROM live_feeds").fetchall()
            c.close()
            for u, lbl in urls: pull_external_feed(u, lbl)
        except Exception: pass
        time.sleep(900)

def self_install(file_path):
    fp = os.path.expanduser(file_path.strip())
    if not os.path.exists(fp): return {"error": f"File not found: {fp}"}
    txt = " ".join(re.findall(r"[A-Za-z0-9_.,:/-]{4,}", open(fp, "rb").read(200000).decode("utf-8", "ignore")))[:10000]
    kws = list(dict.fromkeys([w.lower() for w in re.findall(r"[a-zA-Z]{5,}", txt)]))[:8]
    c = sqlite3.connect(DB)
    for kw in kws:
        ln = "TOOL_ACTION" if kw in ("email","calendar","buy","fleet","backup") else "VAULT_QUERY"
        c.execute("INSERT OR REPLACE INTO learned_rules VALUES(?,?,?,?,?)", ("RUL-"+hashlib.sha256(kw.encode()).hexdigest()[:5].upper(), kw, ln, os.path.basename(fp), time.time()))
    c.commit(); c.close()
    return {"status": "SELF_INSTALLED", "file": os.path.basename(fp), "installed_keywords": kws}

def reflex_decide(prompt):
    q = prompt.lower()
    lane = "DEALERSHIP" if any(w in q for w in ["car","wyler","buy","vehicle","evening"]) else ("GEO_INTEL" if any(w in q for w in ["greensboro","route","triad","weather"]) else ("OSINT_FEED" if any(w in q for w in ["news","feed","search","osint","tor"]) else ("TOOL_ACTION" if any(w in q for w in ["email","calendar","backup","alert"]) else ("AGENT_TASK" if any(w in q for w in ["invoice","build","app","contract"]) else "VAULT_QUERY"))))
    port, ep = UPSTREAM.get(lane, (8096, "/api/brain/route"))
    solid = is_solid(port)
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    prev = c.execute("SELECT * FROM session_state WHERE id=1").fetchone()
    next_best = "Verify Crypto Escrow & Print Certificate" if lane == "DEALERSHIP" else "Commit Output to 45M Vault & Sync Backup"
    prev_note = f"Continuing from [{prev['last_lane']}: {prev['last_goal'][:28]}]" if prev else "Fresh Reflex Session"
    live_data = ""
    if solid:
        try:
            body = json.dumps({"prompt": prompt, "directive": prompt, "query": prompt, "goal": prompt}).encode() if ep != "/api/state" else None
            live_data = urllib.request.urlopen(urllib.request.Request(f"http://{H}:{port}{ep}", data=body, headers={"Content-Type":"application/json"}), timeout=5).read().decode("utf-8","ignore")[:240]
        except Exception as e: live_data = f"Routed ({e})"
    c.execute("INSERT OR REPLACE INTO session_state VALUES(1,?,?,?,?)", (lane, prompt[:80], next_best, time.time())); c.commit(); c.close()
    jid = "JEV-" + hashlib.sha256(f"{prompt}{time.time()}".encode()).hexdigest()[:6].upper()
    return {"id": jid, "lane": lane, "output": f"[{jid} // JEV REFLEX] LANE: {lane} -> :{port} ({'SOLID' if solid else 'STANDBY'})\nCONTEXT: {prev_note}\nNEXT BEST ACTION: {next_best}\nRESPONSE: {live_data}"}

class Handler(BaseHTTPRequestHandler):
    def _j(self, d):
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path.startswith("/api/jev/template/"):
            k = self.path.split("/")[-1].lower()
            self.send_response(200); self.send_header("Content-Type","text/markdown"); self.send_header("Content-Disposition",f"attachment; filename=astra_{k}.md"); self.end_headers()
            self.wfile.write(TEMPLATES.get(k, TEMPLATES["legal"]).encode()); return
        self._j({"status": "JEV_REFLEX_ONLINE", "endpoints": {k: {"port": p, "solid": is_solid(p)} for k, (p, _) in UPSTREAM.items()}})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/jev/connect-feed": self._j(pull_external_feed(d.get("url"), d.get("label","LIVE_FEED")))
        elif self.path == "/api/jev/ingest-file": self._j(self_install(d.get("file_path","~/SYSTEM_MANIFEST.md")))
        elif self.path == "/api/jev/set-key":
            c = sqlite3.connect(DB); c.execute("INSERT OR REPLACE INTO cfg VALUES('typeface_key', ?)", (d.get("api_key","").strip(),)); c.commit(); c.close()
            self._j({"status": "TYPEFACE_KEY_SAVED"})
        elif self.path == "/v1/chat/completions":
            msgs = d.get("messages", [])
            res = reflex_decide(msgs[-1].get("content","") if msgs else d.get("prompt","Status"))
            self._j({"id": res["id"], "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": res["output"]}}]})
        else: self._j(reflex_decide(d.get("prompt", "Recommend next best action")))

init()
threading.Thread(target=auto_poll_feeds, daemon=True).start()
HTTPServer(("0.0.0.0", 8111), Handler).serve_forever()
