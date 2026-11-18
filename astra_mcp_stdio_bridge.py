#!/usr/bin/env python3
"""
ASTRA // Unified MCP Stdio Bridge
- Context-Telemetry (8137) + Multi-Chain VR Auditor (8137) + GitHub Watchdog (8141)
"""
import sys
import json
import urllib.request
from pathlib import Path

CONTEXT_URL = "http://127.0.0.1:8137"
WATCHDOG_URL = "http://127.0.0.1:8141"

MCP_TOOLS = [
    {
        "name": "get_github_watchdog_events",
        "description": "Inspect real-time GitHub commits, branch pushes, Actions workflow runs, and local model task dispatches.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_context_telemetry_state",
        "description": "Monitor token utilization, context window saturation %, prompt cache hit rates, and SQLite WAL session persistence.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "query_multichain_telemetry_snapshot",
        "description": "Scan Ethereum, Base, and Polygon balances/nonces and verify ASTRA cluster health via the local Enhancement Station.",
        "inputSchema": {
            "type": "object",
            "properties": {"chain": {"type": "string", "enum": ["ethereum", "base", "polygon", "all"]}},
            "required": ["chain"]
        }
    }
]

def send_response(msg_id, result=None, error=None):
    pkt = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        pkt["error"] = error
    else:
        pkt["result"] = result
    sys.stdout.write(json.dumps(pkt) + "\n")
    sys.stdout.flush()

def execute_tool(name: str, args: dict) -> str:
    if name == "get_github_watchdog_events":
        with urllib.request.urlopen(f"{WATCHDOG_URL}/api/github/watchdog", timeout=8.0) as r:
            return r.read().decode("utf-8")
    elif name == "get_context_telemetry_state":
        with urllib.request.urlopen(f"{CONTEXT_URL}/api/context/telemetry", timeout=8.0) as r:
            return r.read().decode("utf-8")
    elif name == "query_multichain_telemetry_snapshot":
        with urllib.request.urlopen(f"{CONTEXT_URL}/api/context/unified", timeout=8.0) as r:
            return r.read().decode("utf-8")
    raise ValueError(f"Unknown tool: {name}")

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        msg_id = req.get("id")
        if msg_id is None:
            continue
        method = req.get("method", "")
        params = req.get("params", {})
        if method == "initialize":
            send_response(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "astra-unified-mcp-bridge", "version": "2.1.0"}
            })
        elif method == "tools/list":
            send_response(msg_id, {"tools": MCP_TOOLS})
        elif method == "tools/call":
            try:
                out = execute_tool(params.get("name", ""), params.get("arguments", {}))
                send_response(msg_id, {"content": [{"type": "text", "text": out}], "isError": False})
            except Exception as exc:
                send_response(msg_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        else:
            send_response(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})

if __name__ == "__main__":
    main()
