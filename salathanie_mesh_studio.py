#!/usr/bin/env python3
"""
Salathanie A.I — Digital Divide, DIY Mesh, Offline Wikipedia (FTS5 + Kiwix),
Raspberry Pi 5 Provisioner, Teaching Access Tools, iPad Broadcast Studio & AI Scrintal.
Zero extra PM2 processes: mounted directly into universal_pilot.py (:8125).
"""
import json
import os
import re
import socket
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv
from llm_bridge import enhance_with_llm

REPO = Path("/data/data/com.termux/files/home/live-command-center")
DB_PATH = REPO / "salathanie_mesh_studio.db"
MESH_OUT = REPO / "builds" / "mesh"
BCAST_OUT = REPO / "builds" / "broadcast"
HOME = Path.home()

SEED_WIKI = [
    (
        "DIY Community Mesh Networking (BATMAN-adv & Wi-Fi)",
        "Mesh",
        "A DIY mesh network lets neighbors, classrooms, and field devices connect directly peer-to-peer without depending on a commercial ISP. "
        "Layer-2 routing with BATMAN-adv (bat0) automatically discovers multi-hop routes and heals around downed nodes. "
        "Core stack: (1) 802.11s mesh interface on each Raspberry Pi 5 or OpenWrt router, (2) batctl meshif bat0 interface add mesh0, "
        "(3) Local DHCP/DNS via dnsmasq so any phone or iPad gets an IP offline, (4) Optional gateway uplink shared across all mesh hops.",
        "seed_offline",
    ),
    (
        "Self-Reconnecting Mesh & Edge Watchdog Protocol",
        "Reconnect",
        "To survive power drops, Wi-Fi handoffs, or ISP blackouts, every edge node runs a 3-tier self-reconnection loop: "
        "Tier 1 checks local LAN gateway and loopback services (ports 8125/8126/8090/8182). "
        "Tier 2 checks upstream DNS (1.1.1.1) and restarts the tunnel or mesh interface only when uplink returns. "
        "Tier 3 switches seamlessly to Local-First Offline Mode (Offline Wikipedia FTS5 + Classroom Hub + Scrintal) so users never lose access.",
        "seed_offline",
    ),
    (
        "Raspberry Pi 5 Offline Community Node & Kiwix Server",
        "Pi5",
        "Raspberry Pi 5 (quad-core Cortex-A76, 4GB/8GB RAM, PCIe NVMe/microSD) can serve 30+ simultaneous learners completely offline. "
        "Install hostapd + dnsmasq for a local Wi-Fi AP (SSID: Salathanie-Mesh-Edu), mount an NVMe or 128GB microSD holding Kiwix .zim dumps "
        "(wikipedia_en_top_nopic.zim, gutenberg, khan academy), run kiwix-serve on port 8080, and bridge BATMAN-adv on a USB Wi-Fi adapter for multi-hop coverage.",
        "seed_offline",
    ),
    (
        "Bridging the Digital Divide — Zero-Data Teaching Access",
        "Teaching",
        "Effective digital-divide teaching labs remove data-plan barriers by hosting interactive lessons, quizzes, coding sandboxes, and Offline Wikipedia on local LAN/mesh. "
        "Accessibility essentials: high-contrast themes, dyslexia-friendly letter spacing, large tap targets for tablets/iPads, and browser-native Text-to-Speech (Web Speech API) that works 100% offline.",
        "seed_offline",
    ),
    (
        "iPad as a Portable Broadcast & Teaching Studio",
        "Broadcast",
        "An iPad on the same LAN or mesh AP acts as a zero-cable production switcher: capture rear/front camera and USB-C mic via browser WebRTC, "
        "overlay real-time lower-third chyrons and lesson tickers onto an HTML5 Canvas, monitor mic peaks with a Web Audio VU meter, read from an on-screen teleprompter, "
        "record local MP4/WebM episodes, or push RTMP/SRT into OBS Studio or a community stream.",
        "seed_offline",
    ),
    (
        "Meshtastic & LoRa Long-Range Emergency Reconnection",
        "Mesh",
        "When Wi-Fi range (~100m) is exceeded, 915 MHz LoRa radios (Meshtastic on Heltec/T-Beam/RAK nodes) transmit telemetry, GPS pins, and text relays 3-15 km line-of-sight on milliwatts of solar power. "
        "Pair a LoRa node over USB-serial or BLE to Raspberry Pi 5 or Android Termux to broadcast emergency status and reconnect coordinates when cellular towers are down.",
        "seed_offline",
    ),
]

