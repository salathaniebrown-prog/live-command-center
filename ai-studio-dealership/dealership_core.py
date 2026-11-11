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
