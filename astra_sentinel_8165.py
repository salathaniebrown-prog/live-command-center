import hashlib, http.server, json, os, pathlib, socket, socketserver
import sqlite3, subprocess, threading, time, urllib.request

HOME = pathlib.Path.home()
DB_PATH = HOME / ".astra_sentinel.db"
PORT = 8165
AUDIT_DOMAIN = os.environ.get("ASTRA_AUDIT_DOMAIN", "").strip()

CORE_SERVICES = [
    (8090, "astra-8090-gw"),
    (8088, "astra-8088-ingress"),
    (3000, "astra-3000-core"),
    (8151, "astra-8151-core"),
    (8161, "astra-8161-async"),
]

STATE = {
    "status": "ARMED",
    "threat_level": "LOW",
    "last_scan": 0,
    "ports": {},
    "fim": {"tracked_files": 0, "alerts": 0, "media_folders": {}},
    "network": {"lan_ip": "unknown", "wan_ip": "pending", "wan_drifts": 0},
    "perimeter": {
        "cloudflared": "OFFLINE",
        "doh_dns": "PENDING",
        "domain": AUDIT_DOMAIN or "not_set",
        "spf": "N/A",
        "dmarc": "N/A",
    },
    "hardware": {"ram_pct": 0.0, "ram_avail_mb": 0, "disk_pct": 0.0},
    "self_heals": 0,
}

FIM_BASELINES = {}
LAST_HEAL = {}
LAST_EXT_CHECK = 0

def db_exec(sql, params=(), fetch=False):
    con = sqlite3.connect(str(DB_PATH), timeout=5)
    try:
        cur = con.execute(sql, params)
        rows = cur.fetchall() if fetch else None
        con.commit()
        return rows
    finally:
        con.close()

def init_db():
    db_exec("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            pillar TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)

def log_event(pillar, severity, message):
    db_exec(
        "INSERT INTO events (ts, pillar, severity, message) VALUES (?, ?, ?, ?)",
        (time.time(), pillar, severity, message),
    )

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def doh_txt_query(name):
    url = f"https://cloudflare-dns.com/dns-query?name={name}&type=TXT"
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=4) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [a.get("data", "").strip('"') for a in data.get("Answer", [])]

def scan_fim():
    watch_files = list(HOME.glob("*.py")) + list((HOME / "portable_vserver").glob("*.py"))
    if (HOME / "alstra_save.sh").exists():
        watch_files.append(HOME / "alstra_save.sh")

    current = {}
    for p in watch_files:
        try:
            current[str(p)] = sha256_file(p)
        except OSError:
            pass

    if not FIM_BASELINES:
        FIM_BASELINES.update(current)
        log_event("DATA_FIM", "INFO", f"Baseline locked: {len(current)} files hashed (SHA-256)")
    else:
        for fp, digest in current.items():
            if fp not in FIM_BASELINES:
                FIM_BASELINES[fp] = digest
                STATE["fim"]["alerts"] += 1
                log_event("DATA_FIM", "WARN", f"New script detected: {os.path.basename(fp)}")
            elif FIM_BASELINES[fp] != digest:
                FIM_BASELINES[fp] = digest
                STATE["fim"]["alerts"] += 1
                log_event("DATA_FIM", "HIGH", f"SHA-256 drift: {os.path.basename(fp)}")
        for fp in list(FIM_BASELINES.keys()):
            if fp not in current:
                del FIM_BASELINES[fp]
                STATE["fim"]["alerts"] += 1
                log_event("DATA_FIM", "HIGH", f"Protected file removed: {os.path.basename(fp)}")

    STATE["fim"]["tracked_files"] = len(FIM_BASELINES)
    media_info = {}
    for folder in ["storage/pictures", "storage/dcim"]:
        d = HOME / folder
        if d.exists() and d.is_dir():
            try:
                entries = list(d.iterdir())
                media_info[folder] = {"items": len(entries), "mtime": int(d.stat().st_mtime)}
            except OSError:
                media_info[folder] = {"items": -1, "mtime": 0}
        else:
            media_info[folder] = {"items": 0, "status": "unlinked"}
    STATE["fim"]["media_folders"] = media_info

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0

