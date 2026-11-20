import base64, hashlib, http.server, json, os, pathlib, socketserver, sqlite3, subprocess, tempfile, threading, time, urllib.request

PORT = 8102
HOME = pathlib.Path.home()
DB_PATH = HOME / "astra_orbital_ledger.db"
PRIV_KEY = HOME / ".astra_keys" / "ed25519_private.pem"
PUB_KEY = HOME / ".astra_keys" / "ed25519_public.pem"

LATEST_BLOCK = {}
LOCK = threading.Lock()

def init_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orbital_blocks (
            height INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            prev_hash TEXT NOT NULL,
            merkle_root TEXT NOT NULL,
            block_hash TEXT NOT NULL,
            signature_b64 TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def fetch_json(url, timeout=4.0):
    req = urllib.request.Request(url, headers={"User-Agent": "ASTRA-Orbital-Spine/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def collect_feeds():
    iss = {"lat": None, "lon": None, "alt_km": None, "vel_kmh": None}
    try:
        d = fetch_json("https://api.wheretheiss.at/v1/satellites/25544")
        iss = {
            "lat": round(d.get("latitude", 0.0), 4),
            "lon": round(d.get("longitude", 0.0), 4),
            "alt_km": round(d.get("altitude", 0.0), 2),
            "vel_kmh": round(d.get("velocity", 0.0), 1),
        }
    except Exception:
        pass

    eonet = []
    try:
        d = fetch_json("https://eonet.gsfc.nasa.gov/api/v3/events?limit=3&status=open")
        eonet = [{"id": e.get("id"), "title": e.get("title")} for e in d.get("events", [])[:3]]
    except Exception:
        pass

    spot = {"btc_usd": None, "eth_usd": None}
    try:
        spot["btc_usd"] = float(fetch_json("https://api.coinbase.com/v2/prices/BTC-USD/spot")["data"]["amount"])
        spot["eth_usd"] = float(fetch_json("https://api.coinbase.com/v2/prices/ETH-USD/spot")["data"]["amount"])
    except Exception:
        pass

    return {"iss": iss, "eonet": eonet, "spot": spot}

def merkle_root(leaves):
    hashes = [hashlib.sha256(x.encode("utf-8")).hexdigest() for x in leaves]
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        hashes = [hashlib.sha256((hashes[i] + hashes[i+1]).encode("utf-8")).hexdigest() for i in range(0, len(hashes), 2)]
    return hashes[0]

def sign_ed25519(message_bytes):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(message_bytes)
        in_path = tf.name
    out_path = in_path + ".sig"
    try:
        subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", str(PRIV_KEY), "-rawin", "-in", in_path, "-out", out_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return base64.b64encode(pathlib.Path(out_path).read_bytes()).decode("ascii")
    finally:
        for p in (in_path, out_path):
            try: os.remove(p)
            except OSError: pass

def spine_loop():
    global LATEST_BLOCK
    conn = init_db()
    while True:
        try:
            cur = conn.execute("SELECT block_hash FROM orbital_blocks ORDER BY height DESC LIMIT 1")
            row = cur.fetchone()
            prev_hash = row[0] if row else "0" * 64

            ts = int(time.time())
            feeds = collect_feeds()
            m_root = merkle_root([
                json.dumps(feeds["iss"], sort_keys=True),
                json.dumps(feeds["eonet"], sort_keys=True),
                json.dumps(feeds["spot"], sort_keys=True),
                str(ts),
            ])
            payload_str = json.dumps({"ts": ts, "prev_hash": prev_hash, "merkle_root": m_root, "feeds": feeds}, sort_keys=True)
            b_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
            sig_b64 = sign_ed25519(b_hash.encode("ascii"))

            cur = conn.execute(
                "INSERT INTO orbital_blocks (ts, prev_hash, merkle_root, block_hash, signature_b64, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (ts, prev_hash, m_root, b_hash, sig_b64, payload_str)
            )
            conn.commit()
            block = {
                "height": cur.lastrowid, "ts": ts, "prev_hash": prev_hash,
                "merkle_root": m_root, "block_hash": b_hash,
                "signature_b64": sig_b64, "feeds": feeds
            }
            with LOCK:
                LATEST_BLOCK = block
        except Exception as e:
            with LOCK:
                LATEST_BLOCK = {"error": str(e), "ts": int(time.time())}
        time.sleep(10.0)

class OrbitalHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _send(self, code, ctype, body):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/", "/health", "/api/latest"):
            with LOCK:
                return self._send(200, "application/json", json.dumps({"ok": True, "service": "astra-orbital-8102", "block": LATEST_BLOCK}))
        if self.path == "/api/pubkey":
            return self._send(200, "text/plain; charset=utf-8", PUB_KEY.read_text(encoding="utf-8"))
        if self.path == "/api/chain":
            conn = sqlite3.connect(str(DB_PATH))
            rows = conn.execute("SELECT height, ts, prev_hash, merkle_root, block_hash, signature_b64 FROM orbital_blocks ORDER BY height DESC LIMIT 20").fetchall()
            conn.close()
            chain = [{"height": r[0], "ts": r[1], "prev_hash": r[2], "merkle_root": r[3], "block_hash": r[4], "signature_b64": r[5]} for r in rows]
            return self._send(200, "application/json", json.dumps({"ok": True, "blocks": chain}))
        if self.path == "/ws":
            key = self.headers.get("Sec-WebSocket-Key", "")
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            self.wfile.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
            self.wfile.flush()
            try:
                while True:
                    with LOCK:
                        payload = json.dumps(LATEST_BLOCK).encode("utf-8")
                    n = len(payload)
                    hdr = bytes([0x81, n]) if n < 126 else bytes([0x81, 126, (n >> 8) & 255, n & 255])
                    self.wfile.write(hdr + payload); self.wfile.flush(); time.sleep(2.0)
            except Exception:
                return
        self._send(404, "application/json", '{"ok":false,"error":"Not Found"}')

if __name__ == "__main__":
    threading.Thread(target=spine_loop, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("0.0.0.0", PORT), OrbitalHandler).serve_forever()
