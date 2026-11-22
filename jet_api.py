import json
from pathlib import Path

JET_DIR = Path.home() / "live-command-center" / "builds" / "astra_jet"
TELEM_FILE = JET_DIR / "alstra_jet_telemetry.jsonl"
STATE_FILE = JET_DIR / "alstra_jet_state.json"

def get_hud_json() -> bytes:
    lat = {}
    if TELEM_FILE.exists():
        lines = TELEM_FILE.read_text().strip().splitlines()
        if lines:
            try: lat = json.loads(lines[-1])
            except Exception: pass
    st = {}
    if STATE_FILE.exists():
        try: st = json.loads(STATE_FILE.read_text())
        except Exception: pass
    return json.dumps({"state": st, "latest": lat}).encode()

def update_state(path: str, raw: bytes) -> bytes:
    body = json.loads(raw or b"{}")
    st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    if path == "/api/mode":
        st["mode"] = body.get("mode", "AUTONOMOUS-MUTATE")
    elif path == "/api/pods":
        st["pods"] = body.get("pods", [True, True, True, True])
    elif path == "/api/pilot":
        st["pilot_input"] = body
        if "genome" in st and "thrust" in body:
            st["genome"]["thrust_trim"] = round(float(body["thrust"]), 4)
    STATE_FILE.write_text(json.dumps(st, indent=2))
    return json.dumps({"ok": True}).encode()
