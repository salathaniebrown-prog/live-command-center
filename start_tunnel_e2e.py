import json, pathlib, subprocess, urllib.request

home = pathlib.Path.home()
cf = home / ".cloudflared"
cfg = cf / "config.yml"

if not cfg.exists():
    subprocess.run(["cloudflared", "tunnel", "create", "astra-eagleeyes"])
    subprocess.run(["cloudflared", "tunnel", "route", "dns", "-f", "astra-eagleeyes", "://eagleeyes.com"])
    j = sorted(cf.glob("*.json"))
    body = (
        f"tunnel: {j.stem}\ncredentials-file: {j}\n"
        "ingress:\n  - hostname: ://eagleeyes.com\n"
        "    service: http://" + "127.0.0.1" + ":" + "8088\n"
        "  - service: http_status:404\n"
    )
    cfg.write_text(body, encoding="utf-8")

url = "http://" + "127.0.0.1" + ":" + "8099/v1/execute"
pl = json.dumps({
    "prompt": "E2E node check",
    "command": "python3 -c \"import os; print('LIVE_CORES:', os.cpu_count())\"",
    "language": "python",
    "code": "import os; print('LIVE_CORES:', os.cpu_count())"
}).encode("utf-8")
req = urllib.request.Request(url, data=pl, headers={"Content-Type": "application/json"}, method="POST")
print("E2E_8099 ->", urllib.request.urlopen(req, timeout=5).read().decode())
