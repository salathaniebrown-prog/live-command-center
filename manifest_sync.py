#!/usr/bin/env python3
"""
Fast Zero-Overhead Manifest Registry Auditor & Registrar
Recursively extracts every port/health contract in manifest.json and probes it.
"""
import http.client
import json
import os
import sys

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


def audit() -> int:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Manifest Version : {data.get('version', 'UNVERSIONED')}")
    items = _collect_endpoints(data)

    failures = 0
    for item in items:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", item["port"], timeout=1.5)
            conn.request("GET", item["path"])
            code = conn.getresponse().status
            state = f"HTTP {code}"
            if code >= 400:
                failures += 1
        except Exception as e:
            state = f"DOWN ({type(e).__name__})"
            failures += 1
        print(f"  • {item['id']:<24} :{item['port']:<5} {item['path']:<26} -> {state}")

    print(f"Manifest Audit Summary: {len(items)} registered | {failures} unreachable")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(audit())
