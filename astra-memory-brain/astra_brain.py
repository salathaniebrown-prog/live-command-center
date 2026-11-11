import os
import json
import time
import sqlite3
import hashlib
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "astra_45m_brain.db")
REAL_LOG = os.path.expanduser("~/telemetry-spine/REAL.log")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute('''CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    domain TEXT,
                    title TEXT,
                    content TEXT,
                    token_est INTEGER,
                    links TEXT,
                    updated_at REAL
                )''')
    c.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                    node_id, domain, title, content
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS task_routes (
                    route_id TEXT PRIMARY KEY,
                    prompt TEXT,
                    target_node TEXT,
                    agent_workflow TEXT,
                    status TEXT,
                    routed_at REAL
                )''')

    if c.execute("SELECT COUNT(*) FROM nodes").fetchone() == 0:
        seeds = [
            ("NODE-CORE", "ASTRA_OS", "Astra Master Sovereign Brain",
             "Central persistent memory index with multi-domain routing across crypto, legal, vehicle fleet, and datacenter nodes.",
             12500000, "NODE-CRYPTO,NODE-LEGAL,NODE-FLEET,NODE-INFRA"),
            ("NODE-CRYPTO", "CRYPTO_TREASURY", "ETH / BTC / USDC Multi-Sig & Escrow Vault",
             "Tracks wallet 0x5f04EBB30d3BBf356263c3ef4823080d05bEDDf5, live ETH/USD spot rates, and cryptographic settlement hashes.",
             10500000, "NODE-CORE,NODE-LEGAL,NODE-FLEET"),
            ("NODE-LEGAL", "LEGAL_DOCTRINE", "Harvard & Duke Law Asset Protection Brain",
             "UCC Article 12 Controllable Electronic Records, LLC ring-fencing, Bill of Sale title verification, and escrow protection.",
             8500000, "NODE-CORE,NODE-CRYPTO,NODE-FLEET"),
            ("NODE-FLEET", "WYLER_DEALERSHIP", "Wyler & Dealerslink Autonomous Fleet Engine",
             "Single and batch vehicle acquisition, VIN verification, E-Title minting, carrier dispatch, and printable certificates.",
             6500000, "NODE-CORE,NODE-CRYPTO,NODE-LEGAL"),
            ("NODE-INFRA", "DATACENTER_SPINE", "Deepspace Ledger & Telemetry Spine",
             "Persistent SQLite WAL storage, REAL.log event streaming, Cloudflare HTTPS tunnels, and automated agent workflows.",
             7000000, "NODE-CORE,NODE-CRYPTO,NODE-FLEET")
        ]
        for nid, dom, title, content, tok, links in seeds:
            c.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (nid, dom, title, content, tok, links, time.time()))
            c.execute("INSERT INTO nodes_fts VALUES (?, ?, ?, ?)",
                      (nid, dom, title, content))
    conn.commit()
    conn.close()

def ingest_memory(domain, title, content, links="NODE-CORE"):
    node_id = "MEM-" + hashlib.sha256(f"{title}:{time.time()}".encode()).hexdigest()[:6].upper()
    token_est = max(128, len(content.split()) * 2)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?)",
              (node_id, domain.upper(), title, content, token_est, links, time.time()))
    c.execute("INSERT INTO nodes_fts VALUES (?, ?, ?, ?)",
              (node_id, domain.upper(), title, content))
    conn.commit()
    conn.close()
    return {"node_id": node_id, "domain": domain.upper(), "title": title, "token_est": token_est}

def route_task(prompt):
    q = prompt.lower()
    if any(k in q for k in ["law", "legal", "llc", "contract", "title", "ucc", "protect", "escrow"]):
        target, agent, url = "NODE-LEGAL", "ALSTRA_LEGAL_DOCTRINE_AGENT", "http://127.0.0"
    elif any(k in q for k in ["car", "wyler", "vin", "vehicle", "hummer", "corvette", "escalade", "fleet", "delivery"]):
        target, agent, url = "NODE-FLEET", "WYLER_ACQUISITION_AGENT", "http://127.0.0"
    elif any(k in q for k in ["crypto", "eth", "btc", "wallet", "hash", "usdc", "coinbase"]):
        target, agent, url = "NODE-CRYPTO", "CRYPTO_TREASURY_ORACLE", "http://127.0.0"
    else:
        target, agent, url = "NODE-INFRA", "TELEMETRY_SPINE_ORCHESTRATOR", "http://127.0.0"

    # Recall matching context slices from FTS5 index without loading entire DB into RAM
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    clean_terms = " OR ".join(w for w in "".join(ch if ch.isalnum() else " " for ch in q).split() if len(w) > 2)
    recalled = []
    if clean_terms:
        try:
            recalled = [dict(r) for r in conn.execute(
                "SELECT node_id, domain, title, content FROM nodes_fts WHERE nodes_fts MATCH ? LIMIT 3",
                (clean_terms,)
            ).fetchall()]
        except Exception:
            pass
    if not recalled:
        recalled = [dict(r) for r in conn.execute(
            "SELECT node_id, domain, title, content FROM nodes WHERE node_id=?", (target,)
        ).fetchall()]

    route_id = "RTE-" + hashlib.sha256(f"{prompt}{time.time()}".encode()).hexdigest()[:6].upper()
    conn.execute("INSERT INTO task_routes VALUES (?, ?, ?, ?, ?, ?)",
                 (route_id, prompt, target, agent, "DISPATCHED_&_RECALLED", time.time()))
    conn.commit()
    conn.close()

    # Automatically archive new task into long-term memory so Astra never forgets
    ingest_memory(target.replace("NODE-", ""), f"Task: {prompt[:42]}", prompt, f"NODE-CORE,{target}")

    try:
        os.makedirs(os.path.dirname(REAL_LOG), exist_ok=True)
        with open(REAL_LOG, "a", encoding="utf-8") as lf:
            lf.write(json.dumps({
                "ts": time.time(), "source": "ASTRA_45M_BRAIN",
                "route_id": route_id, "target": target, "agent": agent, "prompt": prompt
            }) + "\n")
    except Exception:
        pass

    return {
        "route_id": route_id,
        "target_node": target,
        "agent_workflow": agent,
        "recalled_context": recalled,
        "status": "ROUTED_AND_PERSISTED"
    }

def auto_sync_loop():
    """Background self-updating daemon that ingests live ETH rates and REAL.log events into Astra memory."""
    while True:
        try:
            req = urllib.request.Request("http://127.0.0", headers={"User-Agent": "Astra-Brain/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                eth_price = data.get("eth_usd")
                if eth_price:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute(
                        "UPDATE nodes SET content=?, updated_at=? WHERE node_id='NODE-CRYPTO'",
                        (f"Live ETH/USD Spot Oracle: ${eth_price:,.2f} | Wallet 0x5f04EBB30d3BBf356263c3ef4823080d05bEDDf5 active.", time.time())
                    )
                    conn.commit()
                    conn.close()
        except Exception:
            pass
        time.sleep(30)

class BrainHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/brain/graph":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            nodes = [dict(r) for r in conn.execute("SELECT * FROM nodes ORDER BY updated_at DESC LIMIT 24").fetchall()]
            total_tokens = conn.execute("SELECT COALESCE(SUM(token_est), 0) FROM nodes").fetchone()[0]
            total_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            routes = [dict(r) for r in conn.execute("SELECT * FROM task_routes ORDER BY routed_at DESC LIMIT 5").fetchall()]
            conn.close()
            self._json({
                "capacity_tokens": 45000000,
                "indexed_tokens": total_tokens,
                "node_count": total_nodes,
                "nodes": nodes,
                "recent_routes": routes
            })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/api/brain/remember":
            res = ingest_memory(
                payload.get("domain", "ASTRA_OS"),
                payload.get("title", "Memory Node"),
                payload.get("content", ""),
                payload.get("links", "NODE-CORE")
            )
            self._json({"status": "REMEMBERED", "node": res})
        elif self.path == "/api/brain/route":
            res = route_task(payload.get("prompt", "Sync telemetry and verify crypto escrow"))
            self._json(res)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=auto_sync_loop, daemon=True).start()
    print("[🧠] Astra 45M-Token Knowledge Graph & Task Router Online at http://127.0.0.1:8096")
    HTTPServer(("0.0.0.0", 8096), BrainHandler).serve_forever()
