import http.server, json, os, socket, sqlite3, subprocess, time

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_telemetry.db")
PORTS = (8088, 8090, 8095, 8096, 8097, 8098, 8099, 8100, 8101, 8102, 8108, 8109, 8110, 8111, 8115, 8117, 8119, 8121, 8125)

def get_free_ram():
    with open("/proc/meminfo", "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            if ln.startswith("MemAvailable:"):
                t = ln.split()
                if len(t) >= 2 and t[1].isdigit():
                    return round(int(t[1]) / 1024.0, 1)
    return 0.0

def scan_ports():
    up = []
    for p in PORTS:
        try:
            with socket.create_connection(("127.0.0.1", p), timeout=0.15):
                up.append(p)
        except OSError:
            pass
    return up

def build_payload(route):
    free_mib = get_free_ram()
    up_ports = scan_ports()
    procs = subprocess.check_output(["ps", "-eo", "pid,rss,comm"], text=True, errors="replace").splitlines()[1:]
    sat = {"source": "satellite_telemetry", "mode": "advisory_opinion", "authoritative": False}
    iot = {"node": "termux-android", "free_ram_mib": free_mib, "ram_floor_ok": free_mib >= 520.0, "process_count": len(procs)}
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE IF NOT EXISTS telemetry_chronicles (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, free_ram_mib REAL, online_count INTEGER, payload TEXT)")
    snap = json.dumps({"free_ram_mib": free_mib, "online_ports": up_ports, "satellite_telemetry": sat, "iot_edge": iot})
    conn.execute("INSERT INTO telemetry_chronicles (ts, free_ram_mib, online_count, payload) VALUES (?, ?, ?, ?)", (time.time(), free_mib, len(up_ports), snap))
    conn.commit()
    rows = [{"id": r[0], "ts": r[1], "free_ram_mib": r[2], "online_count": r[3]} for r in conn.execute("SELECT id, ts, free_ram_mib, online_count FROM telemetry_chronicles ORDER BY id DESC LIMIT 3").fetchall()]
    conn.close()
    return {"status": "LIVE_OK", "route": route, "free_ram_mib": free_mib, "online_ports": up_ports, "satellite_telemetry": sat, "iot_edge": iot, "recent_chronicles": rows}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        raw = json.dumps(build_payload(path), indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def log_message(self, *args):
        pass

http.server.ThreadingHTTPServer(("127.0.0.1", 8125), Handler).serve_forever()
