import os
import time
import hmac
import hashlib
import sqlite3
import asyncio
from aiohttp import web, ClientSession

WEBHOOK_SECRET = os.environ.get("ASTRA_WEBHOOK_SECRET", "change_me_in_env").encode()
MAIN_TELEMETRY_PUSH = "http://127.0.0.1:8099/api/ingest"
DB_PATH = "astra_webhooks.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                chain TEXT,
                tx_hash TEXT,
                payload TEXT,
                verified_at REAL
            )
        """)

def verify_hmac(raw_body: bytes, signature_header: str, timestamp_header: str, tolerance: int = 300) -> bool:
    if not signature_header or not timestamp_header:
        return False
    try:
        if abs(time.time() - float(timestamp_header)) > tolerance:
            return False
    except ValueError:
        return False

    signed_payload = f"{timestamp_header}.".encode() + raw_body
    expected_sig = hmac.new(WEBHOOK_SECRET, signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, signature_header.replace("sha256=", ""))

async def handle_webhook(request: web.Request) -> web.Response:
    raw_body = await request.read()
    sig = request.headers.get("X-Hub-Signature-256", "")
    ts = request.headers.get("X-Webhook-Timestamp", "")

    if not verify_hmac(raw_body, sig, ts):
        return web.json_response({"error": "Invalid signature or stale timestamp"}, status=401)

    data = await request.json()
    chain = data.get("chain", "base-mainnet")
    tx_hash = data.get("tx_hash", "N/A")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO webhook_events (source, chain, tx_hash, payload, verified_at) VALUES (?, ?, ?, ?, ?)",
            (data.get("source", "webhook"), chain, tx_hash, raw_body.decode("utf-8", errors="ignore"), time.time())
        )

    asyncio.create_task(push_to_spine({"node": "8115", "type": "crypto_webhook", "chain": chain, "tx": tx_hash}))
    return web.json_response({"status": "verified", "tx_hash": tx_hash})

async def push_to_spine(event: dict):
    try:
        async with ClientSession() as session:
            await session.post(MAIN_TELEMETRY_PUSH, json=event, timeout=2)
    except Exception:
        pass

async def serve_ui(request: web.Request) -> web.Response:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, chain, tx_hash, verified_at FROM webhook_events ORDER BY id DESC LIMIT 20").fetchall()
    items = "".join(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{time.strftime('%H:%M:%S', time.localtime(r[3]))}</td></tr>" for r in rows)
    html = f"""
    <html><body style="background:#0d1117;color:#c9d1d9;font-family:monospace;padding:20px;">
    <h2>ASTRA // PORT 8115 CRYPTO & HMAC TELEMETRY</h2>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%;">
    <tr><th>ID</th><th>Chain</th><th>TX / Event Hash</th><th>Verified (UTC)</th></tr>{items}
    </table></body></html>
    """
    return web.Response(text=html, content_type="text/html")

app = web.Application()
app.router.add_post("/webhook", handle_webhook)
app.router.add_get("/", serve_ui)

if __name__ == "__main__":
    init_db()
    web.run_app(app, host="127.0.0.1", port=8115)
