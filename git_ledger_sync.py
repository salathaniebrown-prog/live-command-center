import json, pathlib, subprocess, time, urllib.request

BASE = pathlib.Path.home()
REPO = BASE / "live-command-center"
TELEPORT_URL = "http://" + "127.0.0.1" + ":" + "8101/teleport/push"

TRACKED_FILES = [
    ("GLOBAL_EDGE_LEDGER", REPO / "GLOBAL_EDGE_LEDGER.json"),
    ("SECURITY_LEDGER", REPO / "SECURITY_AUDIT_LEDGER.json"),
]

def beam_to_vault(slot_id, content):
    try:
        payload = json.dumps({
            "slot": slot_id,
            "source_node": "GITHUB_EDGE_SYNC",
            "payload_type": "SEALED_LEDGER",
            "data": content
        }).encode("utf-8")
        req = urllib.request.Request(
            TELEPORT_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass

def sync_loop():
    mtimes = {}
    while True:
        try:
            subprocess.run(
                ["git", "-C", str(REPO), "pull", "--ff-only", "origin", "main"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15
            )
            for slot, fpath in TRACKED_FILES:
                if fpath.exists():
                    mt = fpath.stat().st_mtime
                    if mtimes.get(slot) != mt:
                        mtimes[slot] = mt
                        beam_to_vault(slot, fpath.read_text(encoding="utf-8"))
                        print(f"[SYNCED] {slot} -> Teleport Vault", flush=True)
        except Exception:
            pass
        time.sleep(60)

if __name__ == "__main__":
    sync_loop()
