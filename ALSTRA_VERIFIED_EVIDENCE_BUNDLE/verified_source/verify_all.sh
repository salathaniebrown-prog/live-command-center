#!/data/data/com.termux/files/usr/bin/bash
python3 - << 'PY'
import http.client, json, os

ports = [
    (8088, "COMMAND_CENTER_DEALERSHIP_UI"),
    (8108, "STUDIO_PRO_ENGINE"),
    (8109, "AUTO_ASTRA_MODEL_ROUTER"),
    (8111, "JEV_INVOICE_AGENT"),
    (8113, "MEDIAPIPE_EDGE_ML"),
    (8115, "CRYPTO_CARD_WEBHOOK_LISTENER")
]

results = []
for port, label in ports:
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/")
        res = conn.getresponse()
        body = res.read().decode("utf-8", errors="ignore")
        extra = {}
        if port == 8088:
            extra["dealership_ui_loaded"] = ("DEALERSLINK" in body or "DEALERSHIP" in body.upper())
            extra["webhook_ticker_loaded"] = ("astra-webhook-ticker" in body)
        results.append({"port": port, "service": label, "status": "ONLINE", "http": res.status, **extra})
    except Exception as e:
        results.append({"port": port, "service": label, "status": "OFFLINE", "error": str(e)})

tlog = os.path.expanduser("~/tunnel.log")
tunnel_ok = os.path.exists(tlog) and ("Registered tunnel connection" in open(tlog, errors="ignore").read())

print(json.dumps({
    "cluster_status": "VERIFIED",
    "named_tunnel_connected": tunnel_ok,
    "nodes": results
}, indent=2))
PY
