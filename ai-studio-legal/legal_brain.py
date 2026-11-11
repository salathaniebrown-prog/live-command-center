import os
import json
import time
import sqlite3
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "legal_doctrine.db")
REAL_LOG = os.path.expanduser("~/telemetry-spine/REAL.log")

MASTER_SYSTEM_DOCTRINE = """[ALSTRA // ASTRA LEGAL EXCELLENCE & CRYPTO PROTECTION DOCTRINE]
ACADEMIC BENCHMARK: Harvard Law & Duke Law Graduate Doctrine (Corporate, Commercial, FinTech & Digital Asset Law).
CORE MANDATE:
1. CRYPTO & TREASURY PROTECTION: Apply UCC Article 9 & Article 12 (Controllable Electronic Records), Wyoming Digital Asset statutes, multi-sig custody segregation, and non-custodial escrow verification to protect BTC/ETH/USDC capital deployed into AI datacenter and vehicle builds.
2. VEHICLE & HARDWARE ACQUISITION SHIELD: Audit Bills of Sale, UCC-1 liens, title transfers, and dealer escrow terms (Wyler / Dealerslink) to ensure clear title and zero recourse exposure.
3. ENTITY & IP ISOLATION: Structure AI Studio, Deepspace Ledgers, and hardware builds inside isolated LLC holding structures so operating liabilities never pierce core crypto reserves.
4. OUTPUT STANDARD: Cite governing legal doctrines, identify hidden counterparty risks, and provide actionable protective clauses."""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS doctrines (
                    id TEXT PRIMARY KEY,
                    domain TEXT,
                    school_framework TEXT,
                    principle TEXT,
                    protection_rule TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS audits (
                    audit_id TEXT PRIMARY KEY,
                    query TEXT,
                    risk_score TEXT,
                    analysis TEXT,
                    audit_hash TEXT,
                    created_at REAL
                )''')
    if c.execute("SELECT COUNT(*) FROM doctrines").fetchone()[0] == 0:
        seeds = [
            ("DOC-01", "Digital Asset Property & Custody", "Duke Law FinTech / UCC Art. 12",
             "Controllable Electronic Records (CER) & Control Perfection",
             "Maintain exclusive cryptographic key control and separate treasury vaults from operational hot wallets."),
            ("DOC-02", "Commercial Vehicle & Equipment Title", "Harvard Law Commercial / UCC Art. 2 & 9",
             "Good-Faith Purchaser & Lien-Free Title Transfer",
             "Verify clean VIN title, signed Bill of Sale, and release of floorplan liens prior to final escrow settlement."),
            ("DOC-03", "Corporate Veil & Datacenter Liability", "Harvard Corporate Governance Doctrine",
             "Series / Holding LLC Ring-Fencing",
             "Isolate physical robotics, H100/server hardware, and vehicle fleet assets in separate operating entities."),
            ("DOC-04", "Smart Escrow & Counterparty Risk", "Duke Law Contract & Digital Commerce",
             "Atomic Conditional Settlement & Force Majeure",
             "Bind release of ETH/USDC funds strictly to verifiable delivery milestones and cryptographic hash receipts.")
        ]
        c.executemany("INSERT INTO doctrines VALUES (?, ?, ?, ?, ?)", seeds)
    conn.commit()
    conn.close()

def log_telemetry(event_type, detail):
    try:
        os.makedirs(os.path.dirname(REAL_LOG), exist_ok=True)
        with open(REAL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "source": "ALSTRA_LEGAL_BRAIN", "event": event_type, "detail": detail}) + "\n")
    except Exception:
        pass

def analyze_legal_query(query):
    q_low = query.lower()
    matched = []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM doctrines").fetchall()]

    for r in rows:
        if any(k in q_low for k in ["crypto", "eth", "btc", "wallet", "escrow", "car", "wyler", "vin", "title", "build", "llc", "contract"]):
            matched.append(r)
    if not matched:
        matched = rows[:2]

    risk = "LOW / PROTECTED" if "escrow" in q_low or "llc" in q_low else "MODERATE — APPLY RING-FENCE CLAUSE"
    summary = " | ".join(f"[{m['school_framework']}] {m['principle']}: {m['protection_rule']}" for m in matched)
    audit_id = f"LEG-{hashlib.sha256(f'{query}{time.time()}'.encode()).hexdigest()[:6].upper()}"
    audit_hash = "0x" + hashlib.sha256(f"{audit_id}:{summary}".encode()).hexdigest()

    conn.execute("INSERT INTO audits VALUES (?, ?, ?, ?, ?, ?)",
                 (audit_id, query, risk, summary, audit_hash, time.time()))
    conn.commit()
    conn.close()
    log_telemetry("DOCTRINE_AUDIT", f"{audit_id} | Risk: {risk}")
    return {"audit_id": audit_id, "risk_score": risk, "analysis": summary, "audit_hash": audit_hash, "system_prompt": MASTER_SYSTEM_DOCTRINE}

class LegalHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/legal/state":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            docs = [dict(r) for r in conn.execute("SELECT * FROM doctrines").fetchall()]
            audits = [dict(r) for r in conn.execute("SELECT * FROM audits ORDER BY created_at DESC LIMIT 5").fetchall()]
            conn.close()
            self._json({"doctrines": docs, "audits": audits, "system_prompt": MASTER_SYSTEM_DOCTRINE})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/api/legal/audit":
            q = payload.get("query", "Audit crypto escrow and vehicle title protection")
            self._json(analyze_legal_query(q))

if __name__ == "__main__":
    init_db()
    print("[⚖️] Astra/Alstra Legal Doctrine Brain Online at http://127.0.0.1:8095")
    HTTPServer(("0.0.0.0", 8095), LegalHandler).serve_forever()
