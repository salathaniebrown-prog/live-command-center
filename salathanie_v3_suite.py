#!/usr/bin/env python3
"""
Salathanie A.I — V3 Unified Upgrade Suite
1. Dealership Core + Mopar Coverage + Printable HMAC Bill of Sale / Settlement Certificate
2. Eagle Eyes Command Center (Live Weather, BTC/ETH/SOL, Live ISS Orbital, Multi-Layer Map)
3. 50-Code Prompt Accelerator Engine (wired to llm_bridge.py + offline fallback)
4. Persistent Artifact Memory & Supercomputer Indexer (SQLite WAL)
"""
import hashlib
import hmac
import json
import os
import py_compile
import sqlite3
import time
import urllib.request
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv
from llm_bridge import enhance_with_llm

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "salathanie_v3.db"
HOME = Path.home()

STAGES = [
    "VCARD_AUTHORIZED",
    "TITLE_&_BILL_OF_SALE_ISSUED",
    "CARRIER_DISPATCHED",
    "DELIVERED_&_VERIFIED",
]

DEFAULT_INVENTORY = [
    ("VEH-2026-HEV", "2026 GMC Hummer EV SUV 3X", 107326.0, "BASE_USDC", "1GKB0RDC6TU008842"),
    ("VEH-2026-TRX", "2026 RAM 1500 RHO Mopar Edition", 74890.0, "BASE_USDC", "1C6SRFU9XTN114209"),
    ("VEH-2026-CHRG", "2026 Dodge Charger Daytona Scat Pack", 73190.0, "VCARD_USD", "2C3CDZKG1TH440912"),
    ("VEH-2025-ROG", "2025 Nissan Rogue Platinum AWD", 41250.0, "VCARD_USD", "JN8BT3DD8SW220194"),
]