SEED_CARDS = [
    ("CARD-1", "Digital Divide Mission", "Bring zero-data offline Wikipedia, STEM lessons, and peer-to-peer mesh internet to underserved neighborhoods and youth gyms.", "Teaching", 40, 40, "#0ea5e9"),
    ("CARD-2", "Raspberry Pi 5 Mesh Hub", "802.11s + BATMAN-adv + hostapd AP + Kiwix .zim offline Wikipedia + Kolibri classroom server.", "Pi5", 300, 40, "#22c55e"),
    ("CARD-3", "Self-Reconnection Watchdog", "Auto-heals Wi-Fi/mesh links, checks local ports, and keeps Offline Mode running with zero downtime.", "Mesh", 40, 220, "#f59e0b"),
    ("CARD-4", "iPad Broadcast Studio", "Live camera + lower-third chyrons + teleprompter + local recording for teaching and community broadcasts.", "Broadcast", 300, 220, "#ec4899"),
]
SEED_LINKS = [("CARD-1", "CARD-2", "deploys on"), ("CARD-2", "CARD-3", "healed by"), ("CARD-1", "CARD-4", "broadcast via")]


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wiki_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            category TEXT,
            body TEXT,
            source TEXT,
            ts INT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(title, category, body, content='wiki_articles', content_rowid='id');
        CREATE TRIGGER IF NOT EXISTS wiki_ai AFTER INSERT ON wiki_articles BEGIN
            INSERT INTO wiki_fts(rowid, title, category, body) VALUES (new.id, new.title, new.category, new.body);
        END;
        CREATE TRIGGER IF NOT EXISTS wiki_ad AFTER DELETE ON wiki_articles BEGIN
            INSERT INTO wiki_fts(wiki_fts, rowid, title, category, body) VALUES('delete', old.id, old.title, old.category, old.body);
        END;
        CREATE TRIGGER IF NOT EXISTS wiki_au AFTER UPDATE ON wiki_articles BEGIN
            INSERT INTO wiki_fts(wiki_fts, rowid, title, category, body) VALUES('delete', old.id, old.title, old.category, old.body);
            INSERT INTO wiki_fts(rowid, title, category, body) VALUES (new.id, new.title, new.category, new.body);
        END;

        CREATE TABLE IF NOT EXISTS teaching_lessons (
            lesson_id TEXT PRIMARY KEY,
            title TEXT,
            level TEXT,
            body TEXT,
            quiz_json TEXT,
            ts INT
        );

        CREATE TABLE IF NOT EXISTS scrintal_cards (
            card_id TEXT PRIMARY KEY,
            title TEXT,
            body TEXT,
            tag TEXT,
            x REAL,
            y REAL,
            color TEXT,
            ts INT
        );
        CREATE TABLE IF NOT EXISTS scrintal_links (
            src TEXT,
            dst TEXT,
            label TEXT,
            PRIMARY KEY (src, dst)
        );
    """)
    ts = int(time.time())
    if conn.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0] == 0:
        for title, cat, body, src in SEED_WIKI:
            conn.execute("INSERT OR IGNORE INTO wiki_articles(title,category,body,source,ts) VALUES (?,?,?,?,?)", (title, cat, body, src, ts))
    if conn.execute("SELECT COUNT(*) FROM scrintal_cards").fetchone()[0] == 0:
        for cid, title, body, tag, x, y, col in SEED_CARDS:
            conn.execute("INSERT OR IGNORE INTO scrintal_cards VALUES (?,?,?,?,?,?,?,?)", (cid, title, body, tag, x, y, col, ts))
        for s, d, lbl in SEED_LINKS:
            conn.execute("INSERT OR IGNORE INTO scrintal_links VALUES (?,?,?)", (s, d, lbl))
    if conn.execute("SELECT COUNT(*) FROM teaching_lessons").fetchone()[0] == 0:
        conn.execute(
            "INSERT OR IGNORE INTO teaching_lessons VALUES (?,?,?,?,?,?)",
            (
                "LES-001",
                "Build a Community Mesh Node in 30 Minutes",
                "Beginner",
                "1. Flash Raspberry Pi OS Lite 64-bit onto a Pi 5.\n2. Run pi5_community_mesh.sh to enable BATMAN-adv mesh and local Wi-Fi AP.\n3. Copy an offline Wikipedia .zim file into /srv/kiwix.\n4. Connect any phone, tablet, or iPad to Salathanie-Mesh-Edu with zero cell data required.",
                json.dumps([
                    {"q": "Which layer-2 protocol lets Pi 5 mesh nodes auto-route around dead links?", "a": "BATMAN-adv (bat0)"},
                    {"q": "Which file format stores full Offline Wikipedia for Kiwix?", "a": ".zim archive"},
                ]),
                ts,
            ),
        )
    return conn


def _pub_ring(tag: str):
    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-mesh-hub", 8125, 200, deterministic_hv(f"mesh:{tag}"))
    except Exception:
        pass


# =====================================================================
# 1. LIVE MESH DIAGNOSTICS + PI 5 & SELF-RECONNECT SCRIPT GENERATORS
# =====================================================================
def mesh_diagnostics() -> dict:
    lan_ip = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            lan_ip = s.getsockname()[0]
    except Exception:
        pass

    internet_ok = False
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=1.5):
            internet_ok = True
    except Exception:
        pass

    ports = {}
    for p in (8090, 8125, 8126, 8151, 8182, 8080):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.12)
            ports[str(p)] = (s.connect_ex(("127.0.0.1", p)) == 0)

    zim_files = []
    for folder in (HOME / "kiwix", REPO / "zim", HOME / "storage" / "shared" / "Download"):
        if folder.exists():
            try:
                for z in folder.glob("*.zim"):
                    zim_files.append({"name": z.name, "size_mb": round(z.stat().st_size / (1024 * 1024), 1), "path": str(z)})
            except OSError:
                pass

    with db_conn() as c:
        wiki_cnt = c.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0]
        lesson_cnt = c.execute("SELECT COUNT(*) FROM teaching_lessons").fetchone()[0]
        card_cnt = c.execute("SELECT COUNT(*) FROM scrintal_cards").fetchone()[0]

    return {
        "ts": int(time.time()),
        "lan_ip": lan_ip,
        "ipad_studio_url": f"http://{lan_ip}:8125/broadcast",
        "classroom_lan_url": f"http://{lan_ip}:8125/mesh-hub",
        "scrintal_lan_url": f"http://{lan_ip}:8125/scrintal",
        "internet_uplink": internet_ok,
        "mode": "HYBRID_ONLINE_MESH" if internet_ok else "OFFLINE_SOVEREIGN_MESH",
        "mesh_ports": ports,
        "wiki_articles_offline": wiki_cnt,
        "teaching_lessons": lesson_cnt,
        "scrintal_cards": card_cnt,
        "kiwix_zims_found": zim_files,
    }


def generate_pi5_mesh_script(ssid: str = "Salathanie-Mesh-Edu", mesh_id: str = "salathanie-mesh", channel: int = 6) -> dict:
    MESH_OUT.mkdir(parents=True, exist_ok=True)
    safe_ssid = re.sub(r"[^A-Za-z0-9_-]", "", ssid) or "Salathanie-Mesh-Edu"
    safe_mesh = re.sub(r"[^A-Za-z0-9_-]", "", mesh_id) or "salathanie-mesh"
    ch = max(1, min(int(channel or 6), 11))
    script = f"""#!/usr/bin/env bash
# Salathanie A.I — Raspberry Pi 5 Digital Divide Community Mesh + Offline Wikipedia Provisioner
set -euo pipefail

echo "[1/5] Installing BATMAN-adv Mesh, Community AP, Kiwix Offline Wikipedia & Docker..."
sudo apt-get update
sudo apt-get install -y batctl hostapd dnsmasq kiwix-tools curl avahi-daemon python3-pip

echo "[2/5] Enabling batman-adv kernel module..."
sudo modprobe batman-adv
grep -qxF "batman-adv" /etc/modules || echo "batman-adv" | sudo tee -a /etc/modules

echo "[3/5] Configuring local offline DHCP/DNS captive portal (10.77.0.1/24)..."
sudo tee /etc/dnsmasq.d/salathanie-mesh.conf > /dev/null << 'DNSEOF'
interface=wlan0
dhcp-range=10.77.0.10,10.77.0.200,255.255.255.0,12h
address=/salathanie.local/10.77.0.1
address=/wiki.local/10.77.0.1
DNSEOF

echo "[4/5] Preparing Kiwix Offline Wikipedia directory (/srv/kiwix)..."
sudo mkdir -p /srv/kiwix
cat << 'SVC' | sudo tee /etc/systemd/system/salathanie-kiwix.service > /dev/null
[Unit]
Description=Salathanie Offline Wikipedia (Kiwix Serve)
After=network.target

[Service]
ExecStart=/bin/sh -c 'ls /srv/kiwix/*.zim >/dev/null 2>&1 && exec /usr/bin/kiwix-serve --port=8080 /srv/kiwix/*.zim || sleep infinity'
Restart=always

[Install]
WantedBy=multi-user.target
SVC

echo "[5/5] Installing Self-Reconnection Mesh Watchdog (/usr/local/bin/mesh-heal.sh)..."
cat << 'HEAL' | sudo tee /usr/local/bin/mesh-heal.sh > /dev/null
#!/usr/bin/env bash
MESH_ID="{safe_mesh}"
if ip link show wlan1 >/dev/null 2>&1; then
  if ! batctl if | grep -q wlan1; then
    sudo ip link set wlan1 down
    sudo iw dev wlan1 set type mp
    sudo ip link set wlan1 up
    sudo iw dev wlan1 mesh join "$MESH_ID" freq 2437
    sudo batctl if add wlan1
    sudo ip link set bat0 up
  fi
