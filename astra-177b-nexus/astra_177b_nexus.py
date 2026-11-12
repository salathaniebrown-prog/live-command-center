import os, json, time, sqlite3, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-177b-nexus")
DB = f"{BASE}/nexus_177b_brain.db"
SHARDS = [{"gpu": f"GPU-{i}", "expert": e, "params": "22.1B"} for i, e in enumerate(["Planning","Legal","Crypto","Fleet","Code","BI SQL","Crossover","Android"])]

def init():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS ideas(idea_id TEXT PRIMARY KEY, title TEXT, domain TEXT, payload TEXT, generation INT, proof_hash TEXT)")
    if c.execute("SELECT COUNT(*) FROM ideas").fetchone() == 0:
        for i, t, d, p in [("IDEA-01","Crypto Escrow","CRYPTO","ETH escrow + VIN title"),("IDEA-02","LLC Ring-Fence","LEGAL","UCC Art. 12 asset shield"),("IDEA-03","Voice Agent","ANDROID","Self-evolving skills"),("IDEA-04","45M BI Oracle","BI_SQL","Cross-DB SQL intelligence")]:
            c.execute("INSERT INTO ideas VALUES(?,?,?,?,1,?)", (i, t, d, p, "0x"+hashlib.sha256(t.encode()).hexdigest()))
    c.commit(); c.close()

class H(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        ideas = [dict(r) for r in c.execute("SELECT * FROM ideas ORDER BY rowid DESC LIMIT 10")]
        c.close(); self._j({"gpu_topology": SHARDS, "ideas": ideas})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        if self.path == "/api/nexus/crossover":
            a = c.execute("SELECT * FROM ideas WHERE idea_id=?", (d.get("idea_a","IDEA-01"),)).fetchone()
            b = c.execute("SELECT * FROM ideas WHERE idea_id=?", (d.get("idea_b","IDEA-02"),)).fetchone()
            gen = max(a["generation"], b["generation"]) + 1 if (a and b) else 2
            nid = "IDEA-" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:5].upper()
            title = f"{a['title']} x {b['title']} (Gen {gen})" if (a and b) else "Hybrid Synthesis"
            pay = f"{a['payload']} + {b['payload']}" if (a and b) else "Synthesized Node"
            ph = "0x" + hashlib.sha256(pay.encode()).hexdigest()
            c.execute("INSERT INTO ideas VALUES(?,?,?,?,?,?)", (nid, title, "HYBRID", pay, gen, ph))
            c.commit(); c.close()
            self._j({"status":"SYNTHESIZED","idea":{"idea_id":nid,"title":title,"payload":pay},"proving":{"proof_hash":ph}})
        else:
            t = d.get("title") or d.get("goal") or "Evolved Node"
            nid = "IDEA-" + hashlib.sha256(f"{t}{time.time()}".encode()).hexdigest()[:5].upper()
            ph = "0x" + hashlib.sha256(t.encode()).hexdigest()
            c.execute("INSERT INTO ideas VALUES(?,?,?,?,1,?)", (nid, t, "EVOLVED", t, ph))
            c.commit(); c.close()
            self._j({"status":"OK","idea_id":nid,"skill_id":nid,"title":t,"name":t[:24],"proving":{"proof_hash":ph}})

init()
HTTPServer(("0.0.0.0", 8100), H).serve_forever()