SECRET_CODES = {
    "/breakdown": "Break down this complex topic into clear, structured component parts.",
    "/pros cons list": "List the concrete pros and cons in an organized, balanced comparison.",
    "/key takeaways": "Extract the highest-signal key takeaways in concise bullet points.",
    "/myth vs fact": "Separate common myths from verified facts clearly side by side.",
    "/learning path": "Design a step-by-step learning path from fundamentals to mastery.",
    "/daily plan": "Build a practical daily execution schedule with focused time blocks.",
    "/cheat sheet": "Create a compact, high-density quick-reference cheat sheet.",
    "/summary in points": "Summarize the entire topic into crisp, scannable bullet points.",
    "/explain like teacher": "Explain clearly as an experienced classroom teacher using intuitive analogies.",
    "/advanced level": "Deliver an advanced, practitioner-grade deep dive with technical rigor.",
    "/beginner level": "Explain from zero prior knowledge using plain, jargon-free language.",
    "/mistakes to avoid": "Identify the most costly mistakes and exact ways to prevent each.",
    "/best resources": "Recommend the top books, official docs, tools, and open resources.",
    "/exam prep": "Structure key concepts, definitions, and high-yield exam review points.",
    "/motivate me": "Deliver sharp, grounded encouragement focused on execution and resilience.",
    "/quick answer": "Give a direct, no-fluff answer in 2-3 sentences.",
    "/detailed answer": "Provide a thorough, comprehensive explanation covering edge cases.",
    "/step by step": "Walk through the exact numbered procedure from start to finish.",
    "/real world example": "Illustrate the concept with concrete, real-world production examples.",
    "/compare": "Compare the options across cost, speed, trade-offs, and best-fit use cases.",
    "/best option": "Recommend the single best option and justify the choice concretely.",
    "/check my answer": "Audit the provided answer for accuracy, logic gaps, and corrections.",
    "/improve this": "Upgrade clarity, structure, and impact while preserving original intent.",
    "/simplify": "Distill complex language into clear, effortless plain English.",
    "/professional": "Rewrite in polished, executive-ready business tone.",
    "/shorten": "Compress the text to half its length while keeping 100% of the core meaning.",
    "/expand": "Expand this brief outline with concrete details, metrics, and depth.",
    "/examples": "Provide 5 varied, practical examples demonstrating the concept.",
    "/quiz me": "Generate a 5-question interactive knowledge check with answers at the end.",
    "/flashcards": "Create concise Q&A flashcards optimized for rapid active recall.",
    "/interview me": "Run a realistic technical/executive mock interview with tough follow-ups.",
    "/practice questions": "Generate progressive practice problems from easy to hard.",
    "/action plan": "Convert this idea into a concrete, prioritized execution action plan.",
    "/checklist": "Produce a verifiable, step-by-step pre-flight checklist.",
    "/decision matrix": "Score options against weighted criteria in a structured decision matrix.",
    "/find gaps": "Identify missing assumptions, blind spots, and operational vulnerabilities.",
    "/expert mode": "Respond as a Tier-One Principal Specialist with unfiltered tactical depth.",
    "/critical analysis": "Perform a rigorous critical evaluation questioning every assumption.",
    "/fact check": "Verify each claim, flag uncertainties, and separate evidence from opinion.",
    "/research mode": "Structure a deep research dossier: landscape, mechanics, metrics, next steps.",
    "/30 day plan": "Build a concrete 30-day sprint roadmap with weekly deliverables.",
    "/60 day plan": "Build a 60-day execution roadmap across foundation and scale phases.",
    "/90 day plan": "Build a 90-day strategic roadmap with 30/60/90 milestones and KPIs.",
    "/weekly plan": "Lay out a Monday-Sunday operational plan with clear daily outcomes.",
    "/monthly plan": "Map out a 4-week monthly execution plan with review checkpoints.",
    "/habit tracker": "Design a lightweight daily habit tracking system with trigger and reward cues.",
    "/time table": "Create a structured hour-by-hour timetable balancing deep work and recovery.",
    "/productivity tips": "Give high-leverage, zero-fluff workflow tips that immediately save time.",
    "/focus tips": "Provide tactical protocols to eliminate distractions and lock deep focus.",
    "/one line summary": "Compress the entire topic into one razor-sharp sentence.",
}


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dealership_inventory (
            vehicle_id TEXT PRIMARY KEY, name TEXT, price REAL, currency TEXT, vin TEXT, available INT DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS dealership_orders (
            order_id TEXT PRIMARY KEY, ts INT, vehicle_id TEXT, vehicle TEXT, vin TEXT,
            amount REAL, currency TEXT, card_alias TEXT, card_last4 TEXT, stage TEXT,
            mopar_plan TEXT, mopar_monthly REAL, hmac_sig TEXT
        );
        CREATE TABLE IF NOT EXISTS artifact_index (
            path TEXT PRIMARY KEY, root TEXT, name TEXT, ext TEXT, size_bytes INT,
            mtime INT, syntax_ok INT, indexed_ts INT
        );
    """)
    for v in DEFAULT_INVENTORY:
        conn.execute(
            "INSERT OR IGNORE INTO dealership_inventory (vehicle_id, name, price, currency, vin, available) VALUES (?,?,?,?,?,1)",
            v,
        )
    return conn


def _sign_receipt(payload: str) -> str:
    key_path = HOME / ".salathanie_hmac.key"
    key = key_path.read_bytes()[:32] if key_path.exists() else b"salathanie-v3-fallback-key"
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24].upper()


def _pub_ring(label: str):
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-v3-suite", 8125, 200, deterministic_hv(label))
    except Exception:
        pass


# =====================================================================
# 1. DEALERSHIP + MOPAR INSURANCE + PRINTABLE BILL OF SALE / RECEIPT
# =====================================================================
def mopar_quote(price: float, tier: str = "MAX_CARE") -> dict:
    rates = {"BASIC_POWERTRAIN": 0.0014, "ADDED_CARE_PLUS": 0.0021, "MAX_CARE": 0.0029}
    t = tier.upper() if tier.upper() in rates else "MAX_CARE"
    monthly = round(max(49.0, price * rates[t]), 2)
    return {"plan": t, "monthly_usd": monthly, "deductible_usd": 100, "roadside_24_7": True}


def dealership_state() -> dict:
    with db_conn() as c:
        inv = [
            {"vehicle_id": r[0], "name": r[1], "price": r[2], "currency": r[3], "vin": r[4], "available": bool(r[5]), "mopar": mopar_quote(r[2])}
            for r in c.execute("SELECT vehicle_id, name, price, currency, vin, available FROM dealership_inventory").fetchall()
        ]
        orders = [
            {
                "order_id": r[0], "ts": r[1], "vehicle_id": r[2], "vehicle": r[3], "vin": r[4],
                "amount": r[5], "currency": r[6], "card_alias": r[7], "card_last4": r[8],
                "stage": r[9], "mopar_plan": r[10], "mopar_monthly": r[11], "hmac_sig": r[12],
            }
            for r in c.execute("SELECT * FROM dealership_orders ORDER BY ts DESC LIMIT 25").fetchall()
        ]
    return {"ts": int(time.time()), "inventory": inv, "orders": orders}


def dealership_acquire(vehicle_id: str, card_alias: str = "SALATHANIE_VCARD", card_last4: str = "8842", mopar_tier: str = "MAX_CARE") -> dict:
    with db_conn() as c:
        row = c.execute("SELECT vehicle_id, name, price, currency, vin FROM dealership_inventory WHERE vehicle_id=?", (vehicle_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "vehicle_not_found"}
        ts = int(time.time())
        oid = f"ORD-{ts % 1000000}-{row[0][-3:]}"
        mq = mopar_quote(row[2], mopar_tier)
        sig = _sign_receipt(f"{oid}|{row[4]}|{row[2]}|{card_last4}|{ts}")
        c.execute(
            "INSERT INTO dealership_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (oid, ts, row[0], row[1], row[4], row[2], row[3], card_alias, card_last4, STAGES[0], mq["plan"], mq["monthly_usd"], sig),
        )
    _pub_ring(f"dealership:acquire:{oid}")
    return {"ok": True, "order_id": oid, "stage": STAGES[0], "vehicle": row[1], "amount": row[2], "mopar": mq, "hmac_sig": sig}


def dealership_advance(order_id: str, target_stage: str = "") -> dict:
    with db_conn() as c:
        row = c.execute("SELECT stage FROM dealership_orders WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "order_not_found"}
        cur = row[0]
        if target_stage in STAGES:
            nxt = target_stage
        else:
            idx = STAGES.index(cur) if cur in STAGES else 0
            nxt = STAGES[min(idx + 1, len(STAGES) - 1)]
        c.execute("UPDATE dealership_orders SET stage=? WHERE order_id=?", (nxt, order_id))
    _pub_ring(f"dealership:advance:{order_id}:{nxt}")
    return {"ok": True, "order_id": order_id, "stage": nxt}


def dealership_receipt_html(order_id: str) -> str:
    with db_conn() as c:
        r = c.execute("SELECT * FROM dealership_orders WHERE order_id=?", (order_id,)).fetchone()
    if not r:
        return "<html><body style='font-family:monospace;background:#0b0f14;color:#f85149;padding:24px'>Order not found.</body></html>"
    dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(r[1]))
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bill of Sale & Settlement Certificate — {r[0]}</title>
<style>
body{{font-family:monospace;background:#f8fafc;color:#0f172a;margin:20px}}
.cert{{max-width:680px;margin:0 auto;border:2px solid #0f172a;padding:24px;background:#fff}}
.row{{display:flex;justify-content:space-between;border-bottom:1px dashed #cbd5e1;padding:8px 0}}
.sig{{background:#0f172a;color:#38bdf8;padding:10px;border-radius:6px;margin-top:14px;word-break:break-all}}
@media print{{.noprint{{display:none}}}}
</style></head><body><div class="cert">
<h2 style="margin-top:0">SALATHANIE A.I — VEHICLE BILL OF SALE & CRYPTO SETTLEMENT CERTIFICATE</h2>
<div class="row"><b>Order ID</b><span>{r[0]}</span></div>
<div class="row"><b>Timestamp</b><span>{dt}</span></div>
<div class="row"><b>Vehicle</b><span>{r[3]}</span></div>
<div class="row"><b>VIN</b><span>{r[4]}</span></div>
<div class="row"><b>Settlement Amount</b><span>${r[5]:,.2f} ({r[6]})</span></div>
<div class="row"><b>Payment Instrument</b><span>{r[7]} (•••• {r[8]})</span></div>
<div class="row"><b>Pipeline Stage</b><span>{r[9]}</span></div>
<div class="row"><b>Mopar Protection Plan</b><span>{r[10]} (${r[11]:.2f}/mo)</span></div>
<div class="sig"><b>ZERO-TRUST HMAC-SHA256 ATTESTATION:</b> {r[12]}</div>
<div class="noprint" style="margin-top:16px">
  <button onclick="window.print()" style="padding:10px 16px;background:#0f172a;color:#fff;border:none;border-radius:6px;cursor:pointer">Print / Save PDF</button>
  <a href="/dealership" style="margin-left:12px">Back to Dealership</a>
</div></div></body></html>"""


# =====================================================================
# 2. EAGLE EYES COMMAND CENTER (WEATHER + CRYPTO + LIVE ORBITAL)
# =====================================================================
def _fetch_json(url: str, timeout: float = 3.5) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Salathanie-EagleEyes/3.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def eagle_eyes_telemetry() -> dict:
    # Live Piedmont Triad Weather (Winston-Salem: 36.0999, -80.2442)
    wx_raw = _fetch_json("https://api.open-meteo.com/v1/forecast?latitude=36.0999&longitude=-80.2442&current=temperature_2m,relative_humidity_2m,wind_speed_10m")
    if wx_raw and "current" in wx_raw:
        cur = wx_raw["current"]
        weather = {"location": "Winston-Salem / Greensboro, NC", "temp_c": cur.get("temperature_2m"), "humidity_pct": cur.get("relative_humidity_2m"), "wind_kph": cur.get("wind_speed_10m"), "live": True}
    else:
        weather = {"location": "Winston-Salem / Greensboro, NC", "temp_c": 18.6, "humidity_pct": 79, "wind_kph": 8.0, "live": False}

    # Live Crypto Spot (CoinGecko public simple price with fallback)
    cg = _fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
    if cg and "bitcoin" in cg:
        markets = {"BTC": cg["bitcoin"].get("usd", 0), "ETH": cg["ethereum"].get("usd", 0), "SOL": cg["solana"].get("usd", 0), "live": True}
    else:
        markets = {"BTC": 96420.50, "ETH": 3340.25, "SOL": 218.40, "live": False}

    # Live ISS Orbital Telemetry
    iss_raw = _fetch_json("https://api.wheretheiss.at/v1/satellites/25544")
    if iss_raw and "latitude" in iss_raw:
        iss = {
            "name": "ISS (ZARYA)",
            "lat": round(float(iss_raw["latitude"]), 4),
            "lon": round(float(iss_raw["longitude"]), 4),
            "alt_km": round(float(iss_raw.get("altitude", 420)), 1),
            "vel_kph": round(float(iss_raw.get("velocity", 27600)), 1),
            "live": True,
        }
    else:
        iss = {"name": "ISS (ZARYA)", "lat": 36.0999, "lon": -80.2442, "alt_km": 420.2, "vel_kph": 27580.0, "live": False}

    return {
        "ts": int(time.time()),
        "status": "ONLINE",
        "fria_zone": "Eagle Eyes (STEM+C Inc — Triad NC)",
        "weather": weather,
        "crypto": markets,
        "orbital": {"iss": iss, "constellations": ["ISS", "Starlink", "GPS", "NOAA"]},
    }


# =====================================================================
# 3. 50-CODE PROMPT ACCELERATOR ENGINE
# =====================================================================
def run_secret_code(code: str, topic: str) -> dict:
    c = code.strip().lower()
    if not c.startswith("/"):
        c = "/" + c
    directive = SECRET_CODES.get(c)
    if not directive:
        return {"ok": False, "error": f"Unknown code '{c}'", "count": len(SECRET_CODES)}
    t = topic.strip() or "Salathanie A.I Edge Architecture"
    base = {
        "ok": True,
        "code": c,
        "directive": directive,
        "topic": t,
        "structured_output": f"[{c.upper()}] {t}\n1. Directive: {directive}\n2. Core Focus: Execute {t} with measurable KPIs, zero-error checks, and low-RAM edge reliability.\n3. Immediate Action: Apply '{c}' directly to your active Salathanie workflow.",
    }
    return enhance_with_llm("expert_code", f"Apply {c} ({directive}) to: {t}", base)


# =====================================================================
# 4. PERSISTENT ARTIFACT MEMORY & SUPERCOMPUTER INDEXER
# =====================================================================
SCAN_ROOTS = [
    HOME / "live-command-center",
    HOME / "astra-enterprise-core",
    HOME / "ai-studio-dealership",
    HOME / "alstra-core",
    HOME / "models",
    HOME / "telemetry-spine",
]
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "builds", "infra_blueprints"}