fi
systemctl is-active --quiet dnsmasq || sudo systemctl restart dnsmasq
HEAL
sudo chmod +x /usr/local/bin/mesh-heal.sh
(crontab -l 2>/dev/null | grep -v mesh-heal.sh; echo "*/2 * * * * /usr/local/bin/mesh-heal.sh") | crontab -

sudo systemctl daemon-reload
sudo systemctl enable --now salathanie-kiwix.service
echo "[OK] Raspberry Pi 5 Node ready! Drop any Wikipedia .zim into /srv/kiwix and open http://10.77.0.1:8080 (SSID: {safe_ssid}, Channel: {ch})"
"""
    fp = MESH_OUT / "pi5_community_mesh.sh"
    fp.write_text(script, encoding="utf-8")
    os.chmod(fp, 0o755)
    _pub_ring("pi5_script_generated")
    return {"ok": True, "path": str(fp), "ssid": safe_ssid, "mesh_id": safe_mesh, "script": script}


def generate_termux_reconnect_script() -> dict:
    MESH_OUT.mkdir(parents=True, exist_ok=True)
    script = """#!/data/data/com.termux/files/usr/bin/bash
# Salathanie A.I — Termux Self-Reconnection & Offline Fallback Watchdog
set -u
LOG="$HOME/live-command-center/builds/mesh/reconnect.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

# 1. Verify local Universal Pilot (:8125)
if ! curl -sf --max-time 3 http://127.0.0.1:8125/api/pilot/status >/dev/null; then
  echo "[$TS] Pilot :8125 unresponsive -> restarting salathanie-pilot" >> "$LOG"
  pm2 restart salathanie-pilot >/dev/null 2>&1 || true
fi

# 2. Check uplink; if online verify tunnel, if offline stay cleanly in Sovereign Offline Mesh mode
if curl -sf --max-time 4 https://1.1.1.1 >/dev/null 2>&1; then
  TURL=$(grep -hoE "https://[a-zA-Z0-9.-]+\\.trycloudflare\\.com" ~/.pm2/logs/salathanie-tunnel-*.log 2>/dev/null | tail -n 1)
  if [ -n "$TURL" ]; then
    CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 "$TURL/mesh-hub")
    if [ "$CODE" != "200" ]; then
      echo "[$TS] Tunnel HTTP $CODE -> recycling salathanie-tunnel (HTTP/2)" >> "$LOG"
      pm2 restart salathanie-tunnel >/dev/null 2>&1 || true
    fi
  fi
else
  echo "[$TS] No WAN uplink -> holding Offline Sovereign Mesh & Wikipedia FTS5 on :8125" >> "$LOG"
