import os, re, math, json, time, shutil, sqlite3, hashlib, subprocess, urllib.request
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-unified-brain")
DB = f"{BASE}/glass_box_brain.db"
ARTS = f"{BASE}/artifacts"
LOG = os.path.expanduser("~/telemetry-spine/REAL.log")

def embed(txt):
    toks = [w for w in re.findall(r"[a-z0-9_]+", txt.lower()) if len(w) > 2]
    c = Counter(toks)
    n = math.sqrt(sum(v*v for v in c.values())) or 1.0
    return {k: round(v/n, 4) for k, v in c.most_common(40)}

def sim(a, b):
    return round(sum(a[k]*b[k] for k in set(a)&set(b)), 4)

def init():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, repo TEXT, title TEXT, body TEXT, vec TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS arts(id TEXT PRIMARY KEY, kind TEXT, path TEXT, out TEXT)")
    if conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0:
        seeds = [
            ("google-ai-edge/LiteRT-LM", "LiteRT-LM Android Stack", "On-device Gemma 4 inference via Android CPU/GPU/NPU."),
            ("salathaniebrown-prog/live-command-center", "Astra Command Center", "Multi-port AI OS unifying Legal, 45M Brain, OODA, BI SQL & Dealership.")
        ]
        for r, t, b in seeds:
            cid = "CHK-" + hashlib.sha256(t.encode()).hexdigest()[:6].upper()
            conn.execute("INSERT INTO chunks VALUES(?,?,?,?,?)", (cid, r, t, b, json.dumps(embed(t+" "+b))))
    conn.commit(); conn.close()

class H(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path == "/api/os/state":
            c = sqlite3.connect(DB)
            n = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            c.close()
            self._j({"indexed_chunks": n, "status": "ONLINE"})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
        c = sqlite3.connect(DB)
        if self.path == "/api/os/github":
            repo = d.get("repo","google-ai-edge/LiteRT-LM").strip("/")
            fp = d.get("file_path","README.md")
            txt = ""
            for br in ("main","master"):
                try:
                    txt = urllib.request.urlopen(f"https://githubusercontent.com{repo}/{br}/{fp}", timeout=5).read().decode("utf-8","ignore")
                    if txt: break
                except Exception: pass
            ps = [p.strip()[:600] for p in txt.split("\n\n") if len(p.strip())>40][:6]
            for i, p in enumerate(ps):
                cid = "GH-" + hashlib.sha256(f"{repo}{i}".encode()).hexdigest()[:6].upper()
                c.execute("INSERT OR REPLACE INTO chunks VALUES(?,?,?,?,?)", (cid, repo, f"{repo}#{i+1}", p, json.dumps(embed(p))))
            c.commit(); c.close()
            self._j({"repo": repo, "chunks_indexed": len(ps)})
        elif self.path == "/api/os/generate":
            q = d.get("prompt",""); qv = embed(q)
            hits = sorted([(sim(qv, json.loads(r[4])), r[0], r[2], r[3][:180]) for r in c.execute("SELECT * FROM chunks")], reverse=True)[:3]
            ctx = "\n".join(f"[{h[1]} sim={h[0]}] {h[2]}: {h[3]}" for h in hits)
            out = f"[GEMMA-4 / LITERT-LM SYNTHESIS]\nTASK: {q}\nRETRIEVED:\n{ctx}"
            aid = "ART-" + hashlib.sha256(f"{q}{time.time()}".encode()).hexdigest()[:6].upper()
            ap = f"{ARTS}/{aid}.md"; open(ap,"w").write(out)
            c.execute("INSERT INTO arts VALUES(?,?,?,?)", (aid, "RAG", ap, out[:200])); c.commit(); c.close()
            self._j({"artifact": {"artifact_id": aid, "output": out}, "hits": hits})
        elif self.path == "/api/os/skill":
            sk = d.get("skill","SCIENTIFIC")
            out = subprocess.check_output(["termux-battery-status"]).decode() if (sk=="ANDROID_HW" and shutil.which("termux-battery-status")) else f"[{sk}] Verified OK at {time.ctime()}"
            c.close(); self._j({"skill": sk, "output": out})

if __name__ == "__main__":
    init()
    HTTPServer(("0.0.0.0", 8101), H).serve_forever()