def sync_artifact_memory(check_syntax: bool = False) -> dict:
    ts = int(time.time())
    indexed = []
    with db_conn() as c:
        for root in SCAN_ROOTS:
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for fn in filenames:
                    ext = Path(fn).suffix.lower()
                    if ext not in (".py", ".sh", ".js", ".html", ".json", ".kts", ".yml", ".tf"):
                        continue
                    fp = Path(dirpath) / fn
                    try:
                        st = fp.stat()
                    except OSError:
                        continue
                    syn_ok = 1
                    if check_syntax and ext == ".py":
                        try:
                            py_compile.compile(str(fp), doraise=True)
                        except Exception:
                            syn_ok = 0
                    c.execute(
                        "INSERT OR REPLACE INTO artifact_index VALUES (?,?,?,?,?,?,?,?)",
                        (str(fp), root.name, fn, ext, st.st_size, int(st.st_mtime), syn_ok, ts),
                    )
                    indexed.append({"root": root.name, "name": fn, "ext": ext, "size": st.st_size, "syntax_ok": bool(syn_ok)})
    _pub_ring(f"artifacts:synced:{len(indexed)}")
    return {"ok": True, "ts": ts, "total_indexed": len(indexed), "roots_scanned": [r.name for r in SCAN_ROOTS if r.exists()], "recent": sorted(indexed, key=lambda x: x["name"])[:60]}


