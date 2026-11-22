#!/usr/bin/env python3
"""
Salathanie A.I — Offline Wikipedia ZIM & FTS5 Knowledge Grounding Engine
Feeds verified offline programming, mesh, Linux, Docker & STEM articles into
llm_bridge.py (18-Agents, 50 Codes, AI Scrintal, Teaching Hub, Creative Studio)
via local Kiwix-Serve (:8080) + SQLite FTS5 (salathanie_mesh_studio.db).
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "salathanie_mesh_studio.db"
ZIM_DIR = Path(os.getenv("SALATHANIE_ZIM_DIR", str(Path.home() / "kiwix")))
KIWIX_URL = os.getenv("KIWIX_URL", "http://127.0.0.1:8080").rstrip("/")

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "in", "on", "of", "with", "how",
    "what", "is", "are", "was", "were", "be", "can", "do", "does", "my", "your",
    "this", "that", "from", "into", "about", "using", "use", "make", "give", "me",
}

PROGRAMMING_TOPICS = [
    ("Python_(programming_language)", "Programming"),
    ("Bash_(Unix_shell)", "Programming"),
    ("Docker_(software)", "DevOps"),
    ("SQLite", "Database"),
    ("Raspberry_Pi", "Hardware"),
    ("Wireless_mesh_network", "Mesh"),
    ("B.A.T.M.A.N.", "Mesh"),
    ("Internet_protocol_suite", "Networking"),
    ("Kiwix", "OfflineWiki"),
    ("Linux", "Systems"),
    ("Git", "Programming"),
    ("LoRa", "Mesh"),
]


def extract_keywords(text: str, limit: int = 5) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_+#.-]{2,}", text.lower())
    seen, out = set(), []
    for w in words:
        w = w.strip(".-")
        if len(w) < 2 or w in STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def query_kiwix(keywords: list[str], max_hits: int = 2) -> list[dict]:
    """Query local kiwix-serve HTTP endpoint if a .zim file is being served on :8080."""
    if not keywords:
        return []
    pattern = urllib.parse.quote(" ".join(keywords[:3]))
    url = f"{KIWIX_URL}/search?pattern={pattern}&pageLength={max_hits}"
    try:
        with urllib.request.urlopen(url, timeout=1.2) as r:
            html = r.read().decode("utf-8", errors="ignore")
        hits = []
        for m in re.finditer(r'href="(/[^"]+)"[^>]*>([^<]{3,90})</a>', html):
            href, title = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
            if href.startswith("/content/") or "/A/" in href:
                hits.append({"source": "kiwix_zim", "title": title, "snippet": f"{KIWIX_URL}{href}"})
                if len(hits) >= max_hits:
                    break
        return hits
    except Exception:
        return []


def query_fts5(keywords: list[str], max_hits: int = 3) -> list[dict]:
    """Query local SQLite FTS5 offline knowledge vault."""
    if not DB_PATH.exists() or not keywords:
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=1.5)
        match_expr = " OR ".join(re.sub(r"[^a-z0-9_]", "", k) for k in keywords if re.sub(r"[^a-z0-9_]", "", k))
        if not match_expr:
            conn.close()
            return []
        rows = conn.execute(
            "SELECT a.title, a.category, a.body FROM wiki_fts f JOIN wiki_articles a ON a.id = f.rowid WHERE wiki_fts MATCH ? ORDER BY rank LIMIT ?",
            (match_expr, max_hits),
        ).fetchall()
        conn.close()
        return [{"source": "offline_fts5", "title": r[0], "category": r[1], "snippet": r[2][:420]} for r in rows]
    except Exception:
        return []


def build_grounded_context(query: str, max_chars: int = 1200) -> dict:
    """Return compact offline Wikipedia/ZIM passages ready to inject into any AI model."""
    kws = extract_keywords(query)
    hits = query_kiwix(kws, 2) + query_fts5(kws, 3)
    blocks = []
    used = 0
    for h in hits:
        line = f"[{h['source']}] {h['title']}: {h['snippet']}"
        if used + len(line) > max_chars:
            break
        blocks.append(line)
        used += len(line)
    return {"keywords": kws, "hits": len(blocks), "context": "\n".join(blocks)}


def seed_programming_pack() -> dict:
    """Fetch & permanently index core programming/mesh Wikipedia articles into local FTS5."""
    import salathanie_mesh_studio as mesh
    saved, skipped = [], []
    for slug, cat in PROGRAMMING_TOPICS:
        res = mesh.wiki_import_online(slug, cat)
        if res.get("ok"):
            saved.append(res["title"])
        else:
            skipped.append(slug)
    return {"ok": True, "saved_count": len(saved), "saved": saved, "skipped": skipped}


def resolve_latest_zim(flavor: str = "simple_mini") -> str:
    """Resolve the newest compact English Wikipedia .zim via Kiwix OPDS Catalog v2 + directory fallback."""
    hints = {
        "simple_mini": ("simple", "mini"),
        "simple_nopic": ("simple", "nopic"),
        "top_mini": ("top", "mini"),
        "top_nopic": ("top", "nopic"),
    }
    kw1, kw2 = hints.get(flavor, ("simple", "mini"))
    # 1. Official Kiwix OPDS Catalog v2
    try:
        cat_url = f"https://library.kiwix.org/catalog/v2/entries?lang=eng&category=wikipedia&q={kw1}&count=40"
        req = urllib.request.Request(cat_url, headers={"User-Agent": "SalathanieAI-KiwixFetcher/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            xml = r.read().decode("utf-8", errors="ignore")
        links = re.findall(r'href="(https://download\.kiwix\.org/zim/[^"]+\.zim(?:\.meta4)?)"', xml)
        cleaned = sorted(set(u[:-6] if u.endswith(".meta4") else u for u in links))
        exact = [u for u in cleaned if kw1 in u.lower() and kw2 in u.lower()]
        if exact:
            return exact[-1]
        mini_any = [u for u in cleaned if "mini" in u.lower() or "100" in u.lower()]
        if mini_any:
            return mini_any[-1]
    except Exception:
        pass

    # 2. Direct directory index fallback (flexible filename matching)
    index_url = "https://download.kiwix.org/zim/wikipedia/"
    req = urllib.request.Request(index_url, headers={"User-Agent": "SalathanieAI-KiwixFetcher/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="ignore")
    all_en = sorted(set(re.findall(r'wikipedia_en_[A-Za-z0-9_.-]+\.zim', html)))
    for pred in (
        lambda fn: kw1 in fn and kw2 in fn,
        lambda fn: "simple" in fn and ("mini" in fn or "nopic" in fn),
        lambda fn: "100_" in fn and "mini" in fn,
        lambda fn: "_mini_" in fn,
    ):
        hits = [fn for fn in all_en if pred(fn)]
        if hits:
            return f"{index_url}{hits[-1]}"
    raise RuntimeError(f"No compact English Wikipedia ZIM found (saw {len(all_en)} files at {index_url})")


def download_zim(flavor: str = "simple_mini") -> dict:
    ZIM_DIR.mkdir(parents=True, exist_ok=True)
    url = resolve_latest_zim(flavor)
    fname = url.rsplit("/", 1)[-1]
    dest = ZIM_DIR / fname
    print(f"[ZIM] Downloading {url} -> {dest} (resumable)")
    r = subprocess.run(["curl", "-L", "-C", "-", "-o", str(dest), url])
    if r.returncode != 0:
        return {"ok": False, "url": url, "error": f"curl exited {r.returncode}"}
    size_mb = round(dest.stat().st_size / (1024 * 1024), 1)
    return {"ok": True, "file": str(dest), "size_mb": size_mb}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Offline Wikipedia ZIM & FTS5 RAG engine for Salathanie models")
    p.add_argument("--seed-programming", action="store_true", help="Cache core programming/mesh Wikipedia articles into FTS5")
    p.add_argument("--download-zim", choices=["simple_mini", "simple_nopic", "top_mini", "top_nopic"], help="Download latest compact Wikipedia .zim into ~/kiwix/")
    p.add_argument("--query", help="Test offline model grounding retrieval")
    args = p.parse_args()
    if args.seed_programming:
        print(json.dumps(seed_programming_pack(), indent=2))
    if args.download_zim:
        print(json.dumps(download_zim(args.download_zim), indent=2))
    if args.query:
        print(json.dumps(build_grounded_context(args.query), indent=2))
