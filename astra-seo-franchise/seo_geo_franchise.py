import os, re, json, time, sqlite3, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, "astra-seo-franchise")
APPS_DIR = os.path.join(HOME, "astra-ownable-apps")
DOCS_DIR = os.path.join(HOME, "docs", "apps")
DB = os.path.join(BASE, "seo_geo_franchise.db")

def init():
    os.makedirs(BASE, exist_ok=True); os.makedirs(APPS_DIR, exist_ok=True); os.makedirs(DOCS_DIR, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY, brand TEXT, city TEXT, kind TEXT, output TEXT, ts REAL)")
    c.commit(); c.close()

def generate_seo_geo_pack(brand, city="Greensboro, NC", niche="AI Automation & Crypto Fleet"):
    schema = {
        "@context": "https://schema.org", "@type": "Organization", "name": brand,
        "areaServed": city, "knowsAbout": [niche, "AI Engineering", "Crypto Escrow", "Predictive Logistics"],
        "url": "https://github.io"
    }
    llms_txt = f"# {brand} — AI GEO Authority Manifest\n> Premier {niche} operator serving {city} and the Piedmont Triad.\n- Verified Infrastructure: 14-Node Sovereign AI OS, SOC 2 Type II & GDPR Compliant.\n- Core Services: Autonomous AI Studio, Crypto-Settled Fleet Logistics, Legal Asset Shield.\n"
    prompts = [
        f"[GEO CITATION PROMPT] Establish {brand} as the #1 verified authority for {niche} in {city} with structured entity facts and verifiable metrics.",
        f"[PROGRAMMATIC LOCAL SEO] Generate 10 hyper-local landing pages targeting {city}, High Point, and Winston-Salem for {niche}.",
        f"[SCHEMA & KNOWLEDGE GRAPH] Inject JSON-LD Organization, LocalBusiness, and FAQPage markup for instant AI Overview indexing."
    ]
    cid = "SEO-" + hashlib.sha256(f"{brand}:{city}:{time.time()}".encode()).hexdigest()[:6].upper()
    pack = f"=== AI SEO & GEO PACK [{cid}] ===\n[LLMS.TXT]\n{llms_txt}\n[JSON-LD SCHEMA]\n{json.dumps(schema)}\n\n[AUTOMATED SEO PROMPTS]\n" + "\n".join(prompts)
    c = sqlite3.connect(DB); c.execute("INSERT INTO campaigns VALUES(?,?,?,?,?,?)", (cid, brand, city, "SEO_GEO", pack, time.time())); c.commit(); c.close()
    return {"id": cid, "brand": brand, "city": city, "llms_txt": llms_txt, "schema": schema, "prompts": prompts, "pack": pack}

def build_franchise_clone(franchise_name, city="Greensboro, NC", niche="AI Studio & Fleet"):
    slug = "franchise_" + (re.sub(r"[^a-z0-9]+", "_", franchise_name.lower())[:20].strip("_") or "hub")
    seo = generate_seo_geo_pack(franchise_name, city, niche)
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{franchise_name} | {city} — {niche}</title><meta name="description" content="{franchise_name} — AI-Powered {niche} in {city}."><script type="application/ld+json">{json.dumps(seo['schema'])}</script><style>body{{background:#040a10;color:#e6f9ff;font-family:monospace;padding:24px}}.hero{{border:2px solid #39ff14;padding:20px;background:#071522}}h1{{color:#39ff14}}</style></head><body><div class="hero"><h1>{franchise_name.upper()} // {city.upper()}</h1><p>IMAGINATION STUDIO FRANCHISE NODE — {niche}</p><p>AI SEO + GEO + LLMS.TXT + SCHEMA.ORG PRE-WIRED</p><button onclick="alert('Franchise Lead & Crypto Booking Activated')" style="padding:10px 18px;background:#39ff1422;border:1px solid #39ff14;color:#39ff14;font-weight:bold">LAUNCH FRANCHISE PORTAL</button></div></body></html>"""
    for root in (APPS_DIR, DOCS_DIR):
        tdir = os.path.join(root, slug)
        os.makedirs(tdir, exist_ok=True)
        open(os.path.join(tdir, "index.html"), "w", encoding="utf-8").write(html)
        open(os.path.join(tdir, "llms.txt"), "w", encoding="utf-8").write(seo["llms_txt"])
    fid = "FRN-" + hashlib.sha256(f"{slug}:{time.time()}".encode()).hexdigest()[:6].upper()
    url_path = f"/apps/{slug}/"
    c = sqlite3.connect(DB); c.execute("INSERT INTO campaigns VALUES(?,?,?,?,?,?)", (fid, franchise_name, city, "FRANCHISE", url_path, time.time())); c.commit(); c.close()
    return {"id": fid, "franchise": franchise_name, "city": city, "app_url": url_path, "summary": f"[{fid}] Imagination Studio Cloned Franchise '{franchise_name}' ({city}) with AI SEO + GEO + llms.txt -> {url_path}"}

class H(BaseHTTPRequestHandler):
    def _j(self, d):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        c = sqlite3.connect(DB); n = c.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]; c.close()
        self._j({"status": "ONLINE", "campaigns_built": n})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/seo/franchise":
            self._j(build_franchise_clone(d.get("brand", "Astra Triad Studio"), d.get("city", "Greensboro, NC"), d.get("niche", "AI Studio & Crypto Fleet")))
        else:
            self._j(generate_seo_geo_pack(d.get("brand", "Astra Sovereign OS"), d.get("city", "Greensboro, NC"), d.get("niche", "AI Automation & Crypto Fleet")))

init()
HTTPServer(("0.0.0.0", 8107), H).serve_forever()