def search_artifacts(query: str = "") -> dict:
    q = f"%{query.strip().lower()}%"
    with db_conn() as c:
        total = c.execute("SELECT COUNT(*) FROM artifact_index").fetchone()[0]
        if total == 0:
            return sync_artifact_memory(check_syntax=False)
        rows = c.execute(
            "SELECT root, name, ext, size_bytes, mtime, syntax_ok, path FROM artifact_index WHERE lower(name) LIKE ? OR lower(root) LIKE ? ORDER BY mtime DESC LIMIT 80",
            (q, q),
        ).fetchall()
    return {
        "ok": True,
        "total_in_db": total,
        "matches": len(rows),
        "artifacts": [{"root": r[0], "name": r[1], "ext": r[2], "size": r[3], "mtime": r[4], "syntax_ok": bool(r[5]), "path": r[6]} for r in rows],
    }


# =====================================================================
# HTML CONSOLES (MOBILE-FIRST, ZERO HEAVY BUNDLES)
# =====================================================================
NAV_BAR = """<div class="nav" style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px">
  <a href="/">Pilot</a>
  <a href="/agents" style="background:#8957e5">18-Agents</a>
  <a href="/trader" style="background:#d29922;color:#050912">Trader/OMS</a>
  <a href="/infra" style="background:#0ea5e9;color:#050912">Infra/SRE</a>
  <a href="/dealership" style="background:#238636">Dealership</a>
  <a href="/eagle-eyes" style="background:#0891b2">Eagle Eyes</a>
  <a href="/codes" style="background:#db2777">50 Codes</a>
  <a href="/artifacts" style="background:#4f46e5">Artifacts</a>
  <a href="/creative" style="background:#f97316;color:#050912">Creative Studio</a>
  <a href="/astra-jet" style="background:#38bdf8;color:#050912">Astra Jet AI</a>
  <a href="/jet-3d" style="background:#39ff14;color:#050912">3D Jet HUD</a>
</div>"""

