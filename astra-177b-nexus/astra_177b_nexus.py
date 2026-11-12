import os, json, time, sqlite3, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-177b-nexus")
DB = f"{BASE}/nexus_177b_brain.db"
SHARDS = [{"gpu": f"GPU-{i}", "expert": e, "params": "22.1B"} for i, e in enumerate([
    "Planning", "Legal Shield", "Crypto Vault", "Wyler Fleet", "Auto-Code", "BI SQL", "Idea Crossover", "Android OS"
])]

def init_db():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS ideas(idea_id TEXT PRIMARY KEY, title TEXT, domain TEXT, payload TEXT, generation INT, proof_hash TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS skills(skill_id TEXT PRIMARY KEY, name TEXT, goal TEXT, fitness REAL)")
    if c.execute("SELECT COUNT(*) FROM ideas").fetchone()[0] == 0:
        for iid, t, d, p in [
            ("IDEA-01", "Crypto Escrow Settlement", "CRYPTO", "Atomic ETH/USDC escrow tied to VIN E-Title."),
            ("IDEA-02", "LLC Hardware Ring-Fence", "LEGAL", "Isolate racks & fleet under UCC Art. 12."),
            ("IDEA-03", "Self-Evolving Voice Agent", "ANDROID", "Hands-free assistant writing reusable skills."),
            ("IDEA-04", "45M Cross-DB BI Oracle", "BI_SQL", "Unified SQL warehouse feeding any LLM.")
        ]:
            ph = "0x" + hashlib.sha256(f"{iid}{t}".encode()).hexdigest()
            c.execute("INSERT INTO ideas VALUES(?,?,?,?,1,?)", (iid, t, d, p, ph))
    c.commit(); c.close()

class H(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path == "/api/nexus/state":
            c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
            ideas = [dict(r) for r in c.execute("SELECT * FROM ideas ORDER BY rowid DESC LIMIT 10")]
            c.close()
            self._j({"gpu_topology": SHARDS, "ideas": ideas})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        if self.path == "/api/nexus/crossover":
            a = c.execute("SELECT * FROM ideas WHERE idea_id=?", (d.get("idea_a", "IDEA-01"),)).fetchone()
            b = c.execute("SELECT * FROM ideas WHERE idea_id=?", (d.get("idea_b", "IDEA-02"),)).fetchone()
            if not a or not b:
                c.close(); return self._j({"error": "Missing parent ideas"}, 400)
            gen = max(a["generation"], b["generation"]) + 1
            nid = "IDEA-" + hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:5].upper()
            title = f"{a['title'].split()[0]} x {b['title'].split()[0]} Hybrid (Gen {gen})"
            pay = f"[177B GEN-{gen}] {a['payload']} <+> {b['payload']}"
            ph = "0x" + hashlib.sha256(pay.encode()).hexdigest()
            c.execute("INSERT INTO ideas VALUES(?,?,?,?,?,?)", (nid, title, "HYBRID", pay, gen, ph))
            c.commit(); c.close()
            self._j({"status": "SYNTHESIZED", "idea": {"idea_id": nid, "title": title, "payload": pay}, "proving": {"proof_hash": ph}})
        elif self.path == "/api/nexus/add_idea":
            t = d.get("title", "Operator Concept")
            nid = "IDEA-" + hashlib.sha256(f"{t}{time.time()}".encode()).hexdigest()[:5].upper()
            ph = "0x" + hashlib.sha256(t.encode()).hexdigest()
            c.execute("INSERT INTO ideas VALUES(?,?,?,?,1,?)", (nid, t, "SEED", t, ph))
            c.commit(); c.close()
            self._j({"status": "SEEDED", "idea_id": nid, "title": t})
        elif self.path == "/api/nexus/evolve":
            g = d.get("goal", "Self-upgrade telemetry")
            sid = "SKL-" + hashlib.sha256(f"{g}{time.time()}".encode()).hexdigest()[:5].upper()
            ph = "0x" + hashlib.sha256(sid.encode()).hexdigest()
            c.execute("INSERT INTO skills VALUES(?,?,?,0.995)", (sid, g[:24], g))
            c.commit(); c.close()
            self._j({"status": "SELF_UPGRADED", "skill_id": sid, "name": g[:24], "proving": {"proof_hash": ph}})

if __name__ == "__main__":
    init_db()
    HTTPServer(("0.0.0.0", 8100), H).serve_forever()
