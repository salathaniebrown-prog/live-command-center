import hashlib
import hmac
import http.client
import json
import os
import py_compile
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_PATH = os.path.expanduser("~/astra_webhook_ledger.db")
WEBHOOK_SECRET = os.environ.get("ASTRA_WEBHOOK_SECRET", "astra_sovereign_hmac_key_2026")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS webhook_events (
        event_id TEXT PRIMARY KEY,
        source_rail TEXT,
        event_type TEXT,
        order_ref TEXT,
        vin TEXT,
        amount_usd REAL,
        signature_valid INTEGER,
        invoice_forwarded INTEGER,
        raw_payload TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()

init_db()

def verify_hmac_signature(raw_bytes, signature_header):
    if not signature_header:
        return False
    cleaned = signature_header.replace("sha256=", "").strip()
    expected = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, cleaned)

def forward_to_invoice_8111(order_ref, vin, amount_usd, rail):
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 8111, timeout=5)
        body = json.dumps({
            "order_ref": order_ref,
            "vin": vin,
            "amount_usd": amount_usd,
            "settlement_rail": rail
        })
        conn.request("POST", "/invoice", body=body, headers={"Content-Type": "application/json"})
        res = conn.getresponse()
        return 1 if res.status == 200 else 0
    except Exception:
        return 0

class WebhookListenerHandler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Astra-Signature, X-CC-Webhook-Signature, Stripe-Signature")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM webhook_events ORDER BY timestamp DESC LIMIT 20").fetchall()]
        conn.close()
        self._send_json(200, {
            "service": "ASTRA_CRYPTO_VIRTUAL_CARD_WEBHOOK_LISTENER",
            "port": 8115,
            "status": "LISTENING",
            "events_logged": len(rows),
            "recent_events": rows
        })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_bytes = self.rfile.read(length) if length else b"{}"
        raw_text = raw_bytes.decode("utf-8", errors="ignore")

        sig_header = (
            self.headers.get("X-Astra-Signature")
            or self.headers.get("X-CC-Webhook-Signature")
            or self.headers.get("Stripe-Signature")
            or ""
        )
        sig_valid = 1 if verify_hmac_signature(raw_bytes, sig_header) else 0

        try:
            data = json.loads(raw_text)
        except Exception:
            self._send_json(400, {"error": "INVALID_JSON_PAYLOAD"})
            return

        event_id = data.get("id") or ("WH-" + uuid.uuid4().hex[:10].upper())
        rail = data.get("rail", "VIRTUAL_CARD_CRYPTO_SETTLEMENT")
        event_type = data.get("type", "authorization.settled")
        order_ref = data.get("order_ref", "ORD-" + uuid.uuid4().hex[:6].upper())
        vin = data.get("vin", "5YJSA1E28NF192761")
        amount = float(data.get("amount_usd", 88500.00))

        forwarded = forward_to_invoice_8111(order_ref, vin, amount, rail)

        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO webhook_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, rail, event_type, order_ref, vin, amount, sig_valid, forwarded, raw_text, time.time())
        )
        conn.commit()
        conn.close()

        self._send_json(200, {
            "status": "WEBHOOK_ACCEPTED",
            "event_id": event_id,
            "event_type": event_type,
            "order_ref": order_ref,
            "vin": vin,
            "amount_usd": amount,
            "hmac_verified": bool(sig_valid),
            "forwarded_to_jev_8111": bool(forwarded)
        })

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8115), WebhookListenerHandler).serve_forever()