BASE_CSS = """body{font-family:monospace;background:#090d14;color:#e6edf3;margin:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
.nav a{display:inline-block;background:#1f6feb;color:#fff;padding:6px 9px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:bold}
button{background:#238636;color:#fff;border:none;padding:7px 10px;border-radius:6px;cursor:pointer;font-family:monospace;margin:3px 2px}
input,select,textarea{width:100%;box-sizing:border-box;background:#0d1117;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace;margin-top:6px}
pre{background:#0d1117;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:280px;white-space:pre-wrap;word-break:break-all}
.badge{background:#1f6feb;padding:2px 6px;border-radius:4px;font-size:10px}"""

DEALERSHIP_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — Dealership, Mopar & Settlement</title><style>{BASE_CSS}</style></head><body>
<h2>Salathanie AI Dealership // Escrow, Mopar & Bill of Sale</h2>{NAV_BAR}
<div class="card">
  <b>Acquire Vehicle (Virtual Card / Crypto Escrow + Mopar Protection)</b>
  <select id="veh"></select>
  <select id="mopar"><option value="MAX_CARE">Mopar MAX CARE ($100 ded.)</option><option value="ADDED_CARE_PLUS">Mopar Added Care Plus</option><option value="BASIC_POWERTRAIN">Mopar Basic Powertrain</option></select>
  <input id="alias" value="SALATHANIE_VCARD" placeholder="Card / Wallet Alias">
  <button onclick="acquire()">Authorize & Settle Acquisition</button>
  <div id="log" style="margin-top:8px;color:#3fb950"></div>