fi
"""
    fp = MESH_OUT / "termux_self_reconnect.sh"
    fp.write_text(script, encoding="utf-8")
    os.chmod(fp, 0o755)
    return {"ok": True, "path": str(fp), "script": script}


# =====================================================================
# 2. OFFLINE WIKIPEDIA FTS5 SEARCH & LIVE-TO-OFFLINE IMPORTER
# =====================================================================
def wiki_search(q: str = "") -> dict:
    q = q.strip()
    with db_conn() as c:
        if not q:
            rows = c.execute("SELECT id, title, category, body, source, ts FROM wiki_articles ORDER BY ts DESC LIMIT 25").fetchall()
        else:
            safe_q = re.sub(r'["\'*]', " ", q).strip()
            try:
                rows = c.execute(
                    "SELECT a.id, a.title, a.category, a.body, a.source, a.ts FROM wiki_fts f JOIN wiki_articles a ON a.id = f.rowid WHERE wiki_fts MATCH ? ORDER BY rank LIMIT 20",
                    (safe_q,),
                ).fetchall()
            except Exception:
                like = f"%{q.lower()}%"
                rows = c.execute(
                    "SELECT id, title, category, body, source, ts FROM wiki_articles WHERE lower(title) LIKE ? OR lower(body) LIKE ? LIMIT 20",
                    (like, like),
                ).fetchall()
    return {
        "ok": True,
        "query": q,
        "count": len(rows),
        "articles": [{"id": r[0], "title": r[1], "category": r[2], "body": r[3], "source": r[4], "ts": r[5]} for r in rows],
    }


def wiki_import_online(topic: str, category: str = "Wikipedia") -> dict:
    """Fetch a real Wikipedia article summary while online and store it permanently in local SQLite FTS5."""
    t = topic.strip()
    if not t:
        return {"ok": False, "error": "Topic is required"}
    slug = urllib.parse.quote(t.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SalathanieAI-OfflineMesh/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        title = data.get("title") or t
        extract = data.get("extract") or ""
        if not extract:
            return {"ok": False, "error": "No extract returned by Wikipedia"}
        ts = int(time.time())
        with db_conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO wiki_articles(title, category, body, source, ts) VALUES (?,?,?,?,?)",
                (title, category, extract, f"wikipedia:{url}", ts),
            )
        _pub_ring(f"wiki_cached:{title[:18]}")
        return {"ok": True, "title": title, "category": category, "chars_saved": len(extract), "body": extract}
    except Exception as e:
        return {"ok": False, "error": f"Offline or topic not found ({str(e)[:120]})"}


def wiki_add_manual(title: str, category: str, body: str) -> dict:
    t, b = title.strip(), body.strip()
    if not t or not b:
        return {"ok": False, "error": "Title and body required"}
    ts = int(time.time())
    with db_conn() as c:
        c.execute("INSERT OR REPLACE INTO wiki_articles(title, category, body, source, ts) VALUES (?,?,?,?,?)", (t, category.strip() or "FieldNote", b, "local_manual", ts))
    return {"ok": True, "title": t}


# =====================================================================
# 3. TEACHING ACCESS TOOLS (OFFLINE LESSONS & QUIZZES)
# =====================================================================
def list_lessons() -> dict:
    with db_conn() as c:
        rows = c.execute("SELECT lesson_id, title, level, body, quiz_json, ts FROM teaching_lessons ORDER BY ts DESC LIMIT 25").fetchall()
    return {
        "ok": True,
        "lessons": [{"lesson_id": r[0], "title": r[1], "level": r[2], "body": r[3], "quiz": json.loads(r[4] or "[]"), "ts": r[5]} for r in rows],
    }


def create_lesson(topic: str, level: str = "Beginner") -> dict:
    t = topic.strip() or "How Mesh Internet Works"
    ts = int(time.time())
    lid = f"LES-{ts % 100000}"
    base_body = (
        f"Objective: Understand {t} ({level}) with zero internet required.\n"
        f"1. Core Concept: Break {t} into physical components, signal/data flow, and fault recovery.\n"
        f"2. Hands-On Lab: Practice directly on Raspberry Pi 5 or Android Termux over local Wi-Fi.\n"
        f"3. Verification: Confirm another device on the LAN/mesh can access the result."
    )
    quiz = [
        {"q": f"What is the first troubleshooting check when setting up {t}?", "a": "Verify local power, interface link, and loopback health."},
        {"q": f"Why does local hosting of {t} help close the digital divide?", "a": "Learners get full speed and interactive tools without paying for mobile data."},
    ]
    out = enhance_with_llm("teacher", f"Create a concise {level} hands-on lesson for bridging the digital divide on: {t}", {"ok": True, "lesson_id": lid, "title": t, "level": level, "body": base_body, "quiz": quiz})
    final_body = out.get("llm_response") or base_body
    with db_conn() as c:
        c.execute("INSERT OR REPLACE INTO teaching_lessons VALUES (?,?,?,?,?,?)", (lid, t, level, final_body, json.dumps(quiz), ts))
    _pub_ring(f"lesson:{lid}")
    return {"ok": True, "lesson_id": lid, "title": t, "level": level, "body": final_body, "quiz": quiz}


# =====================================================================
# 4. IPAD BROADCAST STUDIO CONFIG EXPORTER
# =====================================================================
def save_broadcast_profile(title: str, ticker: str, rtmp_url: str = "") -> dict:
    BCAST_OUT.mkdir(parents=True, exist_ok=True)
    diag = mesh_diagnostics()
    prof = {
        "ts": int(time.time()),
        "studio": "SalathanieAI iPad Broadcast Studio",
        "show_title": title.strip() or "SALATHANIE LIVE // DIGITAL DIVIDE LAB",
        "ticker": ticker.strip() or "OFFLINE MESH ONLINE • RASPBERRY PI 5 • SALATHANIE AI",
        "ipad_lan_url": diag["ipad_studio_url"],
        "obs_browser_source_url": diag["ipad_studio_url"],
        "rtmp_endpoint": rtmp_url.strip() or "rtmp://127.0.0.1:1935/live/salathanie",
        "video_spec": {"width": 1280, "height": 720, "fps": 30, "audio_khz": 48},
    }
    fp = BCAST_OUT / "ipad_studio_profile.json"
    fp.write_text(json.dumps(prof, indent=2), encoding="utf-8")
    _pub_ring("broadcast_profile_saved")
    return {"ok": True, "path": str(fp), "profile": prof}


# =====================================================================
# 5. AI-POWERED SCRINTAL (SPATIAL KNOWLEDGE CANVAS)
# =====================================================================
def scrintal_state() -> dict:
    with db_conn() as c:
        cards = [
            {"card_id": r[0], "title": r[1], "body": r[2], "tag": r[3], "x": r[4], "y": r[5], "color": r[6], "ts": r[7]}
            for r in c.execute("SELECT * FROM scrintal_cards ORDER BY ts ASC").fetchall()
        ]
        links = [{"src": r[0], "dst": r[1], "label": r[2]} for r in c.execute("SELECT src, dst, label FROM scrintal_links").fetchall()]
    return {"ok": True, "cards": cards, "links": links}


def scrintal_upsert_card(card_id: str, title: str, body: str, tag: str = "Note", x: float = 80.0, y: float = 80.0, color: str = "#38bdf8") -> dict:
    ts = int(time.time())
    cid = card_id.strip() or f"CARD-{ts % 100000}"
    with db_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO scrintal_cards VALUES (?,?,?,?,?,?,?,?)",
            (cid, title.strip() or "Untitled Card", body.strip(), tag.strip() or "Note", float(x), float(y), color or "#38bdf8", ts),
        )
    return {"ok": True, "card_id": cid}


def scrintal_move_card(card_id: str, x: float, y: float) -> dict:
    with db_conn() as c:
        c.execute("UPDATE scrintal_cards SET x=?, y=?, ts=? WHERE card_id=?", (float(x), float(y), int(time.time()), card_id))
    return {"ok": True, "card_id": card_id}


def scrintal_delete_card(card_id: str) -> dict:
    with db_conn() as c:
        c.execute("DELETE FROM scrintal_cards WHERE card_id=?", (card_id,))
        c.execute("DELETE FROM scrintal_links WHERE src=? OR dst=?", (card_id, card_id))
    return {"ok": True, "deleted": card_id}


def scrintal_link_cards(src: str, dst: str, label: str = "relates to") -> dict:
    if not src or not dst or src == dst:
        return {"ok": False, "error": "Select two distinct cards"}
    with db_conn() as c:
        c.execute("INSERT OR REPLACE INTO scrintal_links VALUES (?,?,?)", (src, dst, label.strip() or "links"))
    return {"ok": True, "src": src, "dst": dst}


def scrintal_ai_expand(card_id: str) -> dict:
    """Spawn a linked AI synthesis child card using llm_bridge.py (with deterministic offline fallback)."""
    with db_conn() as c:
        row = c.execute("SELECT title, body, tag, x, y FROM scrintal_cards WHERE card_id=?", (card_id,)).fetchone()
    if not row:
        return {"ok": False, "error": "Card not found"}
    title, body, tag, x, y = row
    fallback = f"Actionable Breakdown for {title}:\n- Hardware/Network: Deploy on Pi 5 + local LAN/mesh.\n- Resilience: Keep offline SQLite/Kiwix cache synced.\n- Next Step: Test from tablet/iPad with Wi-Fi only."
    res = enhance_with_llm("researcher", f"Expand this visual knowledge card into 3 concise actionable bullets: {title} — {body}", {"ok": True, "text": fallback})
    child_body = res.get("llm_response") or fallback
    ts = int(time.time())
    child_id = f"AI-{ts % 100000}"
    nx, ny = min(640.0, float(x) + 230.0), float(y) + 60.0
    with db_conn() as c:
        c.execute("INSERT OR REPLACE INTO scrintal_cards VALUES (?,?,?,?,?,?,?,?)", (child_id, f"AI: {title[:26]}", child_body, f"AI-{tag}", nx, ny, "#a855f7", ts))
        c.execute("INSERT OR REPLACE INTO scrintal_links VALUES (?,?,?)", (card_id, child_id, "AI expanded"))
    _pub_ring(f"scrintal_ai:{child_id}")
    return {"ok": True, "child_id": child_id, "body": child_body}


# =====================================================================
# SHARED NAVIGATION & CSS
# =====================================================================
UNIFIED_NAV = """<div class="nav" style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px">
  <a href="/">Pilot</a>
  <a href="/mesh-hub" style="background:#10b981;color:#050912">Mesh &amp; Wiki</a>
  <a href="/broadcast" style="background:#ec4899">iPad Studio</a>
  <a href="/scrintal" style="background:#a855f7">AI Scrintal</a>
  <a href="/creative" style="background:#f97316;color:#050912">Creative Studio</a>
  <a href="/jet-3d" style="background:#39ff14;color:#050912">3D Jet HUD</a>
  <a href="/eagle-eyes" style="background:#0891b2">Eagle Eyes</a>
  <a href="/agents" style="background:#8957e5">18-Agents</a>
  <a href="/infra" style="background:#0ea5e9;color:#050912">Infra/SRE</a>
