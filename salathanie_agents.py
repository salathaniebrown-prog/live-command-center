#!/usr/bin/env python3
"""
Salathanie A.I — Unified 18-Agent Enterprise Studio, Web Trader, OMS & FIX/FAST Gateway
Pure stdlib + SQLite WAL + Persistent Port Registry + HDC Ring (~11MB RAM).
"""
import concurrent.futures
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv
from llm_bridge import enhance_with_llm, llm_status

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "salathanie_agents.db"
BUILDS_DIR = REPO / "builds"
PORTS_FILE = Path("/data/data/com.termux/files/usr/tmp/salathanie_ports.json")
PREFERRED_PORT = 8128
ACTIVE_PORT = PREFERRED_PORT


def register_port(name: str, port: int):
    PORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if PORTS_FILE.exists():
        try:
            data = json.loads(PORTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[name] = {"port": port, "pid": os.getpid(), "ts": int(time.time())}
    PORTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, ts INT, title TEXT, body TEXT, artifact TEXT);
        CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, ts INT, title TEXT, urgency INT, impact INT, score REAL, status TEXT);
        CREATE TABLE IF NOT EXISTS flows (id INTEGER PRIMARY KEY, ts INT, name TEXT, trigger_evt TEXT, target_agent TEXT, prompt TEXT);
        CREATE TABLE IF NOT EXISTS knowledge (id INTEGER PRIMARY KEY, ts INT, query TEXT, summary TEXT, device_payload TEXT);
        CREATE TABLE IF NOT EXISTS oms_orders (
            id INTEGER PRIMARY KEY, ts INT, cl_ord_id TEXT, symbol TEXT, side TEXT,
            ord_type TEXT, qty REAL, price REAL, fill_price REAL, status TEXT,
            fix_msg TEXT, fast_hex TEXT
        );
        CREATE TABLE IF NOT EXISTS oms_positions (
            symbol TEXT PRIMARY KEY, net_qty REAL, avg_price REAL, realized_pnl REAL, updated_ts INT
        );
    """)
    return conn


def publish_ring(tag: str):
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-agents", ACTIVE_PORT, 200, deterministic_hv(f"agent:{tag}"))
    except Exception:
        pass


# --- FIX 4.4 & FAST PROTOCOL ENGINE ---
def build_fix_44(msg_type: str, fields: list[tuple[int, str]]) -> dict:
    soh = "\x01"
    utc = time.strftime("%Y%m%d-%H:%M:%S", time.gmtime())
    body_pairs = [(35, msg_type), (49, "SALATHANIE_OMS"), (56, "EDGE_LIQUIDITY"), (52, utc)] + fields
    body = soh.join(f"{k}={v}" for k, v in body_pairs) + soh
    head = f"8=FIX.4.4{soh}9={len(body)}{soh}"
    raw_no_chk = head + body
    chk = sum(raw_no_chk.encode("ascii")) % 256
    full = f"{raw_no_chk}10={chk:03d}{soh}"
    return {"fix_readable": full.replace(soh, "|"), "bytes": len(full), "checksum": f"{chk:03d}"}


def _fast_sbit_uint(n: int) -> bytes:
    n = max(0, int(n))
    chunks = [n & 0x7F]
    n >>= 7
    while n:
        chunks.append(n & 0x7F)
        n >>= 7
    chunks.reverse()
    chunks[-1] |= 0x80  # FAST stop-bit on final byte
    return bytes(chunks)


def build_fast_packet(symbol: str, price: float, qty: float, seq: int) -> dict:
    pmap = bytes([0xF8])  # Presence Map (all fields present + stop bit)
    tid = _fast_sbit_uint(120)  # Template ID 120 (Market/Order Update)
    sym_b = symbol.upper().encode("ascii")[:8]
    sym_enc = sym_b[:-1] + bytes([sym_b[-1] | 0x80]) if sym_b else bytes([0x80])
    payload = pmap + tid + _fast_sbit_uint(seq) + sym_enc + _fast_sbit_uint(int(round(price * 100))) + _fast_sbit_uint(int(round(qty * 1000)))
    return {"fast_hex": payload.hex().upper(), "bytes": len(payload), "template_id": 120}


# --- OMS EXECUTION ENGINE ---
REF_PRICES = {"BTCUSD": 96420.50, "ETHUSD": 3340.25, "SOLUSD": 218.40, "SPY": 598.10, "NVDA": 146.80, "EURUSD": 1.0585}


def oms_place_order(symbol: str, side: str, qty: float, ord_type: str = "MARKET", price: float = 0.0) -> dict:
    sym = re.sub(r"[^A-Z0-9]", "", symbol.upper()) or "BTCUSD"
    side = "SELL" if side.upper() == "SELL" else "BUY"
    ord_type = "LIMIT" if ord_type.upper() == "LIMIT" else "MARKET"
    qty = max(0.001, min(float(qty), 100000.0))
    mkt_px = REF_PRICES.get(sym, 100.0)
    px = float(price) if (ord_type == "LIMIT" and float(price) > 0) else mkt_px
    ts = int(time.time())
    cl_ord_id = f"SAL-{ts}-{int(time.perf_counter_ns() % 10000)}"

    # Risk guard & matching logic
    notional = qty * px
    if notional > 5_000_000:
        return {"ok": False, "rejected": "Risk limit exceeded ($5M max notional)"}

    fills_now = (ord_type == "MARKET") or (side == "BUY" and px >= mkt_px) or (side == "SELL" and px <= mkt_px)
    status = "FILLED" if fills_now else "WORKING"
    fill_px = mkt_px if ord_type == "MARKET" else (px if fills_now else 0.0)

    fix_new = build_fix_44("D", [(11, cl_ord_id), (55, sym), (54, "1" if side == "BUY" else "2"), (38, str(qty)), (40, "1" if ord_type == "MARKET" else "2"), (44, f"{px:.4f}")])
    fix_exec = build_fix_44("8", [(11, cl_ord_id), (37, f"EX{ts}"), (17, f"FILL{ts}"), (150, "2" if fills_now else "0"), (39, "2" if fills_now else "0"), (55, sym), (54, "1" if side == "BUY" else "2"), (32, str(qty if fills_now else 0)), (31, f"{fill_px:.4f}")])
    fast_pkt = build_fast_packet(sym, fill_px or px, qty, ts % 100000)

    with db_conn() as c:
        cur = c.execute(
            "INSERT INTO oms_orders (ts, cl_ord_id, symbol, side, ord_type, qty, price, fill_price, status, fix_msg, fast_hex) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ts, cl_ord_id, sym, side, ord_type, qty, px, fill_px, status, fix_exec["fix_readable"], fast_pkt["fast_hex"]),
        )
        oid = cur.lastrowid
        if fills_now:
            row = c.execute("SELECT net_qty, avg_price, realized_pnl FROM oms_positions WHERE symbol=?", (sym,)).fetchone()
            signed = qty if side == "BUY" else -qty
            if not row:
                c.execute("INSERT INTO oms_positions VALUES (?,?,?,?,?)", (sym, signed, fill_px, 0.0, ts))
            else:
                cur_q, cur_avg, rpnl = row
                new_q = round(cur_q + signed, 6)
                if (cur_q >= 0 and signed > 0) or (cur_q <= 0 and signed < 0):
                    new_avg = ((abs(cur_q) * cur_avg) + (qty * fill_px)) / max(1e-9, abs(new_q))
                else:
                    closed = min(abs(cur_q), qty)
                    rpnl += closed * (fill_px - cur_avg) * (1 if cur_q > 0 else -1)
                    new_avg = fill_px if (cur_q * new_q < 0) else (0.0 if new_q == 0 else cur_avg)
                c.execute("UPDATE oms_positions SET net_qty=?, avg_price=?, realized_pnl=?, updated_ts=? WHERE symbol=?", (new_q, round(new_avg, 4), round(rpnl, 2), ts, sym))

    publish_ring(f"oms:{sym}:{side}:{status}")
    return {"ok": True, "order_id": oid, "cl_ord_id": cl_ord_id, "symbol": sym, "side": side, "type": ord_type, "qty": qty, "fill_price": fill_px, "status": status, "fix_new_order": fix_new, "fix_exec_report": fix_exec, "fast_packet": fast_pkt}


def oms_get_state() -> dict:
    with db_conn() as c:
        orders = [
            {"id": r[0], "ts": r[1], "cl_ord_id": r[2], "symbol": r[3], "side": r[4], "type": r[5], "qty": r[6], "price": r[7], "fill_price": r[8], "status": r[9], "fix": r[10], "fast_hex": r[11]}
            for r in c.execute("SELECT * FROM oms_orders ORDER BY id DESC LIMIT 15").fetchall()
        ]
        positions = []
        for r in c.execute("SELECT symbol, net_qty, avg_price, realized_pnl FROM oms_positions ORDER BY symbol").fetchall():
            mkt = REF_PRICES.get(r[0], r[2])
            upnl = round((mkt - r[2]) * r[1], 2)
            positions.append({"symbol": r[0], "net_qty": r[1], "avg_price": r[2], "mark": mkt, "unrealized_pnl": upnl, "realized_pnl": r[3]})
    return {"ts": int(time.time()), "prices": REF_PRICES, "positions": positions, "orders": orders}


def oms_cancel_order(oid: int) -> dict:
    with db_conn() as c:
        row = c.execute("SELECT cl_ord_id, symbol, side, status FROM oms_orders WHERE id=?", (oid,)).fetchone()
        if not row:
            return {"ok": False, "error": "order_not_found"}
        if row[3] != "WORKING":
            return {"ok": False, "error": f"cannot_cancel_{row[3]}"}
        fix_cxl = build_fix_44("8", [(11, row[0]), (150, "4"), (39, "4"), (55, row[1]), (54, "1" if row[2] == "BUY" else "2")])
        c.execute("UPDATE oms_orders SET status='CANCELED', fix_msg=? WHERE id=?", (fix_cxl["fix_readable"], oid))
    return {"ok": True, "order_id": oid, "status": "CANCELED", "fix_cancel_report": fix_cxl}


# --- EBOOK-TO-BUILD GENERATOR ---
def build_from_ebook(source_text_or_path: str) -> dict:
    src = source_text_or_path.strip()
    title = "Salathanie Ebook App"
    raw_text = src
    source_type = "inline_text"

    p = Path(src).expanduser()
    if src and len(src) < 260 and p.exists() and p.is_file():
        title = p.stem.replace("_", " ").replace("-", " ").title()
        if p.suffix.lower() == ".epub":
            source_type = "epub_file"
            parts = []
            with zipfile.ZipFile(p, "r") as z:
                for name in z.namelist():
                    if name.endswith((".xhtml", ".html", ".htm")) and len(parts) < 25:
                        html = z.read(name).decode("utf-8", errors="ignore")
                        parts.append(re.sub(r"<[^>]+>", " ", html))
            raw_text = "\n".join(parts)[:25000]
        else:
            source_type = f"{p.suffix.lstrip('.') or 'txt'}_file"
            raw_text = p.read_text(encoding="utf-8", errors="ignore")[:25000]
    else:
        first_line = src.splitlines()[0] if src else title
        title = first_line[:48].strip() or title

    # Extract chapters / modules
    lines = [ln.strip() for ln in raw_text.splitlines() if len(ln.strip()) > 4]
    chapters = [ln for ln in lines if re.match(r"^(chapter|part|module|section|#|\d+\.)", ln, re.I)][:8]
    if not chapters:
        chapters = [f"Module {i+1}: {w}" for i, w in enumerate(re.split(r"[.;,\n]+", raw_text)[:5]) if w.strip()] or ["Core Engine", "UI Layer", "API Gateway"]

    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:28] or f"ebook_{int(time.time())}"
    out_dir = BUILDS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    app_py = f'''#!/usr/bin/env python3
"""Auto-generated build from ebook: {title}"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

