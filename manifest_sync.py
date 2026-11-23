#!/usr/bin/env python3
"""
Manifest Contract & Live Telemetry Auditor (2026.11.23-r7)
Probes every registered port contract in manifest.json with per-node latency (ms)
and supports --json for live telemetry spine / gateway ingestion.
"""
import http.client
import json
import os
import sys
import time

MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")


def _collect_endpoints(obj, prefix="", out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        if "port" in obj and isinstance(obj["port"], (int, str)) and str(obj["port"]).isdigit():
            nid = obj.get("id") or obj.get("node_id") or obj.get("name") or prefix or f"port-{obj['port']}"
            path = obj.get("health_path") or obj.get("health") or obj.get("path") or "/"
            out.append({"id": str(nid), "port": int(obj["port"]), "path": str(path)})
        else:
            for k, v in obj.items():
                _collect_endpoints(v, str(k), out)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _collect_endpoints(item, f"{prefix}[{idx}]", out)
    return out


def probe_manifest() -> dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    version = data.get("version", "UNVERSIONED")
    items = _collect_endpoints(data)

    results = []
    online = 0
    unreachable = 0
    for item in items:
        t0 = time.perf_counter()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", item["port"], timeout=1.2)
            conn.request("GET", item["path"])
            code = conn.getresponse().status
            conn.close()
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            ok = code < 400
            state = f"HTTP {code}"
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            ok = False
            state = f"DOWN ({type(e).__name__})"
        if ok:
            online += 1
        else:
            unreachable += 1
        results.append({
            "id": item["id"],
            "port": item["port"],
            "path": item["path"],
            "ok": ok,
            "state": state,
            "latency_ms": latency_ms,
        })

    return {
        "ok": True,
        "ts": time.time(),
        "manifest_version": version,
        "registered": len(items),
        "online": online,
        "unreachable": unreachable,
        "nodes": results,
    }


def main() -> int:
    report = probe_manifest()
    if "--json" in sys.argv:
        print(json.dumps(report, separators=(",", ":")))
        return 0 if report["online"] > 0 else 1

    print(f"Manifest Version : {report['manifest_version']}")
    for n in report["nodes"]:
        print(f"  • {n['id']:<24} :{n['port']:<5} {n['path']:<26} -> {n['state']:<24} ({n['latency_ms']} ms)")
    print(f"Manifest Telemetry Summary: {report['online']}/{report['registered']} online | {report['unreachable']} unreachable")
    return 0 if report["unreachable"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
