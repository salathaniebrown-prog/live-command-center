import os, re, json, time, sqlite3, hashlib, urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-osint-harvester")
DB = f"{BASE}/world_knowledge.db"

def init():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS intel(id TEXT PRIMARY KEY, source TEXT, query TEXT, summary TEXT, ts REAL)")
    c.commit(); c.close()

def clean_html(raw):
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S|re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt)).strip()

def harvest_world_intel(query, mode="WEB_ALL"):
    q_enc = urllib.parse.quote(query)
    findings = []
    # 1. Wikipedia Encyclopedic Wisdom API
    try:
        u = f"https://wikipedia.org{q_enc}"
        rq = urllib.request.Request(u, headers={"User-Agent": "Astra-OSINT/1.0"})
        d = json.loads(urllib.request.urlopen(rq, timeout=4).read().decode())
        if d.get("extract"): findings.append(f"[WIKIPEDIA] {d.get('title')}: {d['extract'][:320]}")
    except Exception: pass
    # 2. Hacker News / Tech Wisdom API
    try:
        u = f"https://algolia.com{q_enc}&hitsPerPage=3"
        hits = json.loads(urllib.request.urlopen(u, timeout=4).read().decode()).get("hits", [])
        for h in hits:
            if h.get("title"): findings.append(f"[TECH_INTEL] {h['title']} ({h.get('url','HN')})")
    except Exception: pass
    # 3. Direct URL or Tor .onion SOCKS5 Check
    if query.startswith("http://") or query.startswith("https://"):
        try:
            if ".onion" in query:
                import requests
                r = requests.get(query, proxies={"http":"socks5h://127.0.0.1:9050","https":"socks5h://127.0.0.1:9050"}, timeout=10)
                findings.append(f"[TOR_ONION] {clean_html(r.text)[:450]}")
            else:
                rq = urllib.request.Request(query, headers={"User-Agent": "Mozilla/5.0 Chrome/130.0"})
                raw = urllib.request.urlopen(rq, timeout=5).read().decode("utf-8", "ignore")
                findings.append(f"[CHROME_WEB] {clean_html(raw)[:450]}")
        except Exception as e:
            findings.append(f"[URL_NOTE] {e} (Start Tor daemon for .onion routing)")
    summary = "\n".join(findings) or f"[SYNTHESIZED] Indexed query '{query}' across OSINT knowledge nodes."
    iid = "INT-" + hashlib.sha256(f"{query}{time.time()}".encode()).hexdigest()[:6].upper()
    c = sqlite3.connect(DB); c.execute("INSERT INTO intel VALUES(?,?,?,?,?)", (iid, mode, query, summary, time.time())); c.commit(); c.close()
    try:
        rq = urllib.request.Request("http://127.0.0", data=json.dumps({"domain":"WORLD_OSINT","title":query[:36],"content":summary}).encode(), headers={"Content-Type":"application/json"})
        urllib.request.urlopen(rq, timeout=2)
    except Exception: pass
    return {"id": iid, "query": query, "findings_count": len(findings), "summary": summary}

class H(BaseHTTPRequestHandler):
    def _j(self, d):
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        c = sqlite3.connect(DB); n = c.execute("SELECT COUNT(*) FROM intel").fetchone(); c.close()
        self._j({"status":"ONLINE","indexed_intel":n,"tor_socks":"127.0.0.1:9050"})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
        self._j(harvest_world_intel(d.get("query","Artificial Intelligence"), d.get("mode","WEB_ALL")))

init()
HTTPServer(("0.0.0.0", 8104), H).serve_forever()
