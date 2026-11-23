import hashlib, http.client, json, os, sqlite3, subprocess, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

def _analyze_spine_drift() -> dict:
    import json, os, sqlite3
    db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "astra_flight_ledger.db")
    if not os.path.exists(db):
        return {"ok": True, "status": "NO_LEDGER", "samples": 0, "anomalies": []}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute("SELECT id, ts, craft_id, altitude_ft, airspeed_kts, battery_pct, rotor_rpm FROM telemetry_frames ORDER BY id DESC LIMIT 25").fetchall()
    conn.close()
    if not rows:
        return {"ok": True, "status": "EMPTY", "samples": 0, "anomalies": []}
    latest = rows[0]
    oldest = rows[-1]
    bat_drop = round(oldest[5] - latest[5], 2)
    rpms = [r[6] for r in rows if r[6] > 0]
    rpm_spread = (max(rpms) - min(rpms)) if len(rpms) > 1 else 0
    anomalies = []
    if latest[5] < 20.0:
        anomalies.append("LOW_BATTERY_RESERVE")
    if bat_drop > 3.5:
        anomalies.append("HIGH_BATTERY_SAG")
    if rpm_spread > 900:
        anomalies.append("ROTOR_RPM_VARIANCE")
    return {
        "ok": True,
        "service": "predictive-kernel",
        "port": 8154,
        "status": "WARNING" if anomalies else "NOMINAL",
        "samples": len(rows),
        "craft_id": latest[2],
        "latest_battery_pct": latest[5],
        "window_battery_drop_pct": bat_drop,
        "rotor_rpm_spread": rpm_spread,
        "anomalies": anomalies,
    }


HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_ai_memory.db")

ON_DEMAND_NODES = {
    8096: os.path.join(HOME, "live-command-center", "node_8096.py"),
    8097: os.path.join(HOME, "live-command-center", "node_8097.py"),
    8098: os.path.join(HOME, "live-command-center", "node_8098.py"),
    8100: os.path.join(HOME, "live-command-center", "node_8100.py"),
}

def get_free_ram_mb():
    try:
        vals = {}
        for ln in open("/proc/meminfo"):
            k, sep, v = ln.partition(":")
            if sep:
                tok = next(iter(v.strip().split()), "0")
                if tok.isdigit():
                    vals[k.strip()] = int(tok)
        return round(vals.get("MemAvailable", vals.get("MemFree", 0)) / 1024.0, 1)
    except Exception:
        return 0.0

def probe(port, path="/"):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=1.2)
        c.request("GET", path)
        return c.getresponse().status == 200
    except Exception:
        return False

def wake_node_within_ram_budget(port, min_free_mb=220.0):
    if probe(port):
        return {"port": port, "state": "ALREADY_ONLINE", "free_ram_mb": get_free_ram_mb()}
    free_mb = get_free_ram_mb()
    if free_mb < min_free_mb:
        return {"port": port, "state": "DEFERRED_RAM_GUARD", "free_ram_mb": free_mb}
    script = ON_DEMAND_NODES.get(port)
    if script and os.path.exists(script):
        subprocess.Popen(["python3", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        time.sleep(1.0)
    return {"port": port, "state": "ONLINE" if probe(port) else "STANDBY_UNPROVISIONED", "free_ram_mb": get_free_ram_mb()}

class PredictiveKernelHandler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
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
        if (self.path or "").split("?", 1)[0] in ("/api/predictive/drift", "/api/kernel/telemetry"):
            import json
            b = json.dumps(_analyze_spine_drift()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        active_ports = [8088, 8090, 8095, 8099, 8101, 8102, 8125, 8132, 8140, 8150, 8152]
        live = [p for p in active_ports if probe(p)]
        self._json(200, {
            "service": "SALATHANIE_PREDICTIVE_KERNEL_MULTIPLEXER",
            "port": 8154,
            "status": "ONLINE",
            "host_free_ram_mb": get_free_ram_mb(),
            "live_core_nodes": f"{len(live)}/{len(active_ports)}",
            "online_ports": live
        })

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(ln).decode("utf-8")) if ln else {}
        target_port = int(data.get("wake_port") or 8088)
        wake_res = wake_node_within_ram_budget(target_port)
        tx_id = "KERN-" + uuid.uuid4().hex[:8].upper()
        proof = "0x" + hashlib.sha256(f"{tx_id}|{target_port}|{time.time()}".encode()).hexdigest()
        self._json(200, {"tx_id": tx_id, "wake_result": wake_res, "cryptographic_proof": proof})

if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("0.0.0.0", 8154), PredictiveKernelHandler).serve_forever()
