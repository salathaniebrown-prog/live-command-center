import os
import json
import time
import sqlite3
import hashlib
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

HOME = os.path.expanduser("~")
BI_DB = os.path.join(HOME, "astra-bi-engine", "business_superintelligence.db")
DEALER_DB = os.path.join(HOME, "ai-studio-dealership", "dealership_ledger.db")
LEGAL_DB = os.path.join(HOME, "ai-studio-legal", "legal_doctrine.db")
BRAIN_DB = os.path.join(HOME, "astra-memory-brain", "astra_45m_brain.db")
OODA_DB = os.path.join(HOME, "astra-ooda-os", "infinite_brain_ooda.db")
REAL_LOG = os.path.join(HOME, "telemetry-spine", "REAL.log")

REFINED_SQL_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS refined_kpi_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    gross_fleet_volume_usd REAL,
    gross_fleet_volume_eth REAL,
    completed_orders INTEGER,
    available_inventory INTEGER,
    legal_audits_count INTEGER,
    ooda_cycles_count INTEGER,
    ooda_avg_confidence REAL,
    brain_indexed_tokens INTEGER,
    brain_node_count INTEGER,
    refinement_hash TEXT,
    generated_at REAL
);

CREATE TABLE IF NOT EXISTS unified_fact_ledger (
    fact_id TEXT PRIMARY KEY,
    domain TEXT,
    metric_key TEXT,
    metric_value REAL,
    unit TEXT,
    proof_hash TEXT,
    recorded_at REAL
);
"""

def refine_business_intelligence():
    conn = sqlite3.connect(BI_DB)
    conn.executescript(REFINED_SQL_SCHEMA)
    c = conn.cursor()

    # Attach live operational databases safely if present
    attached = []
    for alias, path in [("dlr", DEALER_DB), ("leg", LEGAL_DB), ("brn", BRAIN_DB), ("ooda", OODA_DB)]:
        if os.path.exists(path):
            c.execute(f"ATTACH DATABASE '{path}' AS {alias};")
            attached.append(alias)

    # 1. Cross-Database SQL Aggregation
    fleet_usd, fleet_eth, orders_cnt, avail_cnt = 0.0, 0.0, 0, 0
    if "dlr" in attached:
        row = c.execute("SELECT COALESCE(SUM(amount),0), COALESCE(SUM(amount_eth),0), COUNT(*) FROM dlr.orders").fetchone()
        fleet_usd, fleet_eth, orders_cnt = float(row[0]), float(row[1]), int(row[2])
        avail_cnt = int(c.execute("SELECT COUNT(*) FROM dlr.inventory WHERE status='AVAILABLE'").fetchone()[0])

    legal_cnt = 0
    if "leg" in attached:
        legal_cnt = int(c.execute("SELECT COUNT(*) FROM leg.audits").fetchone()[0])

    ooda_cnt, ooda_conf = 0, 0.0
    if "ooda" in attached:
        orow = c.execute("SELECT COUNT(*), COALESCE(AVG(confidence), 0.99) FROM ooda.ooda_cycles").fetchone()
        ooda_cnt, ooda_conf = int(orow[0]), round(float(orow[1]), 4)

    brain_tokens, brain_nodes = 0, 0
    graph_edges = []
    if "brn" in attached:
        brow = c.execute("SELECT COALESCE(SUM(token_est),0), COUNT(*) FROM brn.nodes").fetchone()
        brain_tokens, brain_nodes = int(brow[0]), int(brow[1])
        graph_edges = [
            {"node": r[0], "domain": r[1], "title": r[2], "links": r[3]}
            for r in c.execute("SELECT node_id, domain, title, links FROM brn.nodes ORDER BY updated_at DESC LIMIT 12").fetchall()
        ]

    # 2. Populate Refined Star-Schema Fact Table
    facts = [
        ("FACT-FLEET-USD", "REVENUE_&_FLEET", "gross_settled_usd", fleet_usd, "USD"),
        ("FACT-FLEET-ETH", "CRYPTO_TREASURY", "gross_settled_eth", fleet_eth, "ETH"),
        ("FACT-ORDERS-CNT", "OPERATIONS", "settled_vehicle_orders", float(orders_cnt), "COUNT"),
        ("FACT-INV-AVAIL", "SUPPLY_CHAIN", "available_fleet_units", float(avail_cnt), "UNITS"),
        ("FACT-LEGAL-AUD", "COMPLIANCE_SHIELD", "doctrine_audits_completed", float(legal_cnt), "AUDITS"),
        ("FACT-OODA-CONF", "AI_JUDGMENT", "avg_judgment_confidence", ooda_conf, "RATIO"),
        ("FACT-BRAIN-TOK", "INFINITE_MEMORY", "indexed_knowledge_tokens", float(brain_tokens), "TOKENS")
    ]
    now = time.time()
    for fid, dom, mkey, mval, unit in facts:
        phash = "0x" + hashlib.sha256(f"{fid}:{mval}:{now}".encode()).hexdigest()
        c.execute("INSERT OR REPLACE INTO unified_fact_ledger VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (fid, dom, mkey, mval, unit, phash, now))

    snap_id = "BI-" + hashlib.sha256(f"{fleet_usd}:{ooda_cnt}:{now}".encode()).hexdigest()[:6].upper()
    ref_hash = "0x" + hashlib.sha256(f"{snap_id}:{fleet_usd}:{fleet_eth}:{brain_tokens}".encode()).hexdigest()
    c.execute("INSERT INTO refined_kpi_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (snap_id, fleet_usd, fleet_eth, orders_cnt, avail_cnt, legal_cnt, ooda_cnt, ooda_conf, brain_tokens, brain_nodes, ref_hash, now))
    conn.commit()
    conn.close()

    # 3. Build Model-Agnostic AI Context Block (Works with ANY Open-Source or Frontier LLM)
    model_prompt_pack = (
        f"=== ASTRA BUSINESS SUPERINTELLIGENCE & KNOWLEDGE GRAPH CONTEXT ===\n"
        f"SNAPSHOT: {snap_id} | PROOF: {ref_hash}\n"
        f"[FINANCIAL & FLEET KPIs] Settled Volume: ${fleet_usd:,.2f} ({fleet_eth} ETH) | Completed Orders: {orders_cnt} | Available Units: {avail_cnt}\n"
        f"[GOVERNANCE & OODA] Legal Audits: {legal_cnt} | OODA Cycles: {ooda_cnt} (Avg Confidence: {ooda_conf*100:.1f}%)\n"
        f"[KNOWLEDGE GRAPH] Indexed Context: {brain_tokens:,} / 45,000,000 tokens across {brain_nodes} nodes\n"
        f"[ACTIVE GRAPH TOPOLOGY]\n" +
        "\n".join(f"  - {g['node']} [{g['domain']}]: {g['title']} -> links({g['links']})" for g in graph_edges) +
        "\n=== INSTRUCTION: Analyze these live metrics, identify highest-ROI next actions, and enforce UCC/Escrow asset protection. ==="
    )

    # 4. Feed refined BI snapshot back into Infinite Brain & REAL.log
    try:
        req = urllib.request.Request(
            "http://127.0.0",
            data=json.dumps({
                "domain": "BUSINESS_INTEL",
                "title": f"BI Snapshot {snap_id} (${fleet_usd:,.0f})",
                "content": model_prompt_pack,
                "links": "NODE-CORE,NODE-CRYPTO,NODE-LEGAL,NODE-FLEET,NODE-INFRA"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass

    try:
        os.makedirs(os.path.dirname(REAL_LOG), exist_ok=True)
        with open(REAL_LOG, "a", encoding="utf-8") as lf:
            lf.write(json.dumps({
                "ts": now, "source": "BI_SUPERINTELLIGENCE",
                "snapshot_id": snap_id, "gross_usd": fleet_usd, "gross_eth": fleet_eth, "proof": ref_hash
            }) + "\n")
    except Exception:
        pass

    return {
        "snapshot_id": snap_id,
        "kpis": {
            "gross_fleet_volume_usd": fleet_usd,
            "gross_fleet_volume_eth": fleet_eth,
            "completed_orders": orders_cnt,
            "available_inventory": avail_cnt,
            "legal_audits_count": legal_cnt,
            "ooda_cycles_count": ooda_cnt,
            "ooda_avg_confidence": ooda_conf,
            "brain_indexed_tokens": brain_tokens,
            "brain_node_count": brain_nodes
        },
        "graph_edges": graph_edges,
        "model_context_pack": model_prompt_pack,
        "refinement_hash": ref_hash
    }

class BIHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/bi/refine" or self.path == "/api/bi/model-context":
            self._json(refine_business_intelligence())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/api/bi/sql":
            # Read-only custom SQL analytics runner over unified BI warehouse
            query = payload.get("sql", "SELECT * FROM unified_fact_ledger").strip()
            if not query.lower().startswith("select"):
                return self._json({"error": "Only SELECT analytical queries permitted"}, 400)
            conn = sqlite3.connect(BI_DB)
            conn.row_factory = sqlite3.Row
            for alias, path in [("dlr", DEALER_DB), ("leg", LEGAL_DB), ("brn", BRAIN_DB), ("ooda", OODA_DB)]:
                if os.path.exists(path):
                    conn.execute(f"ATTACH DATABASE '{path}' AS {alias};")
            rows = [dict(r) for r in conn.execute(query).fetchall()]
            conn.close()
            self._json({"status": "OK", "row_count": len(rows), "rows": rows})

if __name__ == "__main__":
    refine_business_intelligence()
    print("[📊] Business Superintelligence SQL Engine Online at http://127.0.0.1:8098")
    HTTPServer(("0.0.0.0", 8098), BIHandler).serve_forever()
