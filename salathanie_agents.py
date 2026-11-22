#!/usr/bin/env python3
"""
Salathanie A.I — Unified 11-Agent Studio & Automation Core (:8127)
Pure stdlib + SQLite WAL + HDC Ring integration (~10MB RAM).
"""
import concurrent.futures
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "salathanie_agents.db"
PREFERRED_PORT = 8127
ACTIVE_PORT = PREFERRED_PORT


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, ts INT, title TEXT, body TEXT, artifact TEXT);
        CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, ts INT, title TEXT, urgency INT, impact INT, score REAL, status TEXT);
        CREATE TABLE IF NOT EXISTS flows (id INTEGER PRIMARY KEY, ts INT, name TEXT, trigger_evt TEXT, target_agent TEXT, prompt TEXT);
        CREATE TABLE IF NOT EXISTS knowledge (id INTEGER PRIMARY KEY, ts INT, query TEXT, summary TEXT, device_payload TEXT);
    """)
    return conn


def publish_ring(tag: str):
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-agents", ACTIVE_PORT, 200, deterministic_hv(f"agent:{tag}"))
    except Exception:
        pass


def run_agent(agent: str, text: str, mode: str = "default") -> dict:
    a = agent.lower().strip()
    t = text.strip()
    ts = int(time.time())

    if a in ("copy", "copy.ai", "jasper"):
        out = {
            "agent": "copy_jasper",
            "headline": f"Unlock Next-Level {t.title()} — Built for Speed & Scale",
            "hook": f"Stop wasting time on slow tools. {t} delivers instant results with zero friction.",
            "cta": f"Launch {t} Today ->",
            "social_post": f"Just leveled up with {t}. Built lean, runs fast, scales anywhere. #SalathanieAI",
        }

    elif a in ("canvas", "canvas_elite"):
        label = (t or "Salathanie A.I")[:28].replace("<", "").replace(">", "")
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="180" viewBox="0 0 420 180">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1d4ed8"/></linearGradient></defs>'
            f'<rect width="420" height="180" rx="14" fill="url(#g)"/>'
            f'<circle cx="360" cy="45" r="28" fill="#38bdf8" opacity="0.25"/>'
            f'<text x="24" y="88" fill="#f8fafc" font-family="monospace" font-size="20" font-weight="bold">{label}</text>'
            f'<text x="24" y="122" fill="#93c5fd" font-family="monospace" font-size="12">CANVAS ELITE // SALATHANIE A.I</text></svg>'
        )
        out = {"agent": "canvas_elite", "svg": svg, "theme": mode}

    elif a in ("notion", "notion_ai"):
        slug = re.sub(r"[^a-z0-9_]+", "_", t.lower())[:24] or "note"
        artifact = {
            "code_python": f"def run_{slug}():\n    print('Executing Salathanie module: {t}')\n\nif __name__ == '__main__':\n    run_{slug}()",
            "image_prompt": f"Ultra-sharp cinematic concept art of {t}, high contrast, studio lighting, 8k",
            "short_movie_storyboard": [
                {"scene": 1, "sec": "0-5s", "visual": f"Fast zoom into {t}", "voiceover": f"Everything changes with {t}."},
                {"scene": 2, "sec": "5-15s", "visual": "Live telemetry & action montage", "voiceover": "Built lean from the ground up."},
                {"scene": 3, "sec": "15-25s", "visual": "Logo lockup + CTA", "voiceover": "Salathanie A.I — live now."},
            ],
        }
        with db_conn() as c:
            c.execute("INSERT INTO notes (ts, title, body, artifact) VALUES (?,?,?,?)", (ts, t[:60], t, json.dumps(artifact)))
        out = {"agent": "notion_ai", "saved": True, "artifact": artifact}

    elif a in ("claude", "claude_doc"):
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if len(s.strip()) > 10]
        words = len(t.split())
        key_pts = sents[:3] if sents else [t]
        out = {
            "agent": "claude_doc",
            "word_count": words,
            "read_time_min": round(max(0.2, words / 200.0), 1),
            "executive_summary": " ".join(key_pts[:2]),
            "key_points": key_pts,
        }

    elif a in ("grammarly", "writing"):
        fillers = ["just", "really", "very", "actually", "basically", "literally"]
        cleaned = re.sub(r"\b(" + "|".join(fillers) + r")\b\s*", "", t, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        out = {
            "agent": "grammarly",
            "tone": mode if mode != "default" else "clear_executive",
            "original": t,
            "improved": cleaned[:1].upper() + cleaned[1:] if cleaned else "",
            "fillers_removed": sum(len(re.findall(rf"\b{f}\b", t, re.I)) for f in fillers),
        }

    elif a in ("perplexity", "perplexity_pro"):
        q = urllib.parse.quote(t)
        summary = f"Local knowledge indexed for: {t}"
        try:
            url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Salathanie-Perplexity/1.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode("utf-8"))
                summary = data.get("AbstractText") or data.get("Heading") or summary
        except Exception as e:
            summary = f"Offline mode ({str(e)[:60]}): indexed '{t}'"
        device_payload = {"program_target": "salathanie_hdc_ring.shm", "topic": t, "vector_programmed": True, "ts": ts}
        with db_conn() as c:
            c.execute("INSERT INTO knowledge (ts, query, summary, device_payload) VALUES (?,?,?,?)", (ts, t, summary, json.dumps(device_payload)))
        out = {"agent": "perplexity_pro", "query": t, "summary": summary, "device_programming": device_payload}

    elif a in ("reclaim", "reclaim_ai"):
        parts = [p.strip() for p in t.split("|")]
        title = parts[0] or "Unnamed Task"
        urg = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 8
        imp = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 9
        score = round((urg * 0.6) + (imp * 0.4), 2)
        with db_conn() as c:
            c.execute("INSERT INTO tasks (ts, title, urgency, impact, score, status) VALUES (?,?,?,?,?,?)", (ts, title, urg, imp, score, "queued"))
            top = c.execute("SELECT title, score, status FROM tasks ORDER BY score DESC LIMIT 5").fetchall()
        out = {"agent": "reclaim_ai", "added": {"title": title, "score": score}, "top_priorities": [{"title": r[0], "score": r[1], "status": r[2]} for r in top]}

    elif a in ("tome", "tome_pitch"):
        out = {
            "agent": "tome_pitch",
            "deck_title": f"{t.title()} — Investor & Vision Pitch",
            "slides": [
                {"slide": 1, "title": "The Vision", "body": f"Redefining {t} with autonomous edge AI."},
                {"slide": 2, "title": "The Problem", "body": "Legacy workflows are fragmented, heavy, and expensive."},
                {"slide": 3, "title": "The Solution", "body": f"{t} unified on Salathanie A.I with real-time telemetry."},
                {"slide": 4, "title": "Next Milestone", "body": "Scale deployment across mobile, web, and edge nodes."},
            ],
        }

    elif a in ("durable", "durable_web"):
        biz = (t or "Salathanie Enterprise").replace("<", "").replace(">", "")
        html = (
            f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{biz}</title><style>body{{font-family:sans-serif;margin:0;background:#0f172a;color:#f8fafc;text-align:center}}"
            f".hero{{padding:60px 20px;background:linear-gradient(135deg,#1e3a8a,#0f172a)}}.btn{{background:#22c55e;color:#052e16;padding:12px 24px;"
            f"border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:16px}}</style></head>"
            f"<body><div class='hero'><h1>{biz}</h1><p>Fast, reliable local service powered by Salathanie A.I.</p>"
            f"<a class='btn' href='#contact'>Book Now</a></div><div id='contact' style='padding:40px'><h2>Contact Us</h2>"
            f"<p>Serving Greensboro & Winston-Salem, NC</p></div></body></html>"
        )
        out = {"agent": "durable_web", "business": biz, "html_length": len(html), "html": html}

    elif a in ("zapier", "zapier_plus"):
        # Format: "trigger_name|target_agent|prompt"
        parts = [p.strip() for p in t.split("|")]
        trig = parts[0] if parts and parts[0] else "manual"
        target = parts[1] if len(parts) > 1 else "notion_ai"
        prompt = parts[2] if len(parts) > 2 else t
        with db_conn() as c:
            c.execute("INSERT INTO flows (ts, name, trigger_evt, target_agent, prompt) VALUES (?,?,?,?,?)", (ts, f"{trig}->{target}", trig, target, prompt))
        chained = run_agent(target, prompt)
        out = {"agent": "zapier_plus", "flow_saved": f"{trig} -> {target}", "chained_execution": chained}

    elif a in ("supercomputer", "swarm"):
        # Runs 3 agents in parallel safely (capped at 3 threads for Android RAM)
        targets = [("perplexity_pro", t), ("tome_pitch", t), ("copy_jasper", t)]
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(run_agent, ag, tx): ag for ag, tx in targets}
            for f in concurrent.futures.as_completed(futs):
                results[futs[f]] = f.result()
        out = {"agent": "supercomputer", "parallel_workers": 3, "results": results}

    else:
        out = {"error": f"Unknown agent '{a}'", "available": ["supercomputer", "copy_jasper", "canvas_elite", "notion_ai", "claude_doc", "grammarly", "perplexity_pro", "reclaim_ai", "tome_pitch", "durable_web", "zapier_plus"]}

    publish_ring(f"{a}:{ts}")
    return out


UI_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — 11-Agent Studio</title>
<style>
body{font-family:monospace;background:#0b0f14;color:#e6edf3;margin:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
select,textarea,button{width:100%;box-sizing:border-box;background:#0d1117;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace;margin-top:6px}
button{background:#238636;border:none;font-weight:bold;cursor:pointer;padding:10px}
pre{white-space:pre-wrap;word-break:break-all;font-size:12px;background:#0d1117;padding:10px;border-radius:6px;max-height:360px;overflow:auto}
</style></head><body>
<h2>Salathanie A.I — 11-Agent Studio</h2>
<div class="card">
  <label>Select Agent / Add-On:</label>
  <select id="agent">
    <option value="supercomputer">Supercomputer (Parallel Multi-Agent Swarm)</option>
    <option value="perplexity_pro">Perplexity Pro (Research + Program Devices)</option>
    <option value="notion_ai">Notion AI (Notes -> Code / Image / Short Movie)</option>
    <option value="copy_jasper">Copy.ai / Jasper (Marketing & Brand Copy)</option>
    <option value="canvas_elite">Canvas Elite (SVG Visual Designer)</option>
    <option value="claude_doc">Claude Doc (Long Document Summary)</option>
    <option value="grammarly">Grammarly (Tone + Clarity Assistant)</option>
    <option value="reclaim_ai">Reclaim.ai (Task Priorities: Task|Urgency|Impact)</option>
    <option value="tome_pitch">Tome (AI Storytelling & Pitch Deck)</option>
    <option value="durable_web">Durable (Small Business AI Website)</option>
    <option value="zapier_plus">Zapier AI+ (Trigger|TargetAgent|Prompt)</option>
  </select>
  <textarea id="prompt" rows="3" placeholder="Enter topic, document, task, or workflow...">Salathanie Mobile Mechanic & Lawn Care</textarea>
  <button onclick="fire()">Run Agent</button>
</div>
<div class="card">
  <b>Live Output / Preview</b>
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
  document.getElementById('out').textContent = JSON.stringify(d, null, 2);
}
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
        if parsed.path in ("/", "/ui"):
            return self._send(200, UI_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if parsed.path == "/health":
            return self._send(200, json.dumps({"status": "ok", "service": "salathanie-agents", "port": ACTIVE_PORT}).encode("utf-8"))
        if parsed.path == "/api/agents/run":
            qs = urllib.parse.parse_qs(parsed.query)
            agent = qs.get("agent", ["supercomputer"])[0]
            q = qs.get("q", ["Salathanie A.I"])[0]
            mode = qs.get("mode", ["default"])[0]
            return self._send(200, json.dumps(run_agent(agent, q, mode)).encode("utf-8"))
        return self._send(404, json.dumps({"error": "not_found"}).encode("utf-8"))


if __name__ == "__main__":
    with HDCSharedMemoryBus() as bus:
        ACTIVE_PORT = bus.allocate_port(PREFERRED_PORT)
        bus.publish("salathanie-agents", ACTIVE_PORT, 200, deterministic_hv(f"agents:{ACTIVE_PORT}:UP"))
    print(f"[OK] Salathanie 11-Agent Studio live on 0.0.0.0:{ACTIVE_PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", ACTIVE_PORT), AgentHandler).serve_forever()
