import json, os, pathlib, re, subprocess, time, urllib.request

BASE = pathlib.Path.home()
REPO = BASE / "live-command-center"
LOG_FILE = BASE / "edge_tunnel.log"
URL_FILE = BASE / "LIVE_EDGE_URL.txt"
LEDGER_FILE = REPO / "SECURITY_AUDIT_LEDGER.json"

target_url = "http://" + "127.0.0.1" + ":" + "8088"
teleport_url = "http://" + "127.0.0.1" + ":" + "8101/teleport/push"

def push_teleport(slot, data):
    try:
        body = json.dumps({
            "slot": slot,
            "source_node": "TERMUX_EDGE_GATEWAY",
            "payload_type": "LIVE_EDGE_ENDPOINT",
            "data": data
        }).encode("utf-8")
        req = urllib.request.Request(
            teleport_url, data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass

def run_supervisor():
    last_ledger_mtime = 0
    while True:
        with open(LOG_FILE, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--no-autoupdate", "--url", target_url],
                stdout=lf, stderr=subprocess.STDOUT
            )
            found_url = None
            for _ in range(30):
                time.sleep(1)
                if proc.poll() is not None:
                    break
                txt = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", txt)
                if m:
                    found_url = m.group(0)
                    URL_FILE.write_text(found_url + "\n", encoding="utf-8")
                    push_teleport("EDGE_URL", found_url)
                    print("[EDGE LIVE]", found_url, flush=True)
                    break

            while proc.poll() is None:
                if LEDGER_FILE.exists():
                    mt = LEDGER_FILE.stat().st_mtime
                    if mt != last_ledger_mtime:
                        last_ledger_mtime = mt
                        push_teleport("SECURITY_LEDGER", LEDGER_FILE.read_text(encoding="utf-8"))
                time.sleep(5)
        time.sleep(3)

if __name__ == "__main__":
    run_supervisor()