</div>"""

BASE_CSS = """body{font-family:monospace;background:#060a13;color:#e6edf3;margin:10px}
body.hc{background:#000;color:#fff}
body.dys{letter-spacing:0.06em;line-height:1.65;font-family:sans-serif}
.card{background:#0f172a;border:1px solid #243652;border-radius:10px;padding:12px;margin-bottom:10px}
.nav a{display:inline-block;background:#1f6feb;color:#fff;padding:6px 9px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:bold}
button{background:#238636;color:#fff;border:none;padding:7px 10px;border-radius:6px;cursor:pointer;font-family:monospace;font-weight:bold;margin:3px 2px}
button.alt{background:#0ea5e9;color:#050912}button.purp{background:#8957e5}button.amber{background:#f59e0b;color:#050912}button.red{background:#ef4444}
input,select,textarea{width:100%;box-sizing:border-box;background:#070d18;color:#e6edf3;border:1px solid #30363d;padding:7px;border-radius:6px;font-family:monospace;margin-top:5px}
pre{background:#070d18;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:240px;white-space:pre-wrap;word-break:break-word}
.badge{background:#10b981;color:#050912;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:bold}
.item{border-bottom:1px solid #1e2d45;padding:8px 0}"""

# =====================================================================
# CONSOLE 1: /mesh-hub (Digital Divide, DIY Mesh, Offline Wiki, Pi 5, Teaching)
# =====================================================================
MESH_HUB_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — Digital Divide, DIY Mesh, Offline Wikipedia &amp; Pi 5 Lab</title>
<style>__BASE_CSS__</style></head><body>
<h2 style="color:#10b981;margin:2px 0">DIGITAL DIVIDE // DIY MESH, OFFLINE WIKIPEDIA &amp; PI 5 TEACHING HUB</h2>
__UNIFIED_NAV__

<div class="card">
  <b>Accessibility &amp; Zero-Data Classroom Bar</b>
  <button class="alt" onclick="document.body.classList.toggle('dys')">Dyslexia-Friendly Spacing</button>
  <button class="amber" onclick="document.body.classList.toggle('hc')">High Contrast</button>
  <button class="purp" onclick="bumpFont(1)">Text +</button>
  <button class="purp" onclick="bumpFont(-1)">Text -</button>
  <button onclick="speakPage()">Read Aloud (Offline TTS)</button>
  <button class="red" onclick="window.speechSynthesis && speechSynthesis.cancel()">Stop Audio</button>
  <div id="diagBox" style="margin-top:8px;font-size:12px;color:#38bdf8">Scanning live mesh interfaces...</div>
</div>

<div class="card">
  <b>1. Offline Wikipedia &amp; Vital Self-Reconnection Knowledge Vault (SQLite FTS5 + Kiwix)</b>
  <div style="display:flex;gap:6px;flex-wrap:wrap">
    <input id="wq" style="flex:2;min-width:160px" placeholder="Search offline vault (e.g. mesh, batman, pi5, reconnect, lora)..." oninput="searchWiki()">
    <button class="alt" onclick="searchWiki()">Search Offline</button>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">
    <input id="wimp" style="flex:2;min-width:160px" placeholder="Cache real Wikipedia article offline (e.g. Raspberry Pi, Wireless mesh network)">
    <button onclick="importWiki()">Fetch &amp; Save Offline</button>
  </div>
  <div id="wikiStatus" style="font-size:11px;color:#3fb950;margin-top:4px"></div>
  <div id="wikiList" style="max-height:260px;overflow:auto;margin-top:6px"></div>
</div>

<div class="card">
  <b>2. Raspberry Pi 5 Community Mesh Node &amp; Termux Self-Reconnection Builders</b>
  <div style="display:flex;gap:6px;flex-wrap:wrap">
    <input id="piSsid" style="flex:1;min-width:140px" value="Salathanie-Mesh-Edu" placeholder="Community Wi-Fi SSID">
    <input id="piMesh" style="flex:1;min-width:140px" value="salathanie-mesh" placeholder="802.11s Mesh ID">
  </div>
  <div style="margin-top:6px">
    <button onclick="genPi5()">Generate Pi 5 Mesh + Kiwix Script</button>
    <button class="alt" onclick="genReconnect()">Generate Termux Self-Reconnect Watchdog</button>
    <button class="amber" onclick="dlScript()">Download Current Script (.sh)</button>
  </div>
  <pre id="scriptOut">Generate your Raspberry Pi 5 or Termux self-reconnection script above.</pre>
</div>

<div class="card">
  <b>3. Technology for Teaching Access Tools (Offline Lessons &amp; Quizzes)</b>
  <div style="display:flex;gap:6px;flex-wrap:wrap">
    <input id="lTopic" style="flex:2;min-width:160px" placeholder="Lesson topic (e.g. Solar Power for Off-Grid Wi-Fi, Intro to Python)">
    <select id="lLvl" style="width:120px"><option>Beginner</option><option>Intermediate</option><option>Youth Camp</option></select>
    <button class="purp" onclick="addLesson()">Build Offline Lesson</button>
  </div>
  <div id="lessonList" style="margin-top:8px"></div>
</div>

<script>
let FONT_PX=13, LAST_SCRIPT='', LAST_NAME='pi5_community_mesh.sh';
function bumpFont(d){FONT_PX=Math.max(11,Math.min(22,FONT_PX+d));document.body.style.fontSize=FONT_PX+'px';}
function speakText(txt){
  if(!window.speechSynthesis)return;
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(txt);u.rate=0.95;speechSynthesis.speak(u);
}
function speakPage(){speakText(document.getElementById('wikiList').innerText.slice(0,900)||'Salathanie Digital Divide Hub ready.');}

async function loadDiag(){
  const d=await(await fetch('/api/mesh/diag')).json();
  const pUp=Object.entries(d.mesh_ports).filter(([,v])=>v).map(([k])=>k).join(', ');
  document.getElementById('diagBox').innerHTML=
    `<span class="badge">${d.mode}</span> LAN: <b>${d.lan_ip}:8125</b> | Uplink: <b>${d.internet_uplink?'ONLINE':'OFFLINE SAFE'}</b> | Active Ports: ${pUp}<br>`+
    `Offline Wiki Articles: <b>${d.wiki_articles_offline}</b> | Lessons: <b>${d.teaching_lessons}</b> | Scrintal Cards: <b>${d.scrintal_cards}</b> | Kiwix .zim: <b>${d.kiwix_zims_found.length}</b><br>`+
    `iPad Broadcast URL: <b>${d.ipad_studio_url}</b> | Student LAN Hub: <b>${d.classroom_lan_url}</b>`;
}
async function searchWiki(){
  const q=encodeURIComponent(document.getElementById('wq').value||'');
  const d=await(await fetch('/api/mesh/wiki/search?q='+q)).json();
  document.getElementById('wikiList').innerHTML=(d.articles||[]).map(a=>
    `<div class="item"><b>${a.title}</b> <span class="badge">${a.category}</span> `+
    `<button style="padding:2px 6px;font-size:10px" onclick="speakText(this.dataset.t)" data-t="${a.title.replace(/"/g,'')}. ${a.body.replace(/"/g,'').slice(0,400)}">Read</button> `+
    `<button class="purp" style="padding:2px 6px;font-size:10px" onclick="sendToScrintal(this.dataset.ti,this.dataset.bo)" data-ti="${a.title.replace(/"/g,'')}" data-bo="${a.body.replace(/"/g,'').slice(0,260)}">Pin to Scrintal</button>`+
    `<div style="font-size:11px;color:#cbd5e1;margin-top:4px">${a.body}</div></div>`
  ).join('')||'No offline matches.';
}
async function importWiki(){
  const topic=document.getElementById('wimp').value.trim(); if(!topic)return;
  document.getElementById('wikiStatus').textContent='Fetching from Wikipedia and indexing into local FTS5...';
  const d=await(await fetch('/api/mesh/wiki/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic})})).json();
  document.getElementById('wikiStatus').textContent=d.ok?`[SAVED OFFLINE] ${d.title} (${d.chars_saved} chars indexed)`:d.error;
  searchWiki(); loadDiag();
}
async function sendToScrintal(title,body){
  await fetch('/api/scrintal/card',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,body,tag:'Wiki',x:80+Math.random()*240,y:80+Math.random()*180,color:'#10b981'})});
  document.getElementById('wikiStatus').textContent=`Pinned "${title}" onto AI Scrintal board.`;
}
async function genPi5(){
  const d=await(await fetch('/api/mesh/pi5-script',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid:document.getElementById('piSsid').value,mesh_id:document.getElementById('piMesh').value})})).json();
  LAST_SCRIPT=d.script; LAST_NAME='pi5_community_mesh.sh';
  document.getElementById('scriptOut').textContent=`# Saved to ${d.path}\n`+d.script;
}
async function genReconnect(){
  const d=await(await fetch('/api/mesh/reconnect-script',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
  LAST_SCRIPT=d.script; LAST_NAME='termux_self_reconnect.sh';
  document.getElementById('scriptOut').textContent=`# Saved to ${d.path}\n`+d.script;
}
function dlScript(){
  if(!LAST_SCRIPT)return;
  const a=document.createElement('a'); a.download=LAST_NAME;
  a.href=URL.createObjectURL(new Blob([LAST_SCRIPT],{type:'text/x-shellscript'})); a.click();
}
async function loadLessons(){
  const d=await(await fetch('/api/mesh/lessons')).json();
  document.getElementById('lessonList').innerHTML=(d.lessons||[]).map(l=>
    `<div class="item"><b>${l.title}</b> <span class="badge">${l.level}</span>`+
    `<pre style="margin-top:4px">${l.body}</pre>`+
    `<div style="font-size:11px;color:#fbbf24">${(l.quiz||[]).map(x=>'Q: '+x.q+' -> '+x.a).join(' | ')}</div></div>`
  ).join('');
}
async function addLesson(){
  const topic=document.getElementById('lTopic').value.trim(); if(!topic)return;
  await fetch('/api/mesh/lesson/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic,level:document.getElementById('lLvl').value})});
  document.getElementById('lTopic').value=''; loadLessons(); loadDiag();
}
loadDiag(); searchWiki(); loadLessons();
</script></body></html>""".replace("__BASE_CSS__", BASE_CSS).replace("__UNIFIED_NAV__", UNIFIED_NAV)

# =====================================================================
# CONSOLE 2: /broadcast (iPad as a Broadcast Studio)
# =====================================================================
BROADCAST_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Salathanie A.I — iPad Broadcast Studio</title>
<style>__BASE_CSS__
.studio-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:10px}
canvas#prog{width:100%;aspect-ratio:16/9;background:#02060f;border:2px solid #ec4899;border-radius:8px}
.vu-wrap{height:14px;background:#070d18;border:1px solid #30363d;border-radius:4px;overflow:hidden;margin:6px 0}
.vu-bar{height:100%;width:0%;background:linear-gradient(90deg,#22c55e,#eab308,#ef4444);transition:width 60ms}
#prompter{height:110px;overflow:auto;background:#02060f;border:1px solid #38bdf8;border-radius:6px;padding:10px;font-size:16px;line-height:1.5;color:#fef08a}
</style></head><body>
<h2 style="color:#ec4899;margin:2px 0">IPAD BROADCAST STUDIO // LIVE SWITCHER, CHYRON, VU &amp; RECORDER</h2>
__UNIFIED_NAV__

<div class="studio-grid">
  <div class="card">
    <b>1. Program Monitor (Live Camera + Lower-Third + Tally)</b>
    <canvas id="prog" width="960" height="540"></canvas>
    <video id="camVid" autoplay playsinline muted style="display:none"></video>
    <div class="vu-wrap"><div id="vuBar" class="vu-bar"></div></div>
    <div>
      <button onclick="startCam('user')">Start Front Cam + Mic</button>
      <button class="alt" onclick="startCam('environment')">Rear Cam</button>
      <button class="purp" onclick="startScreen()">Share Screen</button>
      <button class="red" id="recBtn" onclick="toggleRecord()">REC Episode</button>
      <button class="amber" onclick="snapFrame()">Snap Thumbnail</button>
    </div>
    <div id="recStat" style="font-size:11px;color:#38bdf8;margin-top:4px">Tap "Start Front Cam + Mic" on iPad or tablet to go live.</div>
    <a id="recDl" style="display:none;color:#39ff14;font-size:12px;font-weight:bold">Download Recorded Broadcast</a>
  </div>

  <div class="card">
    <b>2. Live Chyron, Scene Switcher &amp; Teleprompter</b>
    <input id="showTitle" value="SALATHANIE A.I LIVE // COMMUNITY MESH &amp; TECH LAB" placeholder="Lower-third headline">
    <input id="showTicker" value="OFFLINE WIKIPEDIA ACTIVE • RASPBERRY PI 5 MESH • ZERO-DATA CLASSROOM ACCESS • SALATHANIE AI" placeholder="Scrolling ticker">
    <div style="margin-top:6px">
      <button class="alt" onclick="SCENE='CAM'">Scene 1: Full Cam</button>
      <button class="purp" onclick="SCENE='SLIDE'">Scene 2: Title Card</button>
      <button class="amber" onclick="SHOW_CHYRON=!SHOW_CHYRON">Toggle Chyron</button>
      <button onclick="saveProfile()">Save OBS / RTMP Profile</button>
    </div>
    <h4 style="margin:10px 0 4px;color:#38bdf8">On-Screen Teleprompter</h4>
    <div id="prompter" contenteditable="true">Welcome to the Salathanie A.I Broadcast Studio. Today we are connecting our neighborhood with a DIY Raspberry Pi 5 mesh network and Offline Wikipedia so every learner has access even when the internet goes down.</div>
    <div style="margin-top:4px">
      <button onclick="PROMPTER_ON=!PROMPTER_ON">Play / Pause Prompter</button>
      <button class="alt" onclick="document.getElementById('prompter').scrollTop=0">Reset Top</button>
    </div>
    <pre id="profOut" style="margin-top:6px;max-height:110px">OBS / RTMP profile ready to export.</pre>
  </div>
</div>

<script>
const cv=document.getElementById('prog'),ctx=cv.getContext('2d'),vid=document.getElementById('camVid');
let STREAM=null,ACTX=null,ANALYSER=null,REC=null,CHUNKS=[],SCENE='CAM',SHOW_CHYRON=true,PROMPTER_ON=false,TICK_X=960,REC_START=0;

async function startCam(facing){
  try{
    if(STREAM)STREAM.getTracks().forEach(t=>t.stop());
    STREAM=await navigator.mediaDevices.getUserMedia({video:{facingMode:facing,width:{ideal:1280},height:{ideal:720}},audio:true});
    vid.srcObject=STREAM; await vid.play();
    setupAudio(STREAM);
    document.getElementById('recStat').textContent='Camera + Mic LIVE ('+facing+').';
  }catch(e){document.getElementById('recStat').textContent='Camera permission/HTTPS note: '+e.message;}
}
async function startScreen(){
  try{
    if(STREAM)STREAM.getTracks().forEach(t=>t.stop());
    STREAM=await navigator.mediaDevices.getDisplayMedia({video:true,audio:true});
    vid.srcObject=STREAM; await vid.play();
    setupAudio(STREAM);
    document.getElementById('recStat').textContent='Screen Capture LIVE.';
  }catch(e){document.getElementById('recStat').textContent='Screen share unavailable: '+e.message;}
}
function setupAudio(stream){
  try{
    if(!stream.getAudioTracks().length)return;
    ACTX=new (window.AudioContext||window.webkitAudioContext)();
    const src=ACTX.createMediaStreamSource(stream);
    ANALYSER=ACTX.createAnalyser(); ANALYSER.fftSize=128;
    src.connect(ANALYSER);
  }catch(e){}
}
function drawProgram(){
  ctx.fillStyle='#050a16'; ctx.fillRect(0,0,960,540);
  if(SCENE==='CAM' && vid.readyState>=2){
    ctx.drawImage(vid,0,0,960,540);
  }else{
    const g=ctx.createLinearGradient(0,0,960,540);
    g.addColorStop(0,'#0f172a'); g.addColorStop(1,'#1e1b4b');
    ctx.fillStyle=g; ctx.fillRect(0,0,960,540);
    ctx.fillStyle='#38bdf8'; ctx.font='bold 36px monospace'; ctx.fillText('SALATHANIE A.I BROADCAST STUDIO',90,240);
    ctx.fillStyle='#e2e8f0'; ctx.font='20px monospace'; ctx.fillText(document.getElementById('showTitle').value.slice(0,52),90,290);
  }
  // Live Tally & Clock
  const isRec=REC && REC.state==='recording';
  ctx.fillStyle=isRec?'#ef4444':'#10b981'; ctx.fillRect(20,18,125,30);
  ctx.fillStyle='#fff'; ctx.font='bold 15px monospace';
  const sec=isRec?Math.floor((Date.now()-REC_START)/1000)+'s':'STANDBY';
  ctx.fillText((isRec?'● REC ':'● LIVE ')+sec,30,38);
  ctx.fillStyle='rgba(5,10,22,0.75)'; ctx.fillRect(790,18,150,30);
  ctx.fillStyle='#7ef9ff'; ctx.fillText(new Date().toLocaleTimeString(),805,38);

  if(SHOW_CHYRON){
    ctx.fillStyle='rgba(8,15,32,0.86)'; ctx.fillRect(0,448,960,56);
    ctx.fillStyle='#ec4899'; ctx.fillRect(0,448,10,56);
    ctx.fillStyle='#ffffff'; ctx.font='bold 22px monospace';
    ctx.fillText(document.getElementById('showTitle').value.slice(0,58),22,482);
    ctx.fillStyle='#020617'; ctx.fillRect(0,504,960,36);
    ctx.fillStyle='#38bdf8'; ctx.font='bold 16px monospace';
    const tk=document.getElementById('showTicker').value;
    TICK_X -= 2.2; if(TICK_X < -tk.length*10) TICK_X = 960;
    ctx.fillText(tk,TICK_X,527);
  }
  if(ANALYSER){
    const arr=new Uint8Array(ANALYSER.frequencyBinCount); ANALYSER.getByteFrequencyData(arr);
    const avg=arr.reduce((a,b)=>a+b,0)/arr.length;
    document.getElementById('vuBar').style.width=Math.min(100,Math.round(avg*1.2))+'%';
  }
  if(PROMPTER_ON){document.getElementById('prompter').scrollTop += 0.6;}
  requestAnimationFrame(drawProgram);
}
function toggleRecord(){
  const btn=document.getElementById('recBtn'), st=document.getElementById('recStat');
  if(REC && REC.state==='recording'){REC.stop(); btn.textContent='REC Episode'; return;}
  if(!cv.captureStream || typeof MediaRecorder==='undefined'){st.textContent='MediaRecorder unsupported in this browser.'; return;}
  const vStream=cv.captureStream(30);
  const tracks=[...vStream.getVideoTracks()];
  if(STREAM) tracks.push(...STREAM.getAudioTracks());
  const mimes=['video/mp4','video/webm;codecs=vp9','video/webm'];
  const mime=mimes.find(m=>MediaRecorder.isTypeSupported(m))||'';
  REC=mime?new MediaRecorder(new MediaStream(tracks),{mimeType:mime}):new MediaRecorder(new MediaStream(tracks));
  CHUNKS=[]; REC_START=Date.now();
  REC.ondataavailable=e=>{if(e.data && e.data.size>0)CHUNKS.push(e.data);};
  REC.onstop=()=>{
    const ext=mime.includes('mp4')?'mp4':'webm';
    const blob=new Blob(CHUNKS,{type:mime||'video/webm'});
    const dl=document.getElementById('recDl');
    dl.href=URL.createObjectURL(blob); dl.download='salathanie_broadcast.'+ext;
    dl.style.display='inline-block'; dl.textContent=`Download Broadcast .${ext.toUpperCase()} (${Math.round(blob.size/1024)} KB)`;
    st.textContent='Broadcast recorded and ready.';
  };
  REC.start(); btn.textContent='STOP REC'; st.textContent='Recording live broadcast...';
}
function snapFrame(){
  const a=document.createElement('a'); a.download='salathanie_studio_frame.png'; a.href=cv.toDataURL('image/png'); a.click();
}
async function saveProfile(){
  const d=await(await fetch('/api/broadcast/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:document.getElementById('showTitle').value,ticker:document.getElementById('showTicker').value})})).json();
  document.getElementById('profOut').textContent=JSON.stringify(d.profile,null,2);
}
drawProgram();
</script></body></html>""".replace("__BASE_CSS__", BASE_CSS).replace("__UNIFIED_NAV__", UNIFIED_NAV)

# =====================================================================
# CONSOLE 3: /scrintal (AI-Powered Scrintal Visual Knowledge Canvas)
# =====================================================================
SCRINTAL_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Salathanie A.I — AI-Powered Scrintal Visual Canvas</title>
<style>__BASE_CSS__
#boardWrap{position:relative;width:100%;height:520px;background:#040812;border:1px solid #30363d;border-radius:10px;overflow:auto;touch-action:none}
#board{position:relative;width:1100px;height:700px;background-image:radial-gradient(#1e293b 1px,transparent 1px);background-size:24px 24px}
svg#edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.scard{position:absolute;width:215px;background:#0f172a;border:2px solid #38bdf8;border-radius:8px;padding:8px;box-shadow:0 4px 14px rgba(0,0,0,0.45);cursor:grab}
.scard-head{display:flex;justify-content:space-between;align-items:center;font-size:11px;font-weight:bold;margin-bottom:4px;border-bottom:1px solid #1e2d45;padding-bottom:3px}
.scard-body{font-size:10px;color:#cbd5e1;white-space:pre-wrap;max-height:95px;overflow:auto}
.scard-act{margin-top:6px;display:flex;gap:4px;flex-wrap:wrap}
.scard-act button{padding:2px 6px;font-size:9px;margin:0}
</style></head><body>
<h2 style="color:#a855f7;margin:2px 0">AI-POWERED SCRINTAL // VISUAL SPATIAL RESEARCH CANVAS</h2>
__UNIFIED_NAV__

<div class="card">
  <div style="display:flex;gap:6px;flex-wrap:wrap">
    <input id="cTitle" style="flex:1;min-width:140px" placeholder="New card title...">
    <input id="cTag" style="width:95px" value="Mesh" placeholder="Tag">
    <select id="cCol" style="width:105px"><option value="#38bdf8">Cyan</option><option value="#22c55e">Green</option><option value="#f59e0b">Gold</option><option value="#ec4899">Pink</option><option value="#a855f7">Violet</option></select>
  </div>
  <textarea id="cBody" rows="2" placeholder="Card notes, research insight, or teaching concept..."></textarea>
  <div style="margin-top:5px">
    <button onclick="addCard()">+ Add Card</button>
    <button class="alt" onclick="exportMD()">Export Board (.md)</button>
    <span id="sStat" style="font-size:11px;color:#3fb950;margin-left:8px">Drag any card to arrange • Tap "Link" on two cards to connect • Tap "AI Expand" to synthesize child notes.</span>
  </div>
</div>

<div id="boardWrap">
  <div id="board"><svg id="edges"></svg></div>
</div>

<script>
let STATE={cards:[],links:[]}, LINK_SRC=null, DRAG=null;
async function loadBoard(){
  STATE=await(await fetch('/api/scrintal/state')).json();
  renderBoard();
}
function renderEdges(){
  const svg=document.getElementById('edges');
  const map=Object.fromEntries((STATE.cards||[]).map(c=>[c.card_id,c]));
  svg.innerHTML=(STATE.links||[]).map(l=>{
    const a=map[l.src], b=map[l.dst]; if(!a||!b)return '';
    const x1=a.x+107,y1=a.y+48,x2=b.x+107,y2=b.y+48;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#a855f7" stroke-width="2" stroke-dasharray="4 3"/>`+
           `<text x="${(x1+x2)/2}" y="${(y1+y2)/2-4}" fill="#e9d5ff" font-size="10" text-anchor="middle">${l.label}</text>`;
  }).join('');
}
function renderBoard(){
  const board=document.getElementById('board');
  board.querySelectorAll('.scard').forEach(el=>el.remove());
  (STATE.cards||[]).forEach(c=>{
    const el=document.createElement('div');
    el.className='scard'; el.style.left=c.x+'px'; el.style.top=c.y+'px'; el.style.borderColor=c.color||'#38bdf8';
    el.innerHTML=`<div class="scard-head"><span style="color:${c.color||'#38bdf8'}">${c.title}</span><span class="badge">${c.tag}</span></div>`+
      `<div class="scard-body">${c.body}</div>`+
      `<div class="scard-act">`+
      `<button class="purp" onclick="aiExpand('${c.card_id}')">AI Expand</button>`+
      `<button class="alt" onclick="pickLink('${c.card_id}')">${LINK_SRC===c.card_id?'Select Target...':'Link'}</button>`+
      `<button class="red" onclick="delCard('${c.card_id}')">Del</button></div>`;
    el.addEventListener('pointerdown',e=>{
      if(e.target.tagName==='BUTTON')return;
      DRAG={id:c.card_id,el,card:c,sx:e.clientX,sy:e.clientY,ox:c.x,oy:c.y};
      el.setPointerCapture(e.pointerId);
    });
    el.addEventListener('pointermove',e=>{
      if(!DRAG||DRAG.id!==c.card_id)return;
      c.x=Math.max(8,Math.min(860,DRAG.ox+(e.clientX-DRAG.sx)));
      c.y=Math.max(8,Math.min(560,DRAG.oy+(e.clientY-DRAG.sy)));
      el.style.left=c.x+'px'; el.style.top=c.y+'px';
      renderEdges();
    });
    el.addEventListener('pointerup',async ()=>{
      if(!DRAG||DRAG.id!==c.card_id)return;
      DRAG=null;
      await fetch('/api/scrintal/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({card_id:c.card_id,x:c.x,y:c.y})});
    });
    board.appendChild(el);
  });
  renderEdges();
}
async function addCard(){
  const title=document.getElementById('cTitle').value.trim(); if(!title)return;
  await fetch('/api/scrintal/card',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    title, body:document.getElementById('cBody').value, tag:document.getElementById('cTag').value,
    color:document.getElementById('cCol').value, x:60+Math.random()*380, y:60+Math.random()*240
  })});
  document.getElementById('cTitle').value=''; document.getElementById('cBody').value='';
  loadBoard();
}
async function pickLink(id){
  if(!LINK_SRC){LINK_SRC=id; document.getElementById('sStat').textContent='Link source selected — tap Link on target card.'; renderBoard(); return;}
  if(LINK_SRC===id){LINK_SRC=null; renderBoard(); return;}
  await fetch('/api/scrintal/link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({src:LINK_SRC,dst:id,label:'connects'})});
  LINK_SRC=null; document.getElementById('sStat').textContent='Cards linked.'; loadBoard();
}
async function aiExpand(id){
  document.getElementById('sStat').textContent='AI synthesizing linked card...';
  const d=await(await fetch('/api/scrintal/ai-expand',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({card_id:id})})).json();
  document.getElementById('sStat').textContent=d.ok?`Created AI card ${d.child_id}`:d.error;
  loadBoard();
}
async function delCard(id){
  await fetch('/api/scrintal/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({card_id:id})});
  loadBoard();
}
function exportMD(){
  let md='# Salathanie A.I — Scrintal Knowledge Board\\n\\n';
  (STATE.cards||[]).forEach(c=>{md+=`## ${c.title} [${c.tag}]\\n${c.body}\\n\\n`;});
  const a=document.createElement('a'); a.download='salathanie_scrintal_board.md';
  a.href=URL.createObjectURL(new Blob([md],{type:'text/markdown'})); a.click();
}
loadBoard();
</script></body></html>""".replace("__BASE_CSS__", BASE_CSS).replace("__UNIFIED_NAV__", UNIFIED_NAV)
