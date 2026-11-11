import os
import sqlite3
import json
import time
import uuid
import hashlib
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dealership_ledger.db")
DEEPSPACE_DB = os.path.expanduser("~/astra_deepspace_ledger.db")
HTML_PATH = os.path.join(BASE_DIR, "index.html")

_RATE_CACHE = {"eth_usd": 3250.00, "ts": 0}

def get_live_eth_price():
    now = time.time()
    if now - _RATE_CACHE["ts"] < 60:
        return _RATE_CACHE["eth_usd"]
    try:
        req = urllib.request.Request(
            "https://coinbase.com",
            headers={"User-Agent": "AI-Studio-Dealership/1.0"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            price = float(data["data"]["amount"])
            _RATE_CACHE["eth_usd"] = price
            _RATE_CACHE["ts"] = now
            return price
    except Exception:
        return _RATE_CACHE["eth_usd"]

def sync_deepspace(order_id, vehicle_id, rail, payment_ref, tx_hash, amount_usd, amount_eth, stage):
    try:
        conn = sqlite3.connect(DEEPSPACE_DB)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS wyler_crypto_ledger (
                        order_id TEXT PRIMARY KEY,
                        vehicle_id TEXT,
                        rail TEXT,
                        payment_ref TEXT,
                        tx_hash TEXT,
                        amount REAL,
                        amount_eth REAL,
                        stage TEXT,
                        synced_at REAL
                    )''')
        cols = [r[1] for r in c.execute("PRAGMA table_info(wyler_crypto_ledger)").fetchall()]
        if "amount_eth" not in cols:
            c.execute("ALTER TABLE wyler_crypto_ledger ADD COLUMN amount_eth REAL DEFAULT 0")
        c.execute('''INSERT OR REPLACE INTO wyler_crypto_ledger
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (order_id, vehicle_id, rail, payment_ref, tx_hash, amount_usd, amount_eth, stage, time.time()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] Deepspace sync deferred: {e}")
    try:
        real_log = os.path.expanduser("~/telemetry-spine/REAL.log")
        os.makedirs(os.path.dirname(real_log), exist_ok=True)
        event = {
            "ts": time.time(),
            "source": "WYLER_CRYPTO_DEALERSHIP",
            "order_id": order_id,
            "vehicle_id": vehicle_id,
            "rail": rail,
            "amount_usd": amount_usd,
            "amount_eth": amount_eth,
            "stage": stage,
            "tx_hash": tx_hash
        }
        with open(real_log, "a", encoding="utf-8") as lf:
            lf.write(json.dumps(event) + "\n")
    except Exception as le:
        print(f"[WARN] REAL.log stream deferred: {le}")
    try:
        wf_url = os.getenv("LANGFLOW_WEBHOOK_URL", "").strip()
        if not wf_url:
            sconn = sqlite3.connect(DB_PATH)
            srow = sconn.execute("SELECT v FROM settings WHERE k='webhook_url'").fetchone()
            sconn.close()
            wf_url = srow[0].strip() if srow else ""
        if wf_url:
            wreq = urllib.request.Request(
                wf_url,
                data=json.dumps({"event": "WYLER_DEALERSHIP_EVENT", "order_id": order_id, "vehicle_id": vehicle_id, "amount_usd": amount_usd, "amount_eth": amount_eth, "stage": stage, "tx_hash": tx_hash}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(wreq, timeout=3)
    except Exception as we:
        print(f"[WARN] Webhook forward deferred: {we}")



def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    id TEXT PRIMARY KEY,
                    dealer TEXT,
                    model TEXT,
                    vin TEXT,
                    price REAL,
                    status TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    vehicle_id TEXT,
                    rail TEXT,
                    payment_ref TEXT,
                    tx_hash TEXT,
                    amount REAL,
                    amount_eth REAL,
                    stage TEXT,
                    updated_at REAL
                )''')

    cols = [r[1] for r in c.execute("PRAGMA table_info(orders)").fetchall()]
    if "amount_eth" not in cols:
        c.execute("DROP TABLE IF EXISTS inventory")
        c.execute("DROP TABLE IF EXISTS orders")
        conn.close()
        return init_db()

    c.execute("SELECT COUNT(*) FROM inventory")
    if c.fetchone()[0] == 0:
        vehicles = [
            ("WYL-01", "WYLER AUTO", "GMC Hummer EV 3X", "1GT49REY5NU100421", 98500.00, "AVAILABLE"),
            ("WYL-02", "WYLER AUTO", "Chevrolet Corvette Z06", "1G1YF2D74P5108932", 114900.00, "AVAILABLE"),
            ("WYL-03", "WYLER AUTO", "Cadillac Escalade-V", "1GYS4GKL9PR204118", 152000.00, "AVAILABLE"),
            ("DLK-04", "DEALERSLINK", "Tesla Model S Plaid", "5YJSA1E28NF192761", 89990.00, "AVAILABLE"),
            ("DLK-05", "DEALERSLINK", "Audi RS e-tron GT", "WA1AAAGE8NA008912", 104900.00, "AVAILABLE")
        ]
        c.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)", vehicles)
    c.execute("CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)")
    conn.commit()
    conn.close()

class DealershipHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/":
            with open(HTML_PATH, "rb") as f:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f.read())
        elif self.path.startswith("/api/receipt/"):
            order_id = self.path.split("/api/receipt/", 1)[1].strip()
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            order = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
            if not order:
                conn.close()
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Order not found")
                return
            vids = order["vehicle_id"].split("+")
            placeholders = ",".join("?" for _ in vids)
            vehs = conn.execute(f"SELECT id, dealer, model, vin, price FROM inventory WHERE id IN ({placeholders})", vids).fetchall()
            conn.close()

            veh_rows = "".join(
                f"<tr><td>{v['id']}</td><td>{v['dealer']}</td><td>{v['model']}</td><td>{v['vin']}</td><td>${v['price']:,.2f}</td></tr>"
                for v in vehs
            )
            ts_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(order["updated_at"]))
            html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Bill of Sale & Crypto Certificate // {order['order_id']}</title>
<style>
  body {{ font-family: 'Courier New', monospace; background: #04090f; color: #e2f8ff; padding: 24px; }}
  .cert {{ max-width: 820px; margin: 0 auto; border: 2px solid #00f0ff; background: #07131f; padding: 28px; box-shadow: 0 0 25px #00f0ff33; }}
  .hdr {{ display: flex; justify-content: space-between; border-bottom: 1px solid #00f0ff55; padding-bottom: 12px; margin-bottom: 18px; }}
  h1 {{ font-size: 18px; color: #39ff14; margin: 0; letter-spacing: 1.5px; }}
  .stamp {{ border: 2px solid #39ff14; color: #39ff14; padding: 4px 10px; font-weight: bold; font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
  th, td {{ border: 1px solid #00f0ff44; padding: 8px; text-align: left; }}
  th {{ background: #0b2033; color: #00f0ff; }}
  .hash-box {{ background: #03080d; border: 1px solid #39ff1466; padding: 12px; word-break: break-all; font-size: 12px; color: #39ff14; margin-top: 12px; }}
  .btn {{ margin-top: 18px; padding: 10px 18px; background: #00f0ff22; border: 1px solid #00f0ff; color: #00f0ff; font-family: inherit; font-weight: bold; cursor: pointer; }}
  @media print {{ .btn {{ display: none; }} body {{ background: #fff; color: #000; }} .cert {{ border-color: #000; background: #fff; box-shadow: none; }} th, td {{ border-color: #000; }} .hash-box {{ border-color: #000; color: #000; background: #f4f4f4; }} }}
</style>
</head>
<body>
<div class="cert">
  <div class="hdr">
    <div>
      <h1>OFFICIAL VEHICLE BILL OF SALE & CRYPTO RECEIPT</h1>
      <div style="font-size:12px; color:#8ad8ff; margin-top:4px;">AI STUDIO COMMAND CENTER // DEALERSHIP SETTLEMENT NODE</div>
    </div>
    <div class="stamp">{order['stage']}</div>
  </div>
  <div style="font-size:13px; line-height:1.7;">
    <strong>ORDER / BATCH ID:</strong> {order['order_id']}<br>
    <strong>SETTLEMENT RAIL:</strong> {order['rail']}<br>
    <strong>BUYER ACCOUNT / WALLET:</strong> {order['payment_ref']}<br>
    <strong>TIMESTAMP:</strong> {ts_str}<br>
    <strong>TOTAL SETTLED:</strong> ${order['amount']:,.2f} USD ({order['amount_eth']} ETH)
  </div>
  <table>
    <thead><tr><th>UNIT ID</th><th>DEALERSHIP</th><th>VEHICLE MODEL</th><th>VIN</th><th>SETTLEMENT PRICE</th></tr></thead>
    <tbody>{veh_rows}</tbody>
  </table>
  <div class="hash-box">
    <strong>CRYPTOGRAPHIC SETTLEMENT HASH (SHA-256):</strong><br>{order['tx_hash']}
  </div>
  <button class="btn" onclick="window.print()">PRINT / SAVE AS PDF CERTIFICATE</button>
</div>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html_doc.encode("utf-8"))
            return

        elif self.path == "/api/state":
            eth_usd = get_live_eth_price()
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            inv = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
            for item in inv:
                item["price_eth"] = round(item["price"] / eth_usd, 4)
            ords = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY updated_at DESC").fetchall()]
            conn.close()
            self._send_json({"eth_usd": eth_usd, "inventory": inv, "orders": ords})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/acquire":
            veh_id = payload.get("vehicle_id")
            rail = payload.get("rail", "CRYPTO_ESCROW")
            payment_ref = payload.get("payment_ref", "0x5f04EBB30d3BBf356263c3ef4823080d05bEDDf5")

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT price, status FROM inventory WHERE id=?", (veh_id,))
            row = c.fetchone()
            if not row or row[1] != "AVAILABLE":
                conn.close()
                return self._send_json({"error": "Vehicle unavailable"}, 400)

            price_usd = row[0]
            eth_usd = get_live_eth_price()
            price_eth = round(price_usd / eth_usd, 4)
            order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
            raw_sig = f"{order_id}:{veh_id}:{payment_ref}:{price_usd}:{price_eth}:{time.time()}".encode()
            tx_hash = "0x" + hashlib.sha256(raw_sig).hexdigest()

            initial_stage = "CRYPTO_TX_CONFIRMED" if rail == "CRYPTO_ESCROW" else "VCARD_AUTHORIZED"
            c.execute("UPDATE inventory SET status='ACQUIRED' WHERE id=?", (veh_id,))
            c.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (order_id, veh_id, rail, payment_ref, tx_hash, price_usd, price_eth, initial_stage, time.time()))
            conn.commit()
            conn.close()

            sync_deepspace(order_id, veh_id, rail, payment_ref, tx_hash, price_usd, price_eth, initial_stage)
            self._send_json({"status": "SUCCESS", "order_id": order_id, "tx_hash": tx_hash, "amount_eth": price_eth, "stage": initial_stage})

        elif self.path == "/api/add_vehicle":
            dealer = payload.get("dealer", "WYLER AUTO").upper()
            model = payload.get("model", "Custom Fleet Unit")
            vin = payload.get("vin", "1G1CUSTOM00000001").upper()
            price = float(payload.get("price", 75000.00))
            veh_id = f"{dealer[:3]}-{uuid.uuid4().hex[:3].upper()}"
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)", (veh_id, dealer, model, vin, price, "AVAILABLE"))
            conn.commit()
            conn.close()
            self._send_json({"status": "ADDED", "id": veh_id, "model": model})

        elif self.path == "/api/acquire_batch":
            veh_ids = payload.get("vehicle_ids", [])
            rail = payload.get("rail", "CRYPTO_ESCROW")
            payment_ref = payload.get("payment_ref", "0x5f04EBB30d3BBf356263c3ef4823080d05bEDDf5")
            if not veh_ids:
                return self._send_json({"error": "No vehicles selected"}, 400)

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            total_usd = 0.0
            valid_ids = []
            for vid in veh_ids:
                row = c.execute("SELECT price, status FROM inventory WHERE id=?", (vid,)).fetchone()
                if row and row[1] == "AVAILABLE":
                    total_usd += float(row[0])
                    valid_ids.append(vid)

            if not valid_ids:
                conn.close()
                return self._send_json({"error": "Selected vehicles unavailable"}, 400)

            eth_usd = get_live_eth_price()
            total_eth = round(total_usd / eth_usd, 4)
            batch_id = f"BATCH-{uuid.uuid4().hex[:5].upper()}"
            joined_vids = "+".join(valid_ids)
            raw_sig = f"{batch_id}:{joined_vids}:{payment_ref}:{total_usd}:{total_eth}:{time.time()}".encode()
            tx_hash = "0x" + hashlib.sha256(raw_sig).hexdigest()
            initial_stage = "CRYPTO_TX_CONFIRMED" if rail == "CRYPTO_ESCROW" else "VCARD_AUTHORIZED"

            for vid in valid_ids:
                c.execute("UPDATE inventory SET status='ACQUIRED' WHERE id=?", (vid,))
            c.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (batch_id, joined_vids, rail, payment_ref, tx_hash, total_usd, total_eth, initial_stage, time.time()))
            conn.commit()
            conn.close()

            sync_deepspace(batch_id, joined_vids, rail, payment_ref, tx_hash, total_usd, total_eth, initial_stage)
            self._send_json({"status": "SUCCESS", "order_id": batch_id, "vehicles": valid_ids, "amount_usd": total_usd, "amount_eth": total_eth, "tx_hash": tx_hash})

        elif self.path == "/api/set_webhook":
            url = payload.get("webhook_url", "").strip()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('webhook_url', ?)", (url,))
            conn.commit()
            conn.close()
            self._send_json({"status": "WEBHOOK_SAVED", "webhook_url": url})

        elif self.path == "/api/reset":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE inventory SET status='AVAILABLE'")
            c.execute("DELETE FROM orders")
            conn.commit()
            conn.close()
            self._send_json({"status": "RESET_COMPLETE"})

        elif self.path == "/api/advance":
            order_id = payload.get("order_id")
            next_stage = payload.get("stage")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE orders SET stage=?, updated_at=? WHERE order_id=?",
                      (next_stage, time.time(), order_id))
            c.execute("SELECT vehicle_id, rail, payment_ref, tx_hash, amount, amount_eth FROM orders WHERE order_id=?", (order_id,))
            row = c.fetchone()
            conn.commit()
            conn.close()

            if row:
                sync_deepspace(order_id, row[0], row[1], row[2], row[3], row[4], row[5], next_stage)
            self._send_json({"status": "UPDATED", "order_id": order_id, "stage": next_stage})

if __name__ == "__main__":
    init_db()
    print("[⚡] Wyler Live ETH/USDC Dealership Engine Online at http://127.0.0.1:8099")
    HTTPServer(("0.0.0.0", 8099), DealershipHandler).serve_forever()
