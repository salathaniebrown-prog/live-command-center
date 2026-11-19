import urllib.request, json, time, os, shutil, sqlite3

DB = "astra_ledger.db"
os.makedirs("backups", exist_ok=True)
last_backup = 0

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AstraEnterpriseCore/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode())

def log_event(kind, detail, val=0.0):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, detail TEXT, val REAL)")
    conn.execute("INSERT INTO ledger (ts, kind, detail, val) VALUES (?, ?, ?, ?)", (ts, kind, detail, val))
    conn.commit()
    conn.close()

def run_hourly_backup():
    global last_backup
    now = time.time()
    if now - last_backup < 3600 or not os.path.exists(DB):
        return
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    dst = f"backups/astra_ledger_{stamp}.db"
    shutil.copy2(DB, dst)
    # Keep only the 24 most recent hourly backups
    files = sorted(os.listdir("backups"))
    for old in files[:-24]:
        os.remove(os.path.join("backups", old))
    last_backup = now
    summary = f"Hourly SQLite snapshot saved -> {dst} ({os.path.getsize(dst)} bytes)"
    log_event("sqlite-backup", summary, float(os.path.getsize(dst)))

    # Optional Webhook / Email Bridge (triggered only if ASTRA_REPORT_WEBHOOK is set in .env)
    hook = os.environ.get("ASTRA_REPORT_WEBHOOK", "").strip()
    if hook:
        try:
            payload = json.dumps({"subject": "ASTRA Hourly Telemetry Report", "summary": summary}).encode()
            req = urllib.request.Request(hook, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=6)
        except Exception:
            pass

while True:
    try:
        # 1. Live USGS Global Seismic Feed (Past Hour)
        eq = fetch_json("https://usgs.gov")
        feats = eq.get("features", [])
        if feats:
            top = feats[0]["properties"]
            log_event("usgs-seismic", f"M{top.get('mag')} :: {top.get('place')} (Total/hr: {len(feats)})", float(top.get("mag") or 0))
        else:
            log_event("usgs-seismic", "0 global earthquakes recorded in past hour", 0.0)

        # 2. Live NWS Active Weather Alerts (US)
        nws = fetch_json("https://weather.gov")
        alerts = nws.get("features", [])
        if alerts:
            p = alerts[0]["properties"]
            log_event("nws-weather", f"{p.get('event')} :: {p.get('areaDesc', '')[:60]}", float(len(alerts)))

        # 3. Live NASA EONET Natural Events Feed
        eonet = fetch_json("https://nasa.gov")
        evs = eonet.get("events", [])
        if evs:
            cat = evs[0]["categories"][0]["title"] if evs[0].get("categories") else "Event"
            log_event("nasa-eonet", f"[{cat}] {evs[0].get('title', '')[:65]}", float(len(evs)))

        run_hourly_backup()
    except Exception as e:
        log_event("global-feed-err", str(e)[:80], 0.0)
    time.sleep(60)
