import hashlib, json, os, socket, sqlite3, time, urllib.request, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_cinema_mcp.db")
RENOISE_OSC_HOST = os.environ.get("RENOISE_OSC_HOST", "127.0.0.1")
RENOISE_OSC_PORT = int(os.environ.get("RENOISE_OSC_PORT", "8000"))

def init_cinema_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS cinema_projects (
        project_id TEXT PRIMARY KEY,
        title TEXT,
        prompt TEXT,
        bpm REAL,
        fps INTEGER,
        duration_sec REAL,
        claude_engine TEXT,
        storyboard_json TEXT,
        renoise_sync_json TEXT,
        attestation_hash TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()

init_cinema_db()

def send_renoise_osc_trigger(bpm, pattern_idx=0):
    # Builds standard OSC packet (/renoise/song/bpm and /renoise/transport/start) via UDP
    def osc_str(s):
        b = s.encode("utf-8") + b"\x00"
        pad = (4 - (len(b) % 4)) % 4
        return b + (b"\x00" * pad)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        import struct
        pkt_bpm = osc_str("/renoise/song/bpm") + osc_str(",f") + struct.pack(">f", float(bpm))
        pkt_play = osc_str("/renoise/transport/start") + osc_str(",")
        sock.sendto(pkt_bpm, (RENOISE_OSC_HOST, RENOISE_OSC_PORT))
        sock.sendto(pkt_play, (RENOISE_OSC_HOST, RENOISE_OSC_PORT))
        sock.close()
        return {"osc_dispatched": True, "target": f"{RENOISE_OSC_HOST}:{RENOISE_OSC_PORT}", "bpm_synced": bpm, "pattern": pattern_idx}
    except Exception as e:
        return {"osc_dispatched": False, "target": f"{RENOISE_OSC_HOST}:{RENOISE_OSC_PORT}", "note": str(e)}

def synthesize_claude_director_plan(prompt_text, bpm=128.0, fps=24):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    engine_used = "LOCAL_DETERMINISTIC_DIRECTOR"
    director_notes = f"Anamorphic 2.39:1 cybernetic sequence synced at {bpm} BPM ({fps} FPS): {prompt_text}"

    if api_key:
        try:
            url = "https://" + "/".join(["://anthropic.com", "v1", "messages"])
            payload = json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 220,
                "messages": [{"role": "user", "content": f"Write a concise 3-shot cinematic camera + Renoise synth sync direction for: {prompt_text} at {bpm} BPM."}]
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            })
            res = json.loads(urllib.request.urlopen(req, timeout=8).read().decode())
            blocks = res.get("content") or []
            if blocks and isinstance(blocks[0], dict):
                director_notes = blocks[0].get("text") or director_notes
                engine_used = "CLAUDE_API_LIVE"
        except Exception:
            pass

    beat_sec = round(60.0 / max(1.0, float(bpm)), 4)
    bar_sec = round(beat_sec * 4.0, 4)
    total_sec = round(bar_sec * 4.0, 2)

    shots = [
        {"shot": 1, "bar_range": "1-2", "start_sec": 0.0, "end_sec": round(bar_sec * 2, 2), "camera": "Dolly-In Low Angle 35mm Anamorphic", "renoise_pattern": 0, "fx": "Sub-bass drop + volumetric cyan rim"},
        {"shot": 2, "bar_range": "3", "start_sec": round(bar_sec * 2, 2), "end_sec": round(bar_sec * 3, 2), "camera": "Orbital FPV Gimbal Sweep", "renoise_pattern": 1, "fx": "16th-note glitch percussion + neon wireframe"},
        {"shot": 3, "bar_range": "4", "start_sec": round(bar_sec * 3, 2), "end_sec": total_sec, "camera": "Crane Pullback Wide Establishing", "renoise_pattern": 2, "fx": "Reverb tail swell + title lockup"}
    ]
    return engine_used, director_notes, total_sec, beat_sec, shots

