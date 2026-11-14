import json, os, random, sqlite3, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_PATH = os.path.expanduser("~/astra_dealership_ledger.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS inventory (
        vin TEXT PRIMARY KEY,
        year INTEGER,
        make TEXT,
        model TEXT,
        trim TEXT,
        price REAL,
        market_value REAL,
        status TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS deals (
        deal_id TEXT PRIMARY KEY,
        vin TEXT,
        virtual_card_number TEXT,
        card_cvv TEXT,
        card_exp TEXT,
        authorized_limit REAL,
        stage TEXT,
        delivery_eta TEXT,
        timestamp REAL
    )""")
    cnt = c.execute("SELECT COUNT(*) FROM inventory").fetchone()
    n = int(next(iter(cnt), 0)) if isinstance(cnt, (tuple, list)) else int(cnt or 0)
    if n == 0:
        vehicles = [
            ("5YJSA1E28NF192761", 2025, "Tesla", "Model S", "Plaid Tri-Motor", 88500.00, 92000.00, "AVAILABLE"),
            ("1GT49REY5NU104829", 2026, "GMC", "Hummer EV", "Edition 1 SUV", 104200.00, 108500.00, "AVAILABLE"),
            ("WAUZZZF85PN009123", 2025, "Audi", "S8", "Quattro Executive", 118900.00, 123000.00, "AVAILABLE"),
        ]
        c.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?)", vehicles)
    conn.commit()
    conn.close()

init_db()

HTML_UI = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ALSTRA // VIRTUAL CARD DEALERSHIP (8099)</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: monospace; }
  body { background: #05080f; color: #00f0ff; padding: 12px; font-size: 12px; }
  .hdr { display: flex; justify-content: space-between; border-bottom: 1px solid #00f0ff44; padding-bottom: 6px; margin-bottom: 10px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .box { border: 1px solid #00f0ff44; background: #0a1220; padding: 10px; }
  .item { border: 1px solid #00f0ff33; padding: 8px; margin-bottom: 8px; }
  button { width: 100%; margin-top: 6px; padding: 7px; background: #00f0ff22; border: 1px solid #00f0ff; color: #00f0ff; font-weight: bold; cursor: pointer; }
  button:hover { background: #00f0ff; color: #05080f; }
  button:disabled { border-color: #555; color: #555; background: transparent; cursor: not-allowed; }
  .vc { border: 1px solid #00ff88; background: #0f2027; padding: 10px; color: #fff; margin-bottom: 8px; }
</style>
</head>
<body>
  <div class="hdr">
    <strong>DEALERSLINK // VIRTUAL CARD ACQUISITION (PORT 8099)</strong>
    <span style="color:#00ff88;">LEDGER: ONLINE</span>
  </div>
  <div class="grid">
    <div class="box">
      <div style="color:#fff;margin-bottom:6px;"><strong>01 // LIVE FLEET INVENTORY</strong></div>
      <div id="inv"></div>
    </div>
    <div class="box">
      <div style="color:#fff;margin-bottom:6px;"><strong>02 // ESCROW CARD & DISPATCH</strong></div>
      <div class="vc">
        <div style="color:#00ff88;font-size:10px;">SINGLE-USE ESCROW VIRTUAL CARD</div>
        <div id="vc-num" style="font-size:15px;margin:8px 0;letter-spacing:2px;">4532 •••• •••• ••••</div>
        <div style="display:flex;justify-content:space-between;font-size:11px;">
          <span>EXP: <strong id="vc-exp">--/--</strong></span>
          <span>CVV: <strong id="vc-cvv">---</strong></span>
          <span>LIMIT: <strong id="vc-lim">$0</strong></span>
        </div>
      </div>
      <div id="deals"></div>
    </div>
  </div>
<script>
async function refreshDealership() {
  const r = await fetch("./api/state");
  const d = await r.json();
  const inv = document.getElementById("inv");
  inv.innerHTML = "";
  (d.inventory || []).forEach(v => {
    const ok = v.status === "AVAILABLE";
    inv.innerHTML += `<div class="item">
      <div style="display:flex;justify-content:space-between;color:#fff;"><strong>${v.year} ${v.make} ${v.model}</strong><span style="color:#00ff88;">$${Number(v.price).toLocaleString()}</span></div>
      <div style="font-size:10px;color:#8899aa;">VIN: ${v.vin}</div>
      <button onclick="acquire('${v.vin}')" ${ok ? "" : "disabled"}>${ok ? "MINT VIRTUAL CARD & ACQUIRE" : "ACQUIRED // ENCLOSED CARRIER"}</button>
    </div>`;
  });
  const deals = document.getElementById("deals");
  deals.innerHTML = "";
  (d.deals || []).slice(0, 3).forEach(x => {
    deals.innerHTML += `<div class="item" style="border-color:#00ff88;">
      <strong style="color:#00ff88;">${x.deal_id}</strong> | VIN: ${x.vin}<br>
      <span style="font-size:10px;">CARD: ${x.virtual_card_number} ($${Number(x.authorized_limit).toLocaleString()})</span>
    </div>`;
  });
}
async function acquire(vin) {
  const r = await fetch("./api/execute", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({vin})});
  const res = await r.json();
  if (res.status === "SUCCESS") {
    document.getElementById("vc-num").innerText = res.virtual_card;
    document.getElementById("vc-exp").innerText = res.exp;
    document.getElementById("vc-cvv").innerText = res.cvv;
    document.getElementById("vc-lim").innerText = "$" + Number(res.authorized_limit).toLocaleString();
    refreshDealership();
  }
}
refreshDealership();
</script>
</body>
</html>"""

class DealershipHandler(BaseHTTPRequestHandler):
    def _send(self, code, content_type, body_bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        if self.path == "/api/state":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            inv = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
            deals = [dict(r) for r in conn.execute("SELECT * FROM deals ORDER BY timestamp DESC").fetchall()]
            conn.close()
            self._send(200, "application/json", json.dumps({"inventory": inv, "deals": deals}).encode("utf-8"))
            return
        self._send(200, "text/html; charset=utf-8", HTML_UI.encode("utf-8"))

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(ln).decode("utf-8")) if ln else {}
        vin = str(data.get("vin") or "").strip()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM inventory WHERE vin = ?", (vin,)).fetchone()
        if not row:
            conn.close()
            self._send(400, "application/json", json.dumps({"error": "VIN_NOT_FOUND"}).encode("utf-8"))
            return
        deal_id = "DL-" + uuid.uuid4().hex[:8].upper()
        vcard = f"4532 {random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
        cvv = str(random.randint(100, 999))
        exp = "11/29"
        limit = round(float(row["price"]) * 1.03, 2)
        conn.execute("UPDATE inventory SET status = 'ACQUIRED_IN_TRANSIT' WHERE vin = ?", (vin,))
        conn.execute("INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (deal_id, vin, vcard, cvv, exp, limit, "DISPATCHED_FOR_DELIVERY", "48 HRS - ENCLOSED CARRIER", time.time()))
        conn.commit()
        conn.close()
        self._send(200, "application/json", json.dumps({"status": "SUCCESS", "deal_id": deal_id, "virtual_card": vcard, "cvv": cvv, "exp": exp, "authorized_limit": limit}).encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8099), DealershipHandler).serve_forever()
