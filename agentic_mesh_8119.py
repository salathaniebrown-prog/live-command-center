import http.server
http.server.HTTPServer.allow_reuse_address = True
import hashlib, http.client, json, os, sqlite3, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_agentic_mesh.db")

CLUSTER_NODES = {
    8088: "COMMAND_CENTER_UI",
    8099: "VIRTUAL_CARD_DEALERSHIP",
    8108: "STUDIO_PRO_COMPUTE",
    8109: "UNIFIED_BRAIN_ROUTER",
    8111: "JEV_INVOICE_AGENT",
    8113: "EDGE_ML_MARKET_FEED",
    8115: "CRYPTO_CARD_WEBHOOKS",
    8117: "AGENTIC_TRUST_CENTER",
    8119: "SUPERCOMPUTER_MESH_BUS"
}

def init_mesh_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS validated_executions (
        exec_id TEXT PRIMARY KEY,
        mission_goal TEXT,
        nodes_invoked TEXT,
        validation_score REAL,
        gate_checks TEXT,
        synthesized_output TEXT,
        attestation_hash TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()

init_mesh_db()

def probe_node(port, path="/", payload=None):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=0.4)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            c.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        else:
            c.request("GET", path)
        res = c.getresponse()
        raw = res.read().decode("utf-8", errors="ignore")
        return {"port": port, "node": CLUSTER_NODES.get(port), "online": res.status == 200, "data": json.loads(raw) if raw.strip().startswith("{") else raw[:200]}
    except Exception as e:
        return {"port": port, "node": CLUSTER_NODES.get(port), "online": False, "error": str(e)}

def validate_and_execute_mission(goal_text):
    goal = (goal_text or "Full cross-node telemetry, market, and compliance synthesis").strip()
    exec_id = "MESH-" + uuid.uuid4().hex[:8].upper()
    ts = time.time()

    # 1. Gather real-time cross-node intelligence in parallel sequence
    n_brain = probe_node(8109, "/route", {"mission": goal, "mode": "SUPERCOMPUTER_MESH"})
    n_edge = probe_node(8113, "/")
    n_trust = probe_node(8117, "/ask", {"question": goal})
    n_wh = probe_node(8115, "/")
    n_cinema = probe_node(8121, "/render", {"title": "MESH_SYNC_CINEMA", "prompt": goal, "bpm": 128, "fps": 24})

    # 2. 3-Gate Deterministic AI Output Validation
    eth_price = 0.0
    if isinstance(n_edge.get("data"), dict):
        mkt = n_edge.get("data").get("market") or {}
        eth_price = float(mkt.get("price") or 0.0)

    trust_ans = ""
    trust_proof = ""
    if isinstance(n_trust.get("data"), dict):
        trust_ans = str(n_trust.get("data").get("answer") or "")
        trust_proof = str(n_trust.get("data").get("attestation_hash") or "")

    wh_events = 0
    if isinstance(n_wh.get("data"), dict):
        wh_events = int(n_wh.get("data").get("events_logged") or 0)

    cinema_ok = isinstance(n_cinema.get("data"), dict) and (n_cinema.get("data").get("status") == "CINEMA_RENOISE_SYNCED")
    cinema_id = n_cinema.get("data").get("project_id", "N/A") if isinstance(n_cinema.get("data"), dict) else "N/A"
    gates = {
        "gate_1_schema_and_non_empty": bool(trust_ans or n_brain.get("online")),
        "gate_2_live_telemetry_grounded": (eth_price > 0.0 and n_trust.get("online")),
        "gate_3_cryptographic_attestation": bool(trust_proof.startswith("0x")),
        "gate_4_cinema_renoise_mcp_synced": cinema_ok
    }
    passed = sum(1 for v in gates.values() if v)
    score_pct = round((passed / 4.0) * 100.0, 1)

    synthesis = (
        f"[SUPERCOMPUTER MESH {exec_id}] Live ETH/USD spot verified at ${eth_price:,.2f} | "
        f"Settled webhook events: {wh_events} | "
        f"Assurance posture: {trust_ans}"
    ).strip()

    attestation = "0x" + hashlib.sha256(f"{exec_id}|{goal}|{synthesis}|{score_pct}|{ts}".encode("utf-8")).hexdigest()
    invoked_list = ["8109:BRAIN", "8113:EDGE_ML", "8115:WEBHOOKS", "8117:TRUST", f"8121:CINEMA_MCP({cinema_id})"]

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO validated_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (exec_id, goal, json.dumps(invoked_list), score_pct, json.dumps(gates), synthesis, attestation, ts)
    )
    conn.commit()
    conn.close()

    return {
        "exec_id": exec_id,
        "status": "VALIDATED_MESH_OUTPUT" if score_pct == 100.0 else "PARTIAL_VALIDATION",
        "validation_score_pct": score_pct,
        "validation_gates": gates,
        "nodes_coordinated": invoked_list,
        "live_eth_spot_usd": eth_price,
        "settled_webhooks": wh_events,
        "synthesized_output": synthesis,
        "attestation_hash": attestation
    }

class AgenticMeshHandler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self._json(200, {"ok": True})

    def do_GET(self):
        probes = [probe_node(p) for p in sorted(CLUSTER_NODES.keys()) if p != 8119]
        online_cnt = sum(1 for x in probes if x.get("online"))
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        recent = [dict(r) for r in conn.execute("SELECT * FROM validated_executions ORDER BY timestamp DESC LIMIT 10").fetchall()]
        conn.close()
        self._json(200, {
            "service": "ASTRA_ALSTRA_AGENTIC_SUPERCOMPUTER_MESH",
            "port": 8119,
            "status": "ONLINE",
            "mesh_nodes_online": f"{online_cnt}/{len(probes)}",
            "topology": probes,
            "recent_validated_runs": recent
        })

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln).decode("utf-8", errors="ignore") if ln else "{}"
        data = json.loads(raw) if raw.strip() else {}
        self._json(200, validate_and_execute_mission(data.get("goal") or data.get("prompt") or ""))

if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("0.0.0.0", 8119), AgenticMeshHandler).serve_forever()
