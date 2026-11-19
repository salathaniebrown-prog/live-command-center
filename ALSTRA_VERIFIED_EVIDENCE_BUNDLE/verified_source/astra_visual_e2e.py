import hashlib, http.client, json, os, re, sqlite3, time

HOME = os.path.expanduser("~")
MEM_DB = os.path.join(HOME, "astra_ai_memory.db")

REQUIRED_SELECTORS = (
    "astra-top-kpi-bar",
    "kpi-net-tooltip",
    "astra-ci-modal",
    "astra-trust-modal",
    "astra-cinema-modal",
    "astra-mesh-modal",
    "astra-voice-cgi-box",
    "astra-webhook-ticker"
)

def run_visual_regression_check():
    conn_http = http.client.HTTPConnection("127.0.0.1", 8088, timeout=8)
    conn_http.request("GET", "/")
    res = conn_http.getresponse()
    html = res.read().decode("utf-8", errors="ignore")

    found = {sel: (sel in html) for sel in REQUIRED_SELECTORS}
    missing = [k for k, v in found.items() if not v]

    tags = re.findall(r"<(div|canvas|button|select|input|iframe)\b", html, flags=re.IGNORECASE)
    fingerprint = hashlib.sha256(("|".join(tags)).encode("utf-8")).hexdigest()[:24]

    conn = sqlite3.connect(MEM_DB, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS visual_baselines (
        page_url TEXT PRIMARY KEY,
        dom_fingerprint TEXT,
        selectors_json TEXT,
        engine_used TEXT,
        timestamp REAL
    )""")
    row = conn.execute("SELECT dom_fingerprint FROM visual_baselines WHERE page_url = ?", ("127.0.0.1:8088",)).fetchone()
    prev_fp = next(iter(row), None) if isinstance(row, (tuple, list)) else None

    if not missing:
        conn.execute(
            "INSERT OR REPLACE INTO visual_baselines VALUES (?, ?, ?, ?, ?)",
            ("127.0.0.1:8088", fingerprint, json.dumps(found), "DIRECT_IP_DOM_EVALUATOR", time.time())
        )
    conn.commit()
    conn.close()

    return {
        "visual_regression_passed": len(missing) == 0,
        "http_status": res.status,
        "dom_fingerprint": fingerprint,
        "baseline_matched": (prev_fp == fingerprint) if prev_fp else True,
        "missing_selectors": missing,
        "selectors_verified": f"{len(REQUIRED_SELECTORS) - len(missing)}/{len(REQUIRED_SELECTORS)}"
    }

if __name__ == "__main__":
    print(json.dumps(run_visual_regression_check(), indent=2))