def build_cinema_sync_project(data):
    title = str(data.get("title") or "ASTRA_CINEMA_SEQUENCE").strip()
    prompt = str(data.get("prompt") or "Hyper-realistic cybernetic supercomputer datacenter flythrough").strip()
    bpm = float(data.get("bpm") or 128.0)
    fps = int(data.get("fps") or 24)
    edit_action = str(data.get("edit_action") or "CREATE_AND_SYNC").strip().upper()

    engine_used, notes, total_sec, beat_sec, shots = synthesize_claude_director_plan(prompt, bpm, fps)
    osc_status = send_renoise_osc_trigger(bpm, 0)

    proj_id = str(data.get("project_id") or ("CIN-" + uuid.uuid4().hex[:8].upper()))
    ts = time.time()
    sync_map = {
        "bpm": bpm,
        "fps": fps,
        "beat_interval_sec": beat_sec,
        "frames_per_beat": round((60.0 / max(1.0, bpm)) * fps, 2),
        "edit_action": edit_action,
        "renoise_osc": osc_status
    }
    attestation = "0x" + hashlib.sha256(f"{proj_id}|{title}|{bpm}|{fps}|{ts}".encode("utf-8")).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO cinema_projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (proj_id, title, prompt, bpm, fps, total_sec, engine_used, json.dumps({"director_notes": notes, "shots": shots}), json.dumps(sync_map), attestation, ts)
    )
    conn.commit()
    conn.close()

    return {
        "status": "CINEMA_RENOISE_SYNCED",
        "project_id": proj_id,
        "title": title,
        "claude_engine": engine_used,
        "director_notes": notes,
        "duration_sec": total_sec,
        "storyboard": shots,
        "renoise_sync": sync_map,
        "attestation_hash": attestation
    }

class CinemaMcpHandler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._json(200, {"ok": True})

    def do_GET(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        projects = [dict(r) for r in conn.execute("SELECT project_id, title, prompt, bpm, fps, duration_sec, claude_engine, attestation_hash, timestamp FROM cinema_projects ORDER BY timestamp DESC LIMIT 15").fetchall()]
        conn.close()
        self._json(200, {
            "service": "ASTRA_CLAUDE_CINEMA_VIDEO_AND_RENOISE_MCP",
            "port": 8121,
            "status": "ONLINE",
            "mcp_protocol": "2024-11-05",
            "mcp_tools": ["create_cinematic_video", "edit_video_timeline", "sync_renoise_bpm_osc"],
            "projects_persisted": len(projects),
            "recent_projects": projects
        })

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln).decode("utf-8", errors="ignore") if ln else "{}"
        data = json.loads(raw) if raw.strip() else {}

        # Standard MCP JSON-RPC 2.0 Handler for Claude AI Desktop / CLI MCP Client
        if self.path == "/mcp" or data.get("jsonrpc") == "2.0":
            rpc_id = data.get("id", 1)
            method = data.get("method", "")
            params = data.get("params") or {}
            if method == "initialize":
                self._json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {"protocolVersion": "2024-11-05", "serverInfo": {"name": "astra-cinema-renoise-mcp", "version": "1.0.0"}, "capabilities": {"tools": {}}}})
                return
            if method == "tools/list":
                self._json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": [
                    {"name": "create_cinematic_video", "description": "Generate beat-synced cinematic storyboard and video timeline"},
                    {"name": "edit_video_timeline", "description": "Edit existing cinematic project cuts, camera motion, and BPM sync"},
                    {"name": "sync_renoise_bpm_osc", "description": "Send live OSC BPM and transport triggers to Renoise DAW"}
                ]}})
                return
            if method == "tools/call":
                args = params.get("arguments") or {}
                res = build_cinema_sync_project(args)
                self._json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {"content": [{"type": "text", "text": json.dumps(res)}]}})
                return

        self._json(200, build_cinema_sync_project(data))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8121), CinemaMcpHandler).serve_forever()