def scan_services():
    now = time.time()
    down_count = 0
    for port, pm2_name in CORE_SERVICES:
        up = check_port(port)
        STATE["ports"][str(port)] = "ONLINE" if up else "OFFLINE"
        if not up:
            down_count += 1
            if now - LAST_HEAL.get(pm2_name, 0) > 300:
                LAST_HEAL[pm2_name] = now
                STATE["self_heals"] += 1
                log_event("SOAR_APP", "WARN", f"Port {port} offline -> auto-healing {pm2_name}")
                subprocess.Popen(["pm2", "restart", pm2_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return down_count

def scan_network_and_perimeter():
    global LAST_EXT_CHECK
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan = s.getsockname()[0]
        s.close()
    except OSError:
        lan = "127.0.0.1"
    if STATE["network"]["lan_ip"] not in ("unknown", lan):
        log_event("NETWORK", "WARN", f"LAN IP shifted: {STATE['network']['lan_ip']} -> {lan}")
    STATE["network"]["lan_ip"] = lan

    cf = subprocess.run(["pgrep", "-f", "cloudflared"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    STATE["perimeter"]["cloudflared"] = "ONLINE" if cf.returncode == 0 else "OFFLINE"

    now = time.time()
    if now - LAST_EXT_CHECK > 300:
        LAST_EXT_CHECK = now
        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=3) as r:
                wan = r.read().decode("utf-8").strip()
            prev = STATE["network"]["wan_ip"]
            if prev not in ("pending", "offline", wan):
                STATE["network"]["wan_drifts"] += 1
                log_event("NETWORK", "WARN", f"Broadband/WAN IP changed: {prev} -> {wan}")
            STATE["network"]["wan_ip"] = wan
        except Exception:
            STATE["network"]["wan_ip"] = "offline"

        try:
            doh_txt_query("cloudflare.com")
            STATE["perimeter"]["doh_dns"] = "VERIFIED"
        except Exception:
            STATE["perimeter"]["doh_dns"] = "UNREACHABLE"

        if AUDIT_DOMAIN:
            try:
                txts = doh_txt_query(AUDIT_DOMAIN)
                STATE["perimeter"]["spf"] = "PASS" if any("v=spf1" in t for t in txts) else "MISSING"
                dmarc = doh_txt_query(f"_dmarc.{AUDIT_DOMAIN}")
                STATE["perimeter"]["dmarc"] = "PASS" if any("v=DMARC1" in t for t in dmarc) else "MISSING"
            except Exception:
                STATE["perimeter"]["spf"] = "ERR"
                STATE["perimeter"]["dmarc"] = "ERR"

def scan_hardware():
    mem = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 1)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        used_pct = round(((total - avail) / total) * 100.0, 1)
        STATE["hardware"]["ram_pct"] = used_pct
        STATE["hardware"]["ram_avail_mb"] = avail // 1024
        if used_pct >= 88.0:
            log_event("DEVICE_HW", "WARN", f"RAM pressure {used_pct}% -> auto-flushing PM2 logs")
            subprocess.Popen(["pm2", "flush"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
    try:
        st = os.statvfs(str(HOME))
        total_d = st.f_blocks * st.f_frsize
        free_d = st.f_bavail * st.f_frsize
        STATE["hardware"]["disk_pct"] = round(((total_d - free_d) / max(total_d, 1)) * 100.0, 1)
    except OSError:
        pass

def sentinel_loop():
    init_db()
    log_event("SOAR_CORE", "INFO", "ASTRA Zero Trust Sentinel (:8165) + Perimeter Audit armed")
    while True:
        try:
            down = scan_services()
            scan_fim()
            scan_network_and_perimeter()
            scan_hardware()
            STATE["last_scan"] = int(time.time())
            if down > 0 or STATE["hardware"]["ram_pct"] >= 90.0:
                STATE["threat_level"] = "ELEVATED"
            elif STATE["fim"]["alerts"] > 0:
                STATE["threat_level"] = "GUARDED"
            else:
                STATE["threat_level"] = "LOW"
        except Exception as e:
            log_event("SOAR_CORE", "ERROR", f"Scan exception: {e}")
        time.sleep(30)

HUD_HTML = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASTRA // ZERO TRUST SENTINEL</title>
<style>
body{margin:0;background:#02060d;color:#e0f2fe;font-family:monospace;padding:14px}
h2{margin:0 0 10px;color:#38bdf8;letter-spacing:1px;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.card{background:#071122;border:1px solid #38bdf855;border-radius:8px;padding:12px}
.label{font-size:11px;color:#94a3b8;text-transform:uppercase}
.val{font-size:18px;font-weight:bold;color:#00ff9d;margin-top:4px}
.warn{color:#f59e0b}.bad{color:#f43f5e}
#events{margin-top:14px;background:#050c18;border:1px solid #1e293b;border-radius:8px;padding:10px;max-height:240px;overflow:auto;font-size:12px;line-height:1.5}
.row{border-bottom:1px solid #0f172a;padding:3px 0}
</style></head><body>
<h2>ASTRA // ZERO TRUST SENTINEL &amp; PERIMETER AUDIT (:8165)</h2>
<div class="grid" id="cards"></div>
<div id="events">Loading forensic ledger...</div>
<script>
const base = location.port === '8090' ? '/api/sentinel' : '/api';
async function refresh(){
  const t = await (await fetch(base + '/telemetry')).json();
  const ev = await (await fetch(base + '/events')).json();
  const ports = Object.entries(t.ports).map(([k,v])=>k+':'+(v==='ONLINE'?'OK':'DOWN')).join(' | ');
  const lvlCls = t.threat_level==='LOW'?'':'warn';
  document.getElementById('cards').innerHTML = `
    <div class="card"><div class="label">Posture</div><div class="val ${lvlCls}">${t.threat_level}</div></div>
    <div class="card"><div class="label">RAM Usage</div><div class="val ${t.hardware.ram_pct>85?'bad':''}">${t.hardware.ram_pct}% (${t.hardware.ram_avail_mb}MB)</div></div>
    <div class="card"><div class="label">FIM Files / Alerts</div><div class="val">${t.fim.tracked_files} / ${t.fim.alerts}</div></div>
    <div class="card"><div class="label">Cloudflare / DoH</div><div class="val" style="font-size:13px">CF: ${t.perimeter.cloudflared}<br>DoH: ${t.perimeter.doh_dns}</div></div>
    <div class="card"><div class="label">Email DNS (${t.perimeter.domain})</div><div class="val" style="font-size:13px">SPF: ${t.perimeter.spf}<br>DMARC: ${t.perimeter.dmarc}</div></div>
    <div class="card"><div class="label">LAN / WAN IP</div><div class="val" style="font-size:12px">${t.network.lan_ip}<br>${t.network.wan_ip}</div></div>
    <div class="card"><div class="label">SOAR Auto-Heals</div><div class="val">${t.self_heals}</div></div>
    <div class="card"><div class="label">Core Ports</div><div class="val" style="font-size:11px">${ports}</div></div>
  `;
  document.getElementById('events').innerHTML = ev.map(e =>
    `<div class="row">[${new Date(e.ts*1000).toLocaleTimeString()}] <b>${e.pillar}</b> (${e.severity}): ${e.message}</div>`
  ).join('');
}
refresh(); setInterval(refresh, 5000);
</script></body></html>"""

class SentinelHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/api/telemetry"):
            self._send(200, "application/json", json.dumps(STATE))
        elif self.path.startswith("/api/perimeter"):
            self._send(200, "application/json", json.dumps(STATE["perimeter"]))
        elif self.path.startswith("/api/events"):
            rows = db_exec("SELECT ts, pillar, severity, message FROM events ORDER BY id DESC LIMIT 40", fetch=True) or []
            data = [{"ts": r[0], "pillar": r[1], "severity": r[2], "message": r[3]} for r in rows]
            self._send(200, "application/json", json.dumps(data))
        else:
            self._send(200, "text/html; charset=utf-8", HUD_HTML)

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    threading.Thread(target=sentinel_loop, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("127.0.0.1", PORT), SentinelHandler).serve_forever()