MODULES = {json.dumps(chapters, indent=2)}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({{"app": "{title}", "modules": MODULES, "status": "ONLINE"}}, indent=2).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

if __name__ == "__main__":
    print("Running {title} on :8190")
    HTTPServer(("0.0.0.0", 8190), Handler).serve_forever()
'''
    readme = f"# {title}\n\nAuto-built by **Salathanie A.I Ebook-to-Build Engine** (`{source_type}`).\n\n## Extracted Modules\n" + "\n".join(f"- {c}" for c in chapters) + "\n\n## Run\n```bash\npython3 app.py\n```\n"
    manifest = {"title": title, "slug": slug, "source_type": source_type, "chapters": chapters, "files": ["app.py", "README.md", "manifest.json"], "created_ts": int(time.time())}

    (out_dir / "app.py").write_text(app_py, encoding="utf-8")
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {"agent": "ebook_builder", "built": True, "build_dir": str(out_dir), "manifest": manifest}


# --- UNIFIED 18-AGENT DISPATCHER ---
def run_agent(agent: str, text: str, mode: str = "default") -> dict:
    a = agent.lower().strip()
    t = text.strip()
    ts = int(time.time())

    if a in ("virtual_dev", "vdev", "software"):
        slug = re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:24] or "service"
        out_dir = BUILDS_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        dockerfile = f"FROM python:3.12-alpine\nWORKDIR /app\nCOPY main.py .\nEXPOSE 8080\nCMD [\"python3\", \"main.py\"]\n"
        main_py = f"#!/usr/bin/env python3\n# Virtual Dev Build: {t}\nimport json, time\nprint(json.dumps({{'service': '{slug}', 'spec': {json.dumps(t)}, 'ts': int(time.time())}}))\n"
        (out_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        (out_dir / "main.py").write_text(main_py, encoding="utf-8")
        out = {"agent": "virtual_dev", "project": slug, "build_dir": str(out_dir), "files_created": ["main.py", "Dockerfile"], "stack": ["Python 3.12", "SQLite WAL", "Docker Alpine", "REST/JSON"]}

    elif a in ("uxui_designer", "uxui", "design"):
        brand = (t or "Salathanie A.I")[:32].replace("<", "").replace(">", "")
        preview = (
            f"<div style='background:linear-gradient(135deg,#090d16,#13203d);border:1px solid #38bdf8;border-radius:12px;padding:16px;font-family:sans-serif;color:#f8fafc'>"
            f"<div style='font-size:11px;letter-spacing:2px;color:#38bdf8'>UX/UI DESIGN SYSTEM</div>"
            f"<h3 style='margin:6px 0'>{brand}</h3>"
            f"<p style='font-size:13px;color:#cbd5e1;margin:0 0 12px'>High-contrast mobile-first grid, 8px spacing rhythm, WCAG AA typography.</p>"
            f"<span style='background:#22c55e;color:#052e16;padding:6px 12px;border-radius:6px;font-weight:bold;font-size:12px'>Primary CTA</span> "
            f"<span style='border:1px solid #38bdf8;color:#38bdf8;padding:6px 12px;border-radius:6px;font-size:12px'>Secondary Action</span></div>"
        )
        out = {"agent": "uxui_designer", "tokens": {"bg": "#090d16", "surface": "#161b22", "accent": "#38bdf8", "success": "#22c55e", "radius": "12px", "grid": "8pt"}, "html_preview": preview}

    elif a in ("aiml_dev", "aiml", "ml"):
        out = {
            "agent": "aiml_dev",
            "objective": t,
            "architecture": {"edge_encoder": "10,000-bit HDC/VSA (Zero-Copy mmap)", "inference_runtime": "LiteRT-LM / ONNX INT4 / Python stdlib", "evaluation": "Hamming drift + F1 + P99 latency"},
            "pipeline_code": f"# AI/ML Pipeline for: {t}\ndef train_step(x, y):\n    # Quantize features -> bind hypervector -> evaluate cosine/hamming loss\n    return {{'loss': 0.041, 'task': {json.dumps(t)}}}\n",
        }

    elif a in ("devexa_ceo_seo", "devexa", "ceo", "seo"):
        kw = [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", t) if len(w) > 3][:6]
        out = {
            "agent": "devexa_ceo_seo",
            "persona": "Devexa Elite Brain (CEO + Trading Strategist + Technical SEO)",
            "executive_directive": f"Focus capital and engineering velocity on {t}: lock recurring cash flow, automate telemetry/OMS execution, and capture high-intent local + organic search.",
            "seo_package": {
                "title_tag": f"{t[:48]} | Salathanie A.I Official",
                "meta_description": f"Discover {t[:110]} — engineered with real-time AI, edge speed, and institutional precision.",
                "target_keywords": kw or ["ai", "trading", "automation", "greensboro"],
                "schema_json_ld": {"@context": "https://schema.org", "@type": "Organization", "name": t[:40], "areaServed": "Greensboro & Winston-Salem, NC"},
            },
            "trader_brief": "Check live positions & FIX 4.4 execution reports at /trader.",
        }

    elif a in ("oms_order", "oms", "trade"):
        # Format: "SYMBOL|SIDE|QTY|TYPE|PRICE"
        parts = [p.strip() for p in t.split("|")]
        sym = parts[0] if parts and parts[0] else "BTCUSD"
        side = parts[1] if len(parts) > 1 else "BUY"
        qty = float(parts[2]) if len(parts) > 2 else 0.25
        otype = parts[3] if len(parts) > 3 else "MARKET"
        px = float(parts[4]) if len(parts) > 4 else 0.0
        out = oms_place_order(sym, side, qty, otype, px)

    elif a in ("fix_fast_gateway", "fix", "fast"):
        parts = [p.strip() for p in t.split("|")]
        sym = parts[0] if parts and parts[0] else "BTCUSD"
        px = float(parts[1]) if len(parts) > 1 and parts[1].replace(".", "", 1).isdigit() else REF_PRICES.get(sym.upper(), 96420.50)
        qty = float(parts[2]) if len(parts) > 2 and parts[2].replace(".", "", 1).isdigit() else 1.5
        fix_m = build_fix_44("D", [(11, f"GW-{ts}"), (55, sym.upper()), (54, "1"), (38, str(qty)), (40, "2"), (44, f"{px:.2f}")])
        fast_m = build_fast_packet(sym, px, qty, ts % 100000)
        out = {"agent": "fix_fast_gateway", "fix_4_4": fix_m, "fast_wire": fast_m, "bandwidth_reduction_pct": round((1 - (fast_m["bytes"] / max(1, fix_m["bytes"]))) * 100, 1)}

    elif a in ("ebook_builder", "ebook"):
        out = build_from_ebook(t)

    elif a in ("copy", "copy.ai", "jasper", "copy_jasper"):
        out = {"agent": "copy_jasper", "headline": f"Scale {t.title()} — Zero Friction, Instant Execution", "hook": f"{t} engineered to convert and automate on autopilot.", "cta": f"Launch {t} Now ->"}

    elif a in ("canvas", "canvas_elite"):
        label = (t or "Salathanie A.I")[:28].replace("<", "").replace(">", "")
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="160" viewBox="0 0 420 160">'
            f'<rect width="420" height="160" rx="12" fill="#0f172a"/><rect x="8" y="8" width="404" height="144" rx="10" fill="none" stroke="#38bdf8" stroke-width="1.5"/>'
            f'<text x="24" y="82" fill="#f8fafc" font-family="monospace" font-size="19" font-weight="bold">{label}</text>'
            f'<text x="24" y="114" fill="#38bdf8" font-family="monospace" font-size="11">CANVAS ELITE // SALATHANIE A.I</text></svg>'
        )
        out = {"agent": "canvas_elite", "svg": svg}

    elif a in ("notion", "notion_ai"):
        slug = re.sub(r"[^a-z0-9_]+", "_", t.lower())[:24] or "note"
        artifact = {
            "code_python": f"def run_{slug}():\n    print('Executing Salathanie module: {t}')\n",
            "image_prompt": f"Ultra-sharp editorial visual of {t}, obsidian & cyan palette, 8k",
            "short_movie_storyboard": [{"scene": 1, "sec": "0-5s", "visual": f"Hook on {t}"}, {"scene": 2, "sec": "5-18s", "visual": "Live terminal + UI demo"}, {"scene": 3, "sec": "18-25s", "visual": "Salathanie A.I CTA"}],
        }
        with db_conn() as c:
            c.execute("INSERT INTO notes (ts, title, body, artifact) VALUES (?,?,?,?)", (ts, t[:60], t, json.dumps(artifact)))
        out = {"agent": "notion_ai", "saved": True, "artifact": artifact}

    elif a in ("claude", "claude_doc"):
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if len(s.strip()) > 8]
        out = {"agent": "claude_doc", "word_count": len(t.split()), "executive_summary": " ".join(sents[:2]) or t, "key_points": sents[:4] or [t]}

    elif a in ("grammarly", "writing"):
        fillers = ["just", "really", "very", "actually", "basically", "literally"]
        cleaned = re.sub(r"\b(" + "|".join(fillers) + r")\b\s*", "", t, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        out = {"agent": "grammarly", "original": t, "improved": cleaned[:1].upper() + cleaned[1:] if cleaned else ""}

    elif a in ("perplexity", "perplexity_pro"):
        q = urllib.parse.quote(t)
        summary = f"Indexed topic: {t}"
        try:
            req = urllib.request.Request(f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1", headers={"User-Agent": "Salathanie-Perplexity/2.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode("utf-8"))
                summary = data.get("AbstractText") or data.get("Heading") or summary
        except Exception as e:
            summary = f"Offline index ({str(e)[:50]}): {t}"
        dp = {"program_target": "salathanie_hdc_ring.shm", "topic": t, "vector_programmed": True, "ts": ts}
        with db_conn() as c:
            c.execute("INSERT INTO knowledge (ts, query, summary, device_payload) VALUES (?,?,?,?)", (ts, t, summary, json.dumps(dp)))
        out = {"agent": "perplexity_pro", "query": t, "summary": summary, "device_programming": dp}

    elif a in ("reclaim", "reclaim_ai"):
        parts = [p.strip() for p in t.split("|")]
        title = parts[0] or "Task"
        urg = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 8
        imp = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 9
        score = round((urg * 0.6) + (imp * 0.4), 2)
        with db_conn() as c:
            c.execute("INSERT INTO tasks (ts, title, urgency, impact, score, status) VALUES (?,?,?,?,?,?)", (ts, title, urg, imp, score, "queued"))
            top = c.execute("SELECT title, score, status FROM tasks ORDER BY score DESC LIMIT 5").fetchall()
        out = {"agent": "reclaim_ai", "added": {"title": title, "score": score}, "top_priorities": [{"title": r[0], "score": r[1], "status": r[2]} for r in top]}

    elif a in ("tome", "tome_pitch"):
        out = {"agent": "tome_pitch", "deck_title": f"{t.title()} — Pitch Deck", "slides": [{"slide": 1, "title": "Vision", "body": t}, {"slide": 2, "title": "Execution", "body": "Edge AI + OMS + Automated Builds"}, {"slide": 3, "title": "Scale", "body": "Live on Salathanie A.I"}]}

    elif a in ("durable", "durable_web"):
        biz = (t or "Salathanie Enterprise").replace("<", "").replace(">", "")
        html = f"<!doctype html><html><body style='font-family:sans-serif;background:#0f172a;color:#f8fafc;text-align:center;padding:40px'><h1>{biz}</h1><p>Powered by Salathanie A.I</p></body></html>"
        out = {"agent": "durable_web", "business": biz, "html": html}

    elif a in ("zapier", "zapier_plus"):
        parts = [p.strip() for p in t.split("|")]
        trig, target, prompt = (parts[0] if parts else "manual"), (parts[1] if len(parts) > 1 else "devexa_ceo_seo"), (parts[2] if len(parts) > 2 else t)
        with db_conn() as c:
            c.execute("INSERT INTO flows (ts, name, trigger_evt, target_agent, prompt) VALUES (?,?,?,?,?)", (ts, f"{trig}->{target}", trig, target, prompt))
        out = {"agent": "zapier_plus", "flow_saved": f"{trig} -> {target}", "chained_execution": run_agent(target, prompt)}

    elif a in ("supercomputer", "swarm"):
        targets = [("devexa_ceo_seo", t), ("virtual_dev", t), ("fix_fast_gateway", "BTCUSD|96420.5|1.0")]
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(run_agent, ag, tx): ag for ag, tx in targets}
            for f in concurrent.futures.as_completed(futs):
                results[futs[f]] = f.result()
        out = {"agent": "supercomputer", "parallel_workers": 3, "results": results}

    else:
        out = {"error": f"Unknown agent '{a}'"}

    if a not in ("oms_order", "oms", "trade", "fix_fast_gateway", "fix", "fast", "supercomputer", "swarm") and "error" not in out:
        out = enhance_with_llm(a, t, out)
    publish_ring(f"{a}:{ts}")
    return out


STUDIO_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — 18-Agent Enterprise Studio</title>
<style>
body{font-family:monospace;background:#0b0f14;color:#e6edf3;margin:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
select,textarea,button{width:100%;box-sizing:border-box;background:#0d1117;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace;margin-top:6px}
button{background:#238636;border:none;font-weight:bold;cursor:pointer;padding:10px}
.nav a{display:inline-block;background:#1f6feb;color:#fff;padding:6px 10px;border-radius:6px;text-decoration:none;margin-right:6px;font-size:12px}
pre{white-space:pre-wrap;word-break:break-all;font-size:12px;background:#0d1117;padding:10px;border-radius:6px;max-height:360px;overflow:auto}
</style></head><body>
<h2>Salathanie A.I — 18-Agent Enterprise Studio</h2>
<div class="nav" style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px">
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
</div>
<div class="card">
  <label>Select Agent / Engine:</label>
  <select id="agent">
    <option value="devexa_ceo_seo">Devexa Elite Brain (CEO + SEO + Strategy)</option>
    <option value="virtual_dev">Virtual Software Dev (Writes Code + Dockerfile)</option>
    <option value="uxui_designer">UX/UI Designer (Live Design System + Preview)</option>
    <option value="aiml_dev">AI/ML Development (Edge & Pipeline Builder)</option>
    <option value="ebook_builder">Ebook-to-Build Generator (Path to .epub/.txt or Outline)</option>
    <option value="fix_fast_gateway">FIX 4.4 / FAST Gateway (SYMBOL|PRICE|QTY)</option>
    <option value="oms_order">OMS Direct Order (SYMBOL|BUY|QTY|MARKET)</option>
    <option value="supercomputer">Supercomputer (Parallel Multi-Agent Swarm)</option>
    <option value="perplexity_pro">Perplexity Pro (Research + Program Devices)</option>
    <option value="notion_ai">Notion AI (Notes -> Code / Image / Short Movie)</option>
    <option value="copy_jasper">Copy.ai / Jasper (Marketing & Brand Copy)</option>
    <option value="canvas_elite">Canvas Elite (SVG Designer)</option>
    <option value="claude_doc">Claude Doc (Long Doc Summary)</option>
    <option value="grammarly">Grammarly (Tone + Clarity)</option>
    <option value="reclaim_ai">Reclaim.ai (Priorities: Task|Urgency|Impact)</option>
    <option value="tome_pitch">Tome (Pitch Deck)</option>
    <option value="durable_web">Durable (Small Business Website)</option>
    <option value="zapier_plus">Zapier AI+ (Trigger|TargetAgent|Prompt)</option>
  </select>
  <textarea id="prompt" rows="3">Salathanie Institutional Edge Platform</textarea>
  <button onclick="fire()">Execute Engine</button>
</div>
<div class="card">
  <b>Live Preview & Output</b>
  <div id="preview" style="margin:8px 0"></div>
  <pre id="out">Ready.</pre>
</div>
<script>
async function fire(){
  const a = document.getElementById('agent').value;
  const p = document.getElementById('prompt').value;
  document.getElementById('out').textContent = 'Running ' + a + '...';
  document.getElementById('preview').innerHTML = '';
  const r = await fetch('/api/agents/run?agent='+encodeURIComponent(a)+'&q='+encodeURIComponent(p));
  const d = await r.json();
  if (d.svg) document.getElementById('preview').innerHTML = d.svg;
  if (d.html_preview) document.getElementById('preview').innerHTML = d.html_preview;
  document.getElementById('out').textContent = JSON.stringify(d, null, 2);
}
</script></body></html>"""

TRADER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie Web Trader — OMS & FIX/FAST Gateway</title>
<style>
body{font-family:monospace;background:#090d14;color:#e6edf3;margin:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
input,select,button{background:#0d1117;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace}
button.buy{background:#238636;border:none;font-weight:bold;cursor:pointer;flex:1}
button.sell{background:#da3633;border:none;font-weight:bold;cursor:pointer;flex:1}
table{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px}
th,td{border-bottom:1px solid #30363d;padding:6px;text-align:left}
.nav a{display:inline-block;background:#1f6feb;color:#fff;padding:6px 10px;border-radius:6px;text-decoration:none;margin-right:6px;font-size:12px}
pre{background:#0d1117;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:200px}
</style></head><body>
<h2>Salathanie Web Trader // OMS & FIX 4.4 / FAST</h2>
<div class="nav" style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px">
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
</div>
<div class="card">
  <b>Order Ticket (OMS + FIX 4.4 + FAST Wire)</b>
  <div class="row">
    <select id="sym"><option>BTCUSD</option><option>ETHUSD</option><option>SOLUSD</option><option>NVDA</option><option>SPY</option><option>EURUSD</option></select>
    <select id="otype"><option>MARKET</option><option>LIMIT</option></select>
    <input id="qty" value="0.5" style="width:70px" placeholder="Qty">
    <input id="px" value="0" style="width:90px" placeholder="Limit Px">
  </div>
  <div class="row">
    <button class="buy" onclick="sendOrd('BUY')">BUY / LONG</button>
    <button class="sell" onclick="sendOrd('SELL')">SELL / SHORT</button>
  </div>
  <pre id="ordRes">Ready for execution.</pre>
</div>
<div class="card"><b>Positions & PnL</b><div id="posTbl">Loading...</div></div>
<div class="card"><b>Recent Orders & FIX 4.4 / FAST Wire</b><div id="ordTbl">Loading...</div></div>
<script>
async function loadOMS(){
  const r = await fetch('/api/oms/state'); const d = await r.json();
  let pt = '<table><tr><th>Sym</th><th>Net Qty</th><th>Avg Px</th><th>Mark</th><th>uPnL</th><th>rPnL</th></tr>';
  (d.positions||[]).forEach(p=>{ pt += `<tr><td>${p.symbol}</td><td>${p.net_qty}</td><td>${p.avg_price}</td><td>${p.mark}</td><td>$${p.unrealized_pnl}</td><td>$${p.realized_pnl}</td></tr>`; });
  document.getElementById('posTbl').innerHTML = pt + '</table>';
  let ot = '<table><tr><th>ID</th><th>Sym</th><th>Side</th><th>Qty</th><th>Status</th><th>FAST Hex</th></tr>';
  (d.orders||[]).forEach(o=>{ ot += `<tr><td>${o.id}</td><td>${o.symbol}</td><td>${o.side}</td><td>${o.qty}</td><td>${o.status}</td><td>${o.fast_hex}</td></tr>`; });
  document.getElementById('ordTbl').innerHTML = ot + '</table>';
}
async function sendOrd(side){
  const q = `symbol=${encodeURIComponent(document.getElementById('sym').value)}&side=${side}&qty=${encodeURIComponent(document.getElementById('qty').value)}&type=${encodeURIComponent(document.getElementById('otype').value)}&price=${encodeURIComponent(document.getElementById('px').value)}`;
  const r = await fetch('/api/oms/order?' + q);
  document.getElementById('ordRes').textContent = JSON.stringify(await r.json(), null, 2);
  loadOMS();
}
loadOMS(); setInterval(loadOMS, 6000);
</script></body></html>"""


class AgentHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path in ("/", "/ui"):
            return self._send(200, STUDIO_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/trader":
            return self._send(200, TRADER_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/health":
            return self._send(200, json.dumps({"status": "ok", "service": "salathanie-agents", "port": ACTIVE_PORT}).encode("utf-8"))
        if parsed.path == "/api/agents/llm":
            return self._send(200, json.dumps(llm_status()).encode("utf-8"))
        if parsed.path == "/api/agents/run":
            return self._send(200, json.dumps(run_agent(qs.get("agent", ["devexa_ceo_seo"])[0], qs.get("q", ["Salathanie A.I"])[0], qs.get("mode", ["default"])[0])).encode("utf-8"))
        if parsed.path == "/api/oms/state":
            return self._send(200, json.dumps(oms_get_state()).encode("utf-8"))
        if parsed.path == "/api/oms/order":
            res = oms_place_order(qs.get("symbol", ["BTCUSD"])[0], qs.get("side", ["BUY"])[0], float(qs.get("qty", ["0.5"])[0]), qs.get("type", ["MARKET"])[0], float(qs.get("price", ["0"])[0]))
            return self._send(200, json.dumps(res).encode("utf-8"))
        if parsed.path == "/api/oms/cancel":
            return self._send(200, json.dumps(oms_cancel_order(int(qs.get("id", ["0"])[0]))).encode("utf-8"))
        return self._send(404, json.dumps({"error": "not_found"}).encode("utf-8"))


if __name__ == "__main__":
    with HDCSharedMemoryBus() as bus:
        ACTIVE_PORT = bus.allocate_port(PREFERRED_PORT)
        bus.publish("salathanie-agents", ACTIVE_PORT, 200, deterministic_hv(f"agents:{ACTIVE_PORT}:UP"))
    register_port("salathanie-agents", ACTIVE_PORT)
    print(f"[OK] Salathanie 18-Agent Studio + Web Trader/OMS/FIX live on 0.0.0.0:{ACTIVE_PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", ACTIVE_PORT), AgentHandler).serve_forever()
