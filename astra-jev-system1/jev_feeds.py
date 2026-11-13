import os, re, json, time, sqlite3, hashlib, threading, urllib.request

BASE = os.path.expanduser("~/astra-jev-system1")
DB = f"{BASE}/jev_system1.db"
H = ".".join(["127","0","0","1"])

DEFAULT_FEEDS = [
    ("FEED-HN", "Hacker News AI & Tech Frontpage", "https://algolia.com"),
    ("FEED-ETH", "Coinbase Live ETH/USD Spot Feed", "https://coinbase.com"),
    ("FEED-GSO", "Greensboro NC Live Weather & Conditions", "https://open-meteo.com")
]

def init_feeds():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS feeds(feed_id TEXT PRIMARY KEY, name TEXT, url TEXT, last_snapshot TEXT, updated_at REAL)")
    if c.execute("SELECT COUNT(*) FROM feeds").fetchone() == 0:
        for fid, nm, url in DEFAULT_FEEDS:
            c.execute("INSERT INTO feeds VALUES(?,?,?,?,0)", (fid, nm, url, "Pending initial sync"))
    c.commit(); c.close()

def pull_single_feed(feed_id, name, url):
    rq = urllib.request.Request(url, headers={"User-Agent": "Jev-Reflex-Feed/1.0"})
    raw = urllib.request.urlopen(rq, timeout=6).read().decode("utf-8", "ignore")
    try:
        j = json.loads(raw)
        if "hits" in j:
            snap = " | ".join(h.get("title", "") for h in j["hits"][:4] if h.get("title"))
        elif "data" in j and "amount" in j["data"]:
            snap = f"ETH/USD Live Spot: ${float(j['data']['amount']):,.2f}"
        elif "current" in j:
            cur = j["current"]
            snap = f"Greensboro Temp: {cur.get('temperature_2m')}F | Wind: {cur.get('wind_speed_10m')} mph"
        else:
            snap = json.dumps(j)[:320]
    except Exception:
        titles = re.findall(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
        clean = [re.sub(r"<[^>]+>", "", t).strip() for t in titles[1:5]]
        snap = " | ".join(clean) if clean else re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))[:320]

    c = sqlite3.connect(DB)
    c.execute("INSERT OR REPLACE INTO feeds VALUES(?,?,?,?,?)", (feed_id, name, url, snap, time.time()))
    c.commit(); c.close()

    try:
        brq = urllib.request.Request(f"http://{H}:8096/api/brain/remember", data=json.dumps({"domain": "LIVE_EXTERNAL_FEED", "title": name[:36], "content": snap}).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(brq, timeout=2)
    except Exception:
        pass
    return {"feed_id": feed_id, "name": name, "url": url, "snapshot": snap}

def sync_all_feeds():
    init_feeds()
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT * FROM feeds")]
    c.close()
    out = []
    for r in rows:
        try:
            out.append(pull_single_feed(r["feed_id"], r["name"], r["url"]))
        except Exception as e:
            out.append({"feed_id": r["feed_id"], "name": r["name"], "error": str(e)})
    return out

def start_feed_daemon():
    def _loop():
        while True:
            try: sync_all_feeds()
            except Exception: pass
            time.sleep(300)
    threading.Thread(target=_loop, daemon=True).start()
