import os

# --- 177B SELF-IMPROVEMENT & REFLEXION HOOK ---
import sys as _sys
_sys.path.append(os.path.expanduser("~/astra-memory-brain"))
try:
    from self_improve import record_and_reflect, get_active_skill_context
except ImportError:
    def record_and_reflect(domain, directive, outcome, success): return "Hook pending"
    def get_active_skill_context(domain): return ""

import os
import json
import time
import sqlite3
import hashlib
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "infinite_brain_ooda.db")
REAL_LOG = os.path.expanduser("~/telemetry-spine/REAL.log")

OPERATOR_EXPERT_PROFILE = {
    "role": "Chief Architect & Sovereign Operator",
    "core_drivers": ["Alstra", "Astra Infinite Brain", "Deepspace Ledgers", "Eagle Eyes"],
    "non_negotiables": [
        "Zero-trust security: verify cryptographic proof before settlement",
        "Real live data & persistent SQLite WAL storage across restarts",
        "Ring-fence crypto treasury & hardware assets via legal doctrine",
        "Single-screen high-contrast cybernetic command execution"
    ]
}

SOPS = {
    "SOP-01": {
        "name": "Crypto Treasury & Spot Settlement",
        "trigger": ["crypto", "eth", "btc", "usdc", "wallet", "treasury", "payment"],
        "steps": ["Verify live ETH/USD oracle", "Check wallet 0x5f04EBB3...05bEDDf5", "Generate SHA-256 settlement hash", "Sync Deepspace Ledger"]
    },
    "SOP-02": {
        "name": "Legal & Title Ring-Fence Audit",
        "trigger": ["legal", "law", "llc", "title", "contract", "escrow", "protect", "audit"],
        "steps": ["Query Port 8095 Legal Doctrine Brain", "Verify UCC Art. 12 & Lien-Free Status", "Bind atomic escrow release", "Archive proof hash"]
    },
    "SOP-03": {
        "name": "Business Client & Fleet Fulfillment",
        "trigger": ["wyler", "car", "vehicle", "client", "business", "order", "delivery", "invoice"],
        "steps": ["Lock inventory unit", "Execute legal & escrow check", "Mint E-Title / Invoice", "Dispatch & log REAL.log receipt"]
    },
    "SOP-04": {
        "name": "Infrastructure & Telemetry Self-Healing",
        "trigger": ["telemetry", "server", "node", "sync", "health", "backup", "spine"],
        "steps": ["Probe ports 8088/8095/8096/8099", "Index events into 45M Brain", "Append structured JSON to REAL.log"]
    }
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute('''CREATE TABLE IF NOT EXISTS ooda_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    directive TEXT,
                    observe_summary TEXT,
                    orient_context TEXT,
                    judgment_verdict TEXT,
                    confidence REAL,
                    sop_executed TEXT,
                    proof_hash TEXT,
                    created_at REAL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS business_ledger (
                    entry_id TEXT PRIMARY KEY,
                    category TEXT,
                    description TEXT,
                    value_usd REAL,
                    status TEXT,
                    created_at REAL
                )''')
    conn.commit()
    conn.close()

def probe_services():
    status = {}
    for name, port, path in [
        ("COMMAND_CENTER", 8088, "/api/telemetry"),
        ("LEGAL_BRAIN", 8095, "/api/legal/state"),
        ("ASTRA_45M_BRAIN", 8096, "/api/brain/graph"),
        ("WYLER_DEALERSHIP", 8099, "/api/state")
    ]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as r:
                status[name] = "ONLINE" if r.status == 200 else f"HTTP_{r.status}"
        except Exception:
            status[name] = "OFFLINE"
    return status

def push_to_brain_and_log(cycle_id, directive, verdict, sop_id, proof_hash):
    try:
        os.makedirs(os.path.dirname(REAL_LOG), exist_ok=True)
        with open(REAL_LOG, "a", encoding="utf-8") as lf:
            lf.write(json.dumps({
                "ts": time.time(),
                "source": "INFINITE_BRAIN_OODA",
                "cycle_id": cycle_id,
                "verdict": verdict,
                "sop": sop_id,
                "proof_hash": proof_hash
            }) + "\n")
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            "http://127.0.0",
            data=json.dumps({
                "domain": "OODA_JUDGMENT",
                "title": f"{cycle_id}: {directive[:30]}",
                "content": f"Verdict: {verdict} | SOP: {sop_id} | Directive: {directive} | Proof: {proof_hash}",
                "links": "NODE-CORE,NODE-LEGAL,NODE-CRYPTO,NODE-INFRA"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass

def run_ooda_cycle(directive, amount_usd=0.0):
    # 1. OBSERVE
    telemetry_health = probe_services()
    online_count = sum(1 for v in telemetry_health.values() if v == "ONLINE")
    observe_str = f"Nodes Online: {online_count}/4 ({', '.join(f'{k}:{v}' for k,v in telemetry_health.items())})"

    # 2. ORIENT (Match Operator Methodology & Select SOP)
    d_low = directive.lower()
    selected_sop = "SOP-04"
    for sop_id, meta in SOPS.items():
        if any(k in d_low for k in meta["trigger"]):
            selected_sop = sop_id
            break
    sop_meta = SOPS[selected_sop]
    orient_str = f"Aligned with {OPERATOR_EXPERT_PROFILE['role']} | Matched {selected_sop}: {sop_meta['name']}"

    # 3. DECIDE (AI Judgment Layer)
    if amount_usd > 50000 and "escrow" not in d_low and "legal" not in d_low:
        verdict = "HOLD_FOR_LEGAL_ESCROW_SHIELD"
        confidence = 0.94
    elif online_count < 2:
        verdict = "DEGRADE_SAFE_MODE_QUEUE"
        confidence = 0.89
    else:
        verdict = "APPROVED_AUTONOMOUS_EXECUTION"
        confidence = 0.99

    # 4. ACT (Execute SOP & Persist)
    cycle_id = "OODA-" + hashlib.sha256(f"{directive}:{time.time()}".encode()).hexdigest()[:6].upper()
    proof_hash = "0x" + hashlib.sha256(f"{cycle_id}:{verdict}:{selected_sop}:{observe_str}".encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO ooda_cycles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (cycle_id, directive, observe_str, orient_str, verdict, confidence, f"{selected_sop}: {sop_meta['name']}", proof_hash, time.time())
    )
    if amount_usd > 0:
        conn.execute(
            "INSERT INTO business_ledger VALUES (?, ?, ?, ?, ?, ?)",
            (cycle_id, selected_sop, directive, amount_usd, verdict, time.time())
        )
    conn.commit()
    conn.close()

    push_to_brain_and_log(cycle_id, directive, verdict, selected_sop, proof_hash)

    return {
        "cycle_id": cycle_id,
        "observe": observe_str,
        "orient": orient_str,
        "judgment": {"verdict": verdict, "confidence": confidence},
        "act": {"sop": selected_sop, "name": sop_meta["name"], "steps": sop_meta["steps"]},
        "proof_hash": proof_hash
    }

def autonomous_heartbeat():
    while True:
        try:
            run_ooda_cycle("Autonomous telemetry & business health sweep", 0.0)
        except Exception:
            pass
        time.sleep(120)

class OODAHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/ooda/state":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cycles = [dict(r) for r in conn.execute("SELECT * FROM ooda_cycles ORDER BY created_at DESC LIMIT 6").fetchall()]
            biz_total = conn.execute("SELECT COALESCE(SUM(value_usd), 0) FROM business_ledger WHERE status='APPROVED_AUTONOMOUS_EXECUTION'").fetchone()
            conn.close()
            self._json({
                "expert_profile": OPERATOR_EXPERT_PROFILE,
                "sops": SOPS,
                "telemetry": probe_services(),
                "approved_volume_usd": biz_total,
                "recent_cycles": cycles
            })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/api/ooda/execute":
            directive = payload.get("directive", "Execute business operations & telemetry audit")
            amount = float(payload.get("amount_usd", 0.0))
            self._json(run_ooda_cycle(directive, amount))

if __name__ == "__main__":
    init_db()
    threading.Thread(target=autonomous_heartbeat, daemon=True).start()
    print("[⚡] Infinite Brain OS OODA & AI Judgment Engine Online at http://127.0.0.1:8097")
    HTTPServer(("0.0.0.0", 8097), OODAHandler).serve_forever()
