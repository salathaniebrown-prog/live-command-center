import hashlib, http.client, json, math, os, sqlite3, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_ai_memory.db")

def fetch_local_json(port, path="/"):
    host = ".".join(["127", "0", "0", "1"])
    try:
        c = http.client.HTTPConnection(host, port, timeout=2.5)
        c.request("GET", path)
        r = c.getresponse()
        if r.status == 200:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception:
        pass
    return {}

def compute_alpha_vector_state():
    sat = fetch_local_json(8158, "/")
    mir = fetch_local_json(8156, "/mirror")
    kern = fetch_local_json(8154, "/")

    sat_t = sat.get("telemetry") or {}
    elev = float(sat_t.get("elevation_deg") or 0.0)
    vel = float(sat_t.get("velocity_kmh") or 27580.0)
    free_ram = float(kern.get("host_free_ram_mb") or 640.0)

    # Normalized multi-domain telemetry state vector [orbital_phase, compute_headroom, mesh_coherence]
    v_orbital = round(math.tanh((elev + 90.0) / 90.0), 4)
    v_compute = round(min(1.0, free_ram / 1024.0), 4)
    v_mesh = 1.0 if mir.get("mirror_id") else 0.75
    alpha_magnitude = round(math.sqrt((v_orbital ** 2 + v_compute ** 2 + v_mesh ** 2) / 3.0), 4)

    vec_id = "AVEC-" + uuid.uuid4().hex[:8].upper()
    ts = time.time()
    proof = "0x" + hashlib.sha256(f"{vec_id}|{alpha_magnitude}|{vel}|{ts}".encode("utf-8")).hexdigest()

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS alpha_vector_telemetry (
        vec_id TEXT PRIMARY KEY,
        alpha_magnitude REAL,
        vector_json TEXT,
        proof_hash TEXT,
        timestamp REAL
    )""")
    vec_payload = {
        "orbital_phase_norm": v_orbital,
        "compute_headroom_norm": v_compute,
        "mirror_mesh_coherence": v_mesh,
        "iss_velocity_kmh": vel,
        "mirror_id": mir.get("mirror_id", "LOCAL_MIRROR")
    }
    conn.execute("INSERT INTO alpha_vector_telemetry VALUES (?, ?, ?, ?, ?)", (vec_id, alpha_magnitude, json.dumps(vec_payload), proof, ts))
    conn.commit()
    conn.close()

    return {
        "vec_id": vec_id,
        "service": "ALPHA_VECTOR_SUPERCOMPUTE_MIRROR",
        "port": 8160,
        "status": "ONLINE",
        "alpha_magnitude": alpha_magnitude,
        "vector_components": vec_payload,
        "attestation_hash": proof,
        "timestamp": ts
    }

class AlphaVectorHandler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self._json(200, compute_alpha_vector_state())

if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("0.0.0.0", 8160), AlphaVectorHandler).serve_forever()
