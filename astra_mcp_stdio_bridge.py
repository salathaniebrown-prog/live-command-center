#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

MASTER_SPINE_URL = "http://127.0.0.1:8095"
GENIUS_BRAIN_URL = "http://127.0.0.1:8099"
TRUST_CENTER_URL = "http://127.0.0.1:8117"

TOOLS = [
    {
        "name": "getLiveTelemetry",
        "description": "Retrieve live hardware, thermal, battery, worker count, and task telemetry from Termux Master (8095) or Genius Brain (8099).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": ["master_8095", "brain_8099", "trust_8117"],
                    "default": "brain_8099",
                    "description": "Target service endpoint to inspect."
                }
            }
        }
    },
    {
        "name": "getAllContext",
        "description": "Read all non-volatile persistent context key-value pairs stored in SQLite WAL memory (Port 8099).",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "upsertContext",
        "description": "Store or update a persistent JSON key-value entry in SQLite WAL memory so it survives reboots and session resets.",
        "inputSchema": {
            "type": "object",
            "required": ["key", "value"],
            "properties": {
                "key": {"type": "string", "description": "Unique context identifier key."},
                "value": {"description": "Any JSON-serializable value (string, number, object, array)."}
            }
        }
    },
    {
        "name": "executeVirtualCode",
        "description": "Execute AST-validated Python or Bash code locally or auto-route across cluster workers based on thermal/load state.",
        "inputSchema": {
            "type": "object",
            "required": ["code"],
            "properties": {
                "objective": {"type": "string", "default": "MCP agent execution"},
                "target_node": {"type": "string", "default": "auto", "description": "'auto', 'termux-main', or registered worker name."},
                "language": {"type": "string", "enum": ["python", "bash"], "default": "python"},
                "code": {"type": "string", "description": "Source code to validate and execute."}
            }
        }
    },
    {
        "name": "registerWorkerNode",
        "description": "Register a secondary Linux, macOS, Windows, or Termux worker node with the Termux Master Spine (Port 8095).",
        "inputSchema": {
            "type": "object",
            "required": ["node_name", "endpoint_url"],
            "properties": {
                "node_name": {"type": "string"},
                "endpoint_url": {"type": "string", "description": "Base HTTP URL of worker (e.g. http://192.168.1.150:8095)"}
            }
        }
    },
    {
        "name": "getTaskLedger",
        "description": "Inspect audited historical task executions, exit codes, and stdout records from the Genius Brain ledger (Port 8099).",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}}
        }
    }
]

def http_json(method: str, url: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "http_status": e.code, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def dispatch_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "getLiveTelemetry":
        target = args.get("target", "brain_8099")
        base = {
            "master_8095": f"{MASTER_SPINE_URL}/v1/telemetry",
            "brain_8099": f"{GENIUS_BRAIN_URL}/v1/telemetry",
            "trust_8117": f"{TRUST_CENTER_URL}/"
        }.get(target, f"{GENIUS_BRAIN_URL}/v1/telemetry")
        return http_json("GET", base)

    if name == "getAllContext":
        return http_json("GET", f"{GENIUS_BRAIN_URL}/v1/context")

    if name == "upsertContext":
        return http_json("POST", f"{GENIUS_BRAIN_URL}/v1/context", {
            "key": args["key"],
            "value": args["value"]
        })

    if name == "executeVirtualCode":
        target_node = args.get("target_node", "auto")
        if target_node == "termux-main":
            return http_json("POST", f"{GENIUS_BRAIN_URL}/v1/execute", {
                "objective": args.get("objective", "MCP local execution"),
                "language": args.get("language", "python"),
                "code": args["code"],
                "auto_repair": True
            })
        return http_json("POST", f"{MASTER_SPINE_URL}/v1/execute", {
            "target_node": target_node,
            "language": args.get("language", "python"),
            "code": args["code"]
        })

    if name == "registerWorkerNode":
        return http_json("POST", f"{MASTER_SPINE_URL}/v1/register", {
            "node_name": args["node_name"],
            "endpoint_url": args["endpoint_url"]
        })

    if name == "getTaskLedger":
        limit = int(args.get("limit", 20))
        return http_json("GET", f"{GENIUS_BRAIN_URL}/v1/ledger?limit={limit}")

    return {"ok": False, "error": f"Unknown tool: {name}"}

def send_response(msg_id: Any, result: Any = None, error: Dict[str, Any] | None = None) -> None:
    response: Dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            send_response(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "alstra-supercompute-mcp", "version": "2.4.0"}
            })
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            send_response(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            output = dispatch_tool(tool_name, tool_args)
            send_response(msg_id, {
                "content": [{"type": "text", "text": json.dumps(output, indent=2)}],
                "isError": not output.get("ok", True)
            })
        elif msg_id is not None:
            send_response(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})

if __name__ == "__main__":
    main()
