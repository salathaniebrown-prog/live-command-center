import astra_contract_middleware  # auto-injected contract shim
#!/usr/bin/env python3
"""
Alstra Autonomous Local AI Agent Loop (127.0.0.1:8145)
- Multi-step task planner & executor wired to:
  * Local OpenAI-Compatible Model Proxy (127.0.0.1:8139/v1)
  * Persistent SQLite WAL Genius Brain (127.0.0.1:8099)
  * Linux Edge Compute & Beta/Meta Node (127.0.0.1:8143)
"""
import http.server
import json
import socketserver
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import os as _astra_os
PORT = int(_astra_os.environ.get('ALSTRA_SHADOW_PORT', '8145'))

RUN_HISTORY = []


def post_json(url: str, payload: dict, timeout: float = 6.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str, timeout: float = 4.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_autonomous_cycle(objective: str) -> dict:
    run_id = f"agent-{uuid.uuid4().hex[:10]}"
    started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    steps = []

    # Step 1: Snapshot live Edge Hardware & Solar telemetry from 8143
    try:
        edge = get_json("http://127.0.0.1:8143/v1/telemetry")
        steps.append({"step": 1, "action": "probe_edge_8143", "ok": True, "cpu_cores": edge.get("hardware", {}).get("cpu_cores")})
    except Exception as exc:
        steps.append({"step": 1, "action": "probe_edge_8143", "ok": False, "error": str(exc)})

    # Step 2: Query local model proxy (8139/v1/chat/completions) for structured execution plan
    plan_summary = f"Autonomous verification plan executed for: {objective}"
    try:
        llm_resp = post_json(
            "http://127.0.0.1:8139/v1/chat/completions",
            {
                "model": "alstra-edge-local",
                "messages": [
                    {"role": "system", "content": "Respond with a concise 1-line operational verification summary."},
                    {"role": "user", "content": objective},
                ],
            },
        )
        choices = llm_resp.get("choices") or []
        if choices:
            plan_summary = choices[0].get("message", {}).get("content", plan_summary)
        steps.append({"step": 2, "action": "reason_proxy_8139", "ok": True, "summary": plan_summary})
    except Exception as exc:
        steps.append({"step": 2, "action": "reason_proxy_8139", "ok": False, "fallback": plan_summary, "error": str(exc)})

    # Step 3: Persist verified execution receipt into SQLite WAL Genius Brain (8099)
    try:
        brain_ack = post_json(
            "http://127.0.0.1:8099/v1/context",
            {
                "key": f"autonomous_run_{run_id}",
                "value": {
                    "run_id": run_id,
                    "objective": objective,
                    "summary": plan_summary,
                    "timestamp_utc": started_utc,
                },
            },
        )
        steps.append({"step": 3, "action": "persist_wal_brain_8099", "ok": True, "ack": brain_ack.get("status", "OK")})
    except Exception as exc:
        steps.append({"step": 3, "action": "persist_wal_brain_8099", "ok": False, "error": str(exc)})

    record = {
        "run_id": run_id,
        "objective": objective,
        "started_utc": started_utc,
        "summary": plan_summary,
        "steps": steps,
    }
    RUN_HISTORY.append(record)
    if len(RUN_HISTORY) > 50:
        del RUN_HISTORY[0]
    return record


class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True


class AgentHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"agent8145-{uuid.uuid4().hex[:12]}")
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/health", "/v1/telemetry"):
            return self._send({
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_AUTONOMOUS_AGENT_8145",
                "completed_cycles": len(RUN_HISTORY),
                "recent_runs": RUN_HISTORY[-5:],
                "timestamp": time.time(),
            })
        return self._send({"ok": False, "error": f"Unknown GET path: {path}"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        if path in ("/v1/run", "/v1/agent/execute"):
            obj = body.get("objective", "Verify full 23-port cluster telemetry & WAL state")
            result = run_autonomous_cycle(obj)
            return self._send({"ok": True, "status": "CYCLE_COMPLETE", "result": result})
        return self._send({"ok": False, "error": f"Unknown POST path: {path}"}, 404)


if __name__ == "__main__":
    with ReuseTCP(("127.0.0.1", PORT), AgentHandler) as srv:
        print(f"[✔] Alstra Autonomous AI Agent Loop active on 127.0.0.1:{PORT}")
        srv.serve_forever()
