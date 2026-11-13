import http.client, json, os, sqlite3, subprocess, time

HOME = os.path.expanduser("~")
PORTS = {
    8088: "dashboard_server.py (Command Center UI, Top KPI Bar, CI Modal, 3D CGI Voice Core, 1-Click Pipeline)",
    8099: "dealership_module.py (Virtual Card Dealership & Escrow Fleet UI)",
    8108: "compute_router_8108_8109.py (Studio Pro Engine)",
    8109: "compute_router_8108_8109.py (Auto-Astra Highest Brain Model Router)",
    8111: "invoice_agent_8111.py (JEV Primary Intent Router & SHA-256 Invoice Agent)",
    8113: "mediapipe_edge_ml.py (Edge ML & Live ETH/USD Spot Feed)",
    8115: "webhook_listener_8115.py (Multi-Chain Crypto & Virtual Card HMAC Webhook Listener)"
}

def check_port(port):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=1.5)
        c.request("GET", "/")
        return "ONLINE" if c.getresponse().status == 200 else "DEGRADED"
    except Exception:
        return "OFFLINE"

def count_rows(db_name, table_name):
    p = os.path.join(HOME, db_name)
    if not os.path.exists(p):
        return 0
    try:
        conn = sqlite3.connect(p)
        row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        conn.close()
        return int(next(iter(row), 0)) if isinstance(row, (tuple, list)) else int(row or 0)
    except Exception:
        return 0

try:
    git_sha = subprocess.check_output(["git", "-C", HOME, "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
except Exception:
    git_sha = "unknown"

tlog = os.path.join(HOME, "tunnel.log")
tunnel_live = os.path.exists(tlog) and ("Registered tunnel connection" in open(tlog, errors="ignore").read())

port_lines = [f"- Port {p}: {status} -> {desc}" for p, desc in PORTS.items() for status in [check_port(p)]]
wh_count = count_rows("astra_webhook_ledger.db", "webhook_events")
inv_count = count_rows("astra_invoice_ledger.db", "invoices")
deal_count = count_rows("astra_dealership_ledger.db", "deals")

handoff_text = f"""=== ASTRA LIVE COMMAND CENTER // INCREMENTAL UPGRADE HANDOFF ===
STRICT EXECUTION DIRECTIVE:
1. DO NOT REBUILD, OVERWRITE, OR RECREATE EXISTING FILES FROM SCRATCH.
2. ONLY ADD NEW FUNCTIONS/ROUTES OR PATCH/UPDATE EXISTING MODULES IN-PLACE.
3. ALL SCRIPTS MUST BE CLIPBOARD-SAFE FOR ANDROID TERMUX (NO SQUARE-BRACKET REGEX OR UNESCAPED INDEXERS).
4. VERIFY SYNTAX WITH py_compile AND COMMIT/PUSH INCREMENTAL CHANGES TO origin/main.

ACTIVE REPOSITORY & ENVIRONMENT:
- GitHub Repo: salathaniebrown-prog/live-command-center (branch: main, HEAD: {git_sha})
- Runtime: Android Termux ($HOME = {HOME})
- Named Cloudflare Tunnel: astra-command-center (38457208-da93-4484-b0bc-74eb05b3dbc6) -> {"CONNECTED" if tunnel_live else "STANDBY"}
- Watchdog Daemon: $HOME/astra-unified-brain/auto_correct_brain.py (30s port, tunnel & post-push CI guard)
- CI Workflow: .github/workflows/ci-verify.yml (py_compile + secret hygiene check)

LIVE 7-PORT CLUSTER ARCHITECTURE:
{chr(10).join(port_lines)}

PERSISTENT SQLITE LEDGERS (DO NOT DROP OR RESET):
- ~/astra_webhook_ledger.db (webhook_events: {wh_count} settled HMAC records)
- ~/astra_invoice_ledger.db (invoices: {inv_count} persisted SHA-256 receipts)
- ~/astra_dealership_ledger.db (deals: {deal_count} vehicle acquisitions)

CURRENT REQUEST (UPGRADE / ADD ONLY):
[Describe the exact feature or patch to add here]
=================================================================="""

manifest_path = os.path.join(HOME, "ASTRA_STATE_MANIFEST.md")
with open(manifest_path, "w", encoding="utf-8") as f:
    f.write(handoff_text + "\n")

print(handoff_text)
