import hashlib
import json
import os
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_PATH = os.path.expanduser("~/astra_invoice_ledger.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS invoices (
        invoice_id TEXT PRIMARY KEY,
        order_ref TEXT,
        vehicle_vin TEXT,
        amount_usd REAL,
        settlement_rail TEXT,
        receipt_hash TEXT,
        status TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()

init_db()

class InvoiceRouterHandler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM invoices ORDER BY timestamp DESC LIMIT 20").fetchall()]
        conn.close()
        self._send_json(200, {
            "service": "JEV_SYSTEM_ONE_INVOICE_AGENT",
            "port": 8111,
            "status": "ONLINE",
            "invoices_count": len(rows),
            "recent_invoices": rows
        })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(raw)

        inv_id = "INV-" + uuid.uuid4().hex[:8].upper()
        order_ref = data.get("order_ref", "ORD-" + uuid.uuid4().hex[:6].upper())
        vin = data.get("vin", "WAIAAAUF85PN008912")
        amount = float(data.get("amount_usd", 104900.00))
        rail = data.get("settlement_rail", "VIRTUAL_CARD_CRYPTO_ESCROW")
        ts = time.time()

        sig_payload = f"{inv_id}|{order_ref}|{vin}|{amount}|{rail}|{ts}".encode("utf-8")
        receipt_hash = "0x" + hashlib.sha256(sig_payload).hexdigest()

        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (inv_id, order_ref, vin, amount, rail, receipt_hash, "VERIFIED_SETTLED", ts)
        )
        conn.commit()
        conn.close()

        self._send_json(200, {
            "status": "INVOICE_GENERATED",
            "invoice_id": inv_id,
            "order_ref": order_ref,
            "vin": vin,
            "amount_usd": amount,
            "settlement_rail": rail,
            "sha256_certificate": receipt_hash,
            "ledger_persisted": True
        })

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8111), InvoiceRouterHandler).serve_forever()
