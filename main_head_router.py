#!/usr/bin/env python3
"""
SalathanieAI — Main Head Declarative Control Plane (:8140)
Hot-loads plug-in modes, nodes, and vector services from nodes_manifest/*.json
without editing core code. Provides live health sweeps, self-healing probes,
and zero-edit dynamic proxying (/node/<id>/<path>).
"""
import http.server
import json
import time
import urllib.request
from pathlib import Path

REPO = Path("/data/data/com.termux/files/home/live-command-center")
MANIFEST_DIR = REPO / "nodes_manifest"
PORT = 8140


def load_manifests() -> dict:
    nodes = {}
    if MANIFEST_DIR.exists():
        for mf in sorted(MANIFEST_DIR.glob("*.json")):
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
                for n in data.get("nodes", []):
                    if isinstance(n, dict) and n.get("id") and n.get("url"):
                        n["manifest"] = mf.name
                        nodes[n["id"]] = n
            except Exception:
                continue
    return nodes


def probe_node(url: str, timeout: float = 0.8) -> dict:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": "ONLINE", "http": r.status, "latency_ms": round((time.time() - t0) * 1000, 1)}
    except Exception as e:
        return {"status": "OFFLINE", "http": 0, "error": str(e)[:80]}


class ReusableServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class MainHeadHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method: str, body: bytes = b""):
        parts = (self.path or "/").split("?", 1)
        clean_path = parts[0]
        qs = ("?" + parts[1]) if len(parts) > 1 else ""
        segs = [s for s in clean_path.split("/") if s]

        if len(segs) < 2 or segs[0] != "node":
            return self._send(404, json.dumps({"ok": False, "error": "Use /node/<id>/<subpath>"}).encode())

        node_id = segs[1]
        subpath = "/" + "/".join(segs[2:]) + qs
        nodes = load_manifests()
        node = nodes.get(node_id)
        if not node:
            return self._send(404, json.dumps({"ok": False, "error": f"Node '{node_id}' not registered"}).encode())

        target = node["url"].rstrip("/") + subpath
        try:
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")} if method == "POST" else {}
            req = urllib.request.Request(target, data=(body if method == "POST" else None), method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=2.5) as r:
                ctype = r.headers.get("Content-Type", "application/octet-stream")
                return self._send(r.status, r.read(), ctype)
        except Exception as e:
            return self._send(502, json.dumps({"ok": False, "node": node_id, "error": str(e)[:120]}).encode())

    def do_GET(self):
        p = (self.path or "/").split("?", 1)[0]
        if p in ("/", "/health"):
            nodes = load_manifests()
            report = {nid: {**n, "probe": probe_node(n["url"])} for nid, n in nodes.items()}
            online = sum(1 for v in report.values() if v["probe"]["status"] == "ONLINE")
            return self._send(200, json.dumps({
                "ok": True,
                "service": "SALATHANIE_MAIN_HEAD_8140",
                "ts": int(time.time()),
                "nodes_total": len(report),
                "nodes_online": online,
                "nodes": report,
            }, indent=2).encode())
        if p == "/nodes":
            return self._send(200, json.dumps({"ok": True, "nodes": list(load_manifests().values())}, indent=2).encode())
        return self._proxy("GET")

    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or "0")
        bd = self.rfile.read(ln) if ln > 0 else b""
        return self._proxy("POST", bd)


if __name__ == "__main__":
    ReusableServer(("127.0.0.1", PORT), MainHeadHandler).serve_forever()
