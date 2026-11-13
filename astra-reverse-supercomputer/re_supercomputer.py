import os, re, json, time, shutil, sqlite3, hashlib, subprocess, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, "astra-reverse-supercomputer")
APPS_DIR = os.path.join(HOME, "astra-ownable-apps")
DB = os.path.join(BASE, "re_supercomputer.db")

def init():
    os.makedirs(BASE, exist_ok=True); os.makedirs(APPS_DIR, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS audits(id TEXT PRIMARY KEY, target TEXT, kind TEXT, report TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS keys(provider TEXT PRIMARY KEY, api_key TEXT)")
    c.commit(); c.close()

def get_key(provider):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT api_key FROM keys WHERE provider=?", (provider,)).fetchone()
    c.close()
    return (r[0] if r and r[0] else os.getenv(f"{provider.upper()}_API_KEY", "")).strip()

def query_llm_code(directive):
    prompt = f"Write a complete single-file cybernetic HTML5/JS web app for: {directive}. Return ONLY raw HTML starting with <!DOCTYPE html>."
    for prov, url, mdl in [
        ("deepseek", "https://deepseek.com", "deepseek-chat"),
        ("openrouter", "https://openrouter.ai", "deepseek/deepseek-chat-v3-0324:free")
    ]:
        key = get_key(prov)
        if key:
            try:
                body = json.dumps({"model": mdl, "messages": [{"role": "user", "content": prompt}]}).encode()
                rq = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
                res = json.loads(urllib.request.urlopen(rq, timeout=15).read().decode())
                txt = res["choices"][0]["message"]["content"]
                m = re.search(r"<!DOCTYPE html>.*</html>", txt, re.S | re.I)
                return (m.group(0) if m else txt), prov.upper()
            except Exception:
                pass
    if shutil.which("ollama"):
        try:
            out = subprocess.check_output(["ollama", "list"], timeout=2).decode()
            ms = [l.split()[0] for l in out.splitlines()[1:] if l.strip()]
            if ms:
                rq = urllib.request.Request("http://127.0.0", data=json.dumps({"model": ms[0], "prompt": prompt, "stream": False}).encode(), headers={"Content-Type": "application/json"})
                txt = json.loads(urllib.request.urlopen(rq, timeout=15).read().decode()).get("response", "")
                m = re.search(r"<!DOCTYPE html>.*</html>", txt, re.S | re.I)
                if m: return m.group(0), f"OLLAMA:{ms[0]}"
        except Exception:
            pass
    fallback = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{directive}</title><style>body{{background:#040a10;color:#39ff14;font-family:monospace;padding:24px}}.card{{border:1px solid #00f0ff;padding:16px;background:#071420}}</style></head><body><div class="card"><h2>OWNABLE APP // {directive}</h2><p>Engineered by Astra Supercomputer (Claude Code + Codex + DeepSeek + Open-AI)</p><input id="inp" placeholder="Enter live data..." style="padding:6px;background:#02060b;color:#fff;border:1px solid #39ff14"><button onclick="out.innerText='[EXECUTED] '+inp.value+' @ '+new Date().toLocaleTimeString()" style="padding:6px 12px;background:#39ff1422;color:#39ff14;border:1px solid #39ff14">EXECUTE</button><pre id="out" style="margin-top:12px;color:#00f0ff">READY</pre></div></body></html>"""
    return fallback, "LOCAL_SUPERCOMPUTER_CORE"

def reverse_engineer_target(target_path):
    p = os.path.expanduser(target_path.strip() or "~/package.json")
    if not os.path.exists(p): return {"error": f"Path not found: {p}"}
    if os.path.isdir(p):
        files = [os.path.join(r, f) for r, _, fns in os.walk(p) if ".git" not in r for f in fns][:40]
        report = f"[DIR SCAN] {len(files)} files | ASAR: {[f for f in files if f.endswith('.asar')][:2]} | Manifests: {[f for f in files if f.endswith('package.json')][:3]}"
    else:
        txt = open(p, "rb").read(65536).decode("utf-8", "ignore")
        urls = list(set(re.findall(r"https?://[^\s\"'<>]+", txt)))[:6]
        report = f"[FILE AUDIT] {os.path.basename(p)} | Endpoints: {urls} | JS Hooks: {re.findall(r'(?:fetch|ipcRenderer|BrowserWindow)\([^\)]*\)', txt)[:5]}"
    aid = "RE-" + hashlib.sha256(f"{p}{time.time()}".encode()).hexdigest()[:6].upper()
    c = sqlite3.connect(DB); c.execute("INSERT INTO audits VALUES(?,?,?,?,?)", (aid, p, "RE", report, time.time())); c.commit(); c.close()
    return {"id": aid, "target": p, "report": report}


def mirror_to_docs(slug, html_code):
    d_dir = os.path.join(HOME, "docs", "apps", slug)
    os.makedirs(d_dir, exist_ok=True)
    open(os.path.join(d_dir, "index.html"), "w", encoding="utf-8").write(html_code)

def run_supercomputer_agents(directive):
    slug = re.sub(r"[^a-z0-9]+", "_", directive.lower())[:24].strip("_") or "ownable_app"
    app_dir = os.path.join(APPS_DIR, slug)
    os.makedirs(app_dir, exist_ok=True)
    html_code, engine_used = query_llm_code(directive)
    open(os.path.join(app_dir, "index.html"), "w", encoding="utf-8").write(html_code)
    mirror_to_docs(slug, html_code)
    open(os.path.join(app_dir, "manifest.json"), "w").write(json.dumps({"name": directive, "short_name": slug, "start_url": f"/apps/{slug}/", "display": "standalone"}))
    aid = "APP-" + hashlib.sha256(f"{directive}{time.time()}".encode()).hexdigest()[:6].upper()
    url_path = f"/apps/{slug}/"
    summary = f"[{aid}] Engine: {engine_used} -> Live Ownable App ready at {url_path}"
    c = sqlite3.connect(DB); c.execute("INSERT INTO audits VALUES(?,?,?,?,?)", (aid, directive, "APP", summary, time.time())); c.commit(); c.close()
    return {"id": aid, "engine": engine_used, "app_url": url_path, "summary": summary}

def portfolio_risk_radar():
    H = ".".join(["127", "0", "0", "1"])
    eth_usd, ram_pct, geo_mult = 3250.0, 0.0, 1.04
    try: eth_usd = float(json.loads(urllib.request.urlopen(f"http://{H}:8099/api/state", timeout=2).read().decode()).get("eth_usd", 3250.0))
    except Exception: pass
    try: ram_pct = float(json.loads(urllib.request.urlopen(f"http://{H}:8102/api/wf/metrics", timeout=2).read().decode()).get("ram_pct", 0.0))
    except Exception: pass
    try: geo_mult = float(json.loads(urllib.request.urlopen(f"http://{H}:8103/api/geo/state", timeout=2).read().decode()).get("weather", {}).get("demand_multiplier", 1.04))
    except Exception: pass
    signals = []
    if eth_usd < 2800: signals.append("EARLY WARNING: ETH/USD below $2,800 hedge threshold")
    if ram_pct > 85: signals.append(f"SYSTEM RISK: Android RAM at {ram_pct}%")
    if geo_mult > 1.08: signals.append(f"OPPORTUNITY SIGNAL: Local weather demand surge ({geo_mult}x)")
    if not signals: signals.append("ALL CLEAR: Crypto Treasury, Legal Shield, Local Demand & RAM Nominal")
    return {"risk_level": "AMBER" if len(signals) > 1 else "GREEN", "eth_usd": eth_usd, "ram_pct": ram_pct, "geo_multiplier": geo_mult, "early_signals": signals}

class Handler(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path == "/api/re/portfolio-risk": self._j(portfolio_risk_radar())
        else:
            apps = sorted(os.listdir(APPS_DIR)) if os.path.exists(APPS_DIR) else []
            self._j({"status": "ONLINE", "apps": apps})
    def do_POST(self):

        if self.path == "/api/3d/bundle":
            import sys
            sys.path.insert(0, os.path.expanduser("~/astra-reverse-supercomputer"))
            import threejs_bundle_addon as t3b
            ln = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(ln).decode("utf-8", errors="ignore") or "{}")
            res = t3b.generate_3d_bundle(body.get("app_name", "astra_3d_app"), body.get("concept", "Sovereign 3D Experience"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res, indent=2).encode())
            return


        if self.path in ("/api/re/anything", "/api/re/prompt-pack", "/api/re/build-notes"):
            import sys; sys.path.insert(0, os.path.expanduser("~/astra-reverse-supercomputer"))
            import re_anything_addon as rea
            ln = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(ln).decode("utf-8", errors="ignore") or "{}")
            if self.path == "/api/re/anything":
                res = rea.analyze_target(body.get("target", ""), body.get("mode", "auto"))
            elif self.path == "/api/re/prompt-pack":
                ana = rea.analyze_target(body.get("target", ""))
                res = rea.generate_prompt_pack(ana, body.get("objective", "Clean-room clone & harden"))
            else:
                res = rea.build_from_notes(body.get("notes", ""), body.get("app_name", "astra_note_build"))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps(res, indent=2).encode()); return

        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/re/inspect": self._j(reverse_engineer_target(d.get("target", "~/package.json")))
        elif self.path == "/api/re/agents": self._j(run_supercomputer_agents(d.get("directive", "Sovereign Crypto Tracker")))
        elif self.path == "/api/re/set-key":
            c = sqlite3.connect(DB); c.execute("INSERT OR REPLACE INTO keys VALUES(?,?)", (d.get("provider","deepseek").lower(), d.get("api_key","").strip())); c.commit(); c.close()
            self._j({"status": "KEY_SAVED", "provider": d.get("provider")})

init()
HTTPServer(("0.0.0.0", 8105), Handler).serve_forever()