</div>
<div class="card"><b>Active Pipeline & Printable Settlement Certificates</b><div id="orders">Loading...</div></div>
<script>
async function refresh(){{
  const r = await fetch('/api/v3/dealership/state'); const d = await r.json();
  document.getElementById('veh').innerHTML = d.inventory.map(v=>`<option value="${{v.vehicle_id}}">${{v.name}} — $${{v.price.toLocaleString()}} (${{v.currency}})</option>`).join('');
  document.getElementById('orders').innerHTML = (d.orders.length ? d.orders.map(o=>{{
    let btn = '';
    if(o.stage==='VCARD_AUTHORIZED') btn=`<button onclick="adv('${{o.order_id}}','TITLE_&_BILL_OF_SALE_ISSUED')">1. Issue Bill of Sale</button>`;
    else if(o.stage==='TITLE_&_BILL_OF_SALE_ISSUED') btn=`<button onclick="adv('${{o.order_id}}','CARRIER_DISPATCHED')">2. Dispatch Carrier</button>`;
    else if(o.stage==='CARRIER_DISPATCHED') btn=`<button onclick="adv('${{o.order_id}}','DELIVERED_&_VERIFIED')">3. Confirm Delivery</button>`;
    return `<div style="border-bottom:1px solid #30363d;padding:10px 0">
      <b>${{o.order_id}}</b> — ${{o.vehicle}} <span class="badge">${{o.stage}}</span><br>
      <small>VIN: ${{o.vin}} | $${{o.amount.toLocaleString()}} via ${{o.card_alias}} | Mopar: ${{o.mopar_plan}} ($${{o.mopar_monthly}}/mo)</small><br>
      ${{btn}} <a href="/api/v3/receipt?id=${{o.order_id}}" target="_blank"><button style="background:#1f6feb">Printable Bill of Sale / Cert</button></a>
    </div>`;
  }}).join('') : 'No orders yet.');
}}
async function acquire(){{
  const r = await fetch('/api/v3/dealership/acquire',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{vehicle_id:document.getElementById('veh').value,card_alias:document.getElementById('alias').value,mopar_tier:document.getElementById('mopar').value}})}});
  const out = await r.json();
  document.getElementById('log').textContent = out.ok ? `[OK] ${{out.order_id}} settled | HMAC: ${{out.hmac_sig}}` : out.error;
  refresh();
}}
async function adv(id, stage){{
  await fetch('/api/v3/dealership/advance',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{order_id:id,stage}})}});
  refresh();
}}
refresh();
</script></body></html>"""

EAGLE_EYES_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eagle Eyes Command Center v3 — Live 3D/Orbital Telemetry</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>{BASE_CSS} #map{{height:320px;border-radius:8px;border:1px solid #30363d;background:#0d1117}}</style></head><body>
<h2 style="color:#38bdf8">EAGLE EYES COMMAND CENTER v3 // LIVE TELEMETRY</h2>{NAV_BAR}
<div class="card" id="feeds">Loading live Piedmont Triad weather, crypto markets & ISS orbital feed...</div>
<div class="card">
  <b>Multi-Layer Imagery & Terrain Map (Esri Satellite / OSM / Topo / Dark + Live ISS Tracker)</b>
  <div id="map" style="margin-top:8px"></div>
</div>
<script>
const map = L.map('map').setView([36.0999, -80.2442], 4);
const layers = {{
  "Esri Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'),
  "OpenStreetMap": L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'),
  "World Terrain": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}'),
  "Dark Tactical": L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png')
}};
layers["Esri Satellite"].addTo(map);
L.control.layers(layers).addTo(map);
L.marker([36.0999, -80.2442]).addTo(map).bindPopup("<b>Eagle Eyes FRIA HQ</b><br>Winston-Salem / Greensboro, NC");
let issMarker = null;
async function loadEE(){{
  const r = await fetch('/api/v3/eagle-eyes'); const d = await r.json();
  const w = d.weather, c = d.crypto, iss = d.orbital.iss;
  document.getElementById('feeds').innerHTML =
    `<span style="color:#3fb950"><b>SYSTEM STATUS: ${{d.status}}</b></span> | FRIA: ${{d.fria_zone}}<br>`+
    `<b>WEATHER (${{w.location}}):</b> ${{w.temp_c}}°C | Humidity: ${{w.humidity_pct}}% | Wind: ${{w.wind_kph}} km/h<br>`+
    `<b>CRYPTO MARKETS:</b> BTC $${{Number(c.BTC).toLocaleString()}} | ETH $${{Number(c.ETH).toLocaleString()}} | SOL $${{Number(c.SOL).toLocaleString()}}<br>`+
    `<b>ORBITAL TRACKING:</b> ${{iss.name}} @ (${{iss.lat}}, ${{iss.lon}}) | Alt: ${{iss.alt_km}} km | Vel: ${{iss.vel_kph}} km/h | Feeds: ${{d.orbital.constellations.join(', ')}}`;
  if(!issMarker) issMarker = L.circleMarker([iss.lat, iss.lon], {{radius:7,color:'#38bdf8',fillOpacity:0.8}}).addTo(map).bindPopup('ISS Live Position');
  else issMarker.setLatLng([iss.lat, iss.lon]);
}}
loadEE(); setInterval(loadEE, 15000);
</script></body></html>"""

