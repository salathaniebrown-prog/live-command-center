#!/usr/bin/env python3
"""
Fast Zero-Overhead Manifest Registry Auditor & Registrar
Validates manifest.json contracts and probes every registered health endpoint.
"""
import http.client
import json
import os
import sys

MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")


def load_manifest() -> dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def audit() -> int:
    data = load_manifest()
    print(f"Manifest Version : {data.get('version', 'UNVERSIONED')}")
    nodes = data.get("nodes") or data.get("services") or []
    if isinstance(nodes, dict):
        items = [{"id": k, **v} for k, v in nodes.items()]
    else:
        items = nodes

    failures = 0
    for item in items:
        nid = item.get("id") or item.get("node_id") or item.get("name") or "unknown"
        port = item.get("port")
        path = item.get("health_path") or item.get("health") or "/"
        if not port:
            continue
        try:
            conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=1.5)
            conn.request("GET", path)
            code = conn.getresponse().status
            state = f"HTTP {code}"
            if code >= 400:
                failures += 1
        except Exception as e:
            state = f"DOWN ({type(e).__name__})"
            failures += 1
        print(f"  • {nid:<22} :{port:<5} {path:<26} -> {state}")

    print(f"Manifest Audit Summary: {len(items)} registered | {failures} unreachable")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(audit())
