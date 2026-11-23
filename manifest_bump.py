#!/usr/bin/env python3
"""
SalathanieAI — Automated manifest.json Upgrade & Node Registry Stamper
"""
import argparse
import json
import time
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"


def bump_manifest(version: str, title: str, node_id: str = "", port: int = 0, health_path: str = "/", tier: str = "core") -> dict:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    data["version"] = version
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    history = data.setdefault("upgrade_history", [])
    history.append({
        "version": version,
        "title": title,
        "ts": int(time.time()),
    })
    data["upgrade_history"] = history[-25:]

    if node_id and port > 0:
        nodes = data.setdefault("telemetry_nodes", [])
        existing = next((n for n in nodes if n.get("id") == node_id or n.get("port") == port), None)
        entry = {"id": node_id, "port": port, "health_path": health_path, "tier": tier}
        if existing:
            existing.update(entry)
        else:
            nodes.append(entry)

    MANIFEST_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--node-id", default="")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--health-path", default="/")
    ap.add_argument("--tier", default="core")
    args = ap.parse_args()
    out = bump_manifest(args.version, args.title, args.node_id, args.port, args.health_path, args.tier)
    print(f"[OK] manifest.json bumped to {out['version']} ({len(out.get('telemetry_nodes', []))} nodes registered)")