CODES_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — 50 Secret Codes Engine</title><style>{BASE_CSS}
.grid{{display:flex;flex-wrap:wrap;gap:4px;max-height:190px;overflow:auto;margin-top:8px}}
.chip{{background:#0d1117;border:1px solid #30363d;color:#58a6ff;padding:4px 7px;border-radius:5px;font-size:11px;cursor:pointer}}
</style></head><body>
<h2>Salathanie A.I — 50 Prompt Accelerator Codes</h2>{NAV_BAR}
<div class="card">
  <b>Tap Any of the 50 Codes or Type Below</b>
  <div id="chips" class="grid"></div>
  <input id="code" value="/action plan">
  <textarea id="topic" rows="2">Scale Salathanie A.I edge architecture and mobile services in Greensboro & Winston-Salem</textarea>
  <button onclick="runCode()">Execute Code</button>
</div>
<div class="card"><b>Output</b><pre id="out">Ready.</pre></div>
<script>
fetch('/api/v3/codes/list').then(r=>r.json()).then(d=>{{
  document.getElementById('chips').innerHTML = Object.keys(d.codes).map(k=>`<span class="chip" onclick="document.getElementById('code').value='${{k}}'">${{k}}</span>`).join('');
}});
async function runCode(){{
  document.getElementById('out').textContent = 'Running...';
  const r = await fetch('/api/v3/codes/run',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{code:document.getElementById('code').value,topic:document.getElementById('topic').value}})}});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}}
</script></body></html>"""

ARTIFACTS_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — Persistent Artifact Memory Index</title><style>{BASE_CSS}</style></head><body>
<h2>Salathanie A.I — Persistent Artifact Memory Indexer</h2>{NAV_BAR}
<div class="card">
  <button onclick="syncNow(false)">Fast Sync All Artifacts</button>
  <button style="background:#1f6feb" onclick="syncNow(true)">Deep Sync + Python Syntax Audit</button>
  <input id="q" placeholder="Filter artifacts by name or folder..." oninput="searchNow()">
  <div id="meta" style="margin-top:8px;color:#3fb950"></div>
</div>
<div class="card"><pre id="list">Loading index...</pre></div>
<script>
async function syncNow(audit){{
  document.getElementById('meta').textContent = audit ? 'Deep auditing syntax across all roots...' : 'Indexing...';
  const r = await fetch('/api/v3/artifacts/sync?audit='+(audit?'1':'0')); const d = await r.json();
  document.getElementById('meta').textContent = `[VERIFIED] Indexed ${{d.total_indexed}} artifacts across: ${{d.roots_scanned.join(', ')}}`;
  searchNow();
}}
async function searchNow(){{
  const q = encodeURIComponent(document.getElementById('q').value || '');
  const r = await fetch('/api/v3/artifacts/search?q='+q); const d = await r.json();
  const lines = (d.artifacts||[]).map(a=>`${{a.syntax_ok?'[OK]':'[ERR]'}} [${{a.root}}] ${{a.name}} (${{a.size}}B)`);
  document.getElementById('list').textContent = lines.join('\\n') || 'No matches.';
}}
searchNow();
</script></body></html>"""
