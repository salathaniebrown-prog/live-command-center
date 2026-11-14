#!/usr/bin/env python3
import glob
import http.client
import importlib.util
import json
import os
import py_compile
import sys
import time

HOME = os.path.expanduser("~")
PLUGIN_DIR = os.path.join(HOME, "astra_plugins")
MANIFEST_PATH = os.path.join(HOME, "astra_plugins_manifest.json")

BUILTIN_PLUGINS = [
    {"id": "plugin.saga.execute", "name": "Durable Self-Healing Saga Runner", "port": 8123, "endpoint": "/saga/run", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"name": {"type": "string"}}}},
    {"id": "plugin.polyglot.run", "name": "Polyglot Raw Code Sandbox (Python/Java/PHP/Go/.NET)", "port": 8123, "endpoint": "/polyglot/run", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"language": {"type": "string"}, "code": {"type": "string"}}}},
    {"id": "plugin.stripe.meter", "name": "Stripe External Usage & Payment Metering", "port": 8123, "endpoint": "/stripe/meter", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"meter": {"type": "string"}, "units": {"type": "integer"}, "amount_usd": {"type": "number"}}}},
    {"id": "plugin.datadog.memory", "name": "Datadog APM & System Memory Telemetry", "port": 8123, "endpoint": "/state", "method": "GET", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {}}},
    {"id": "plugin.gov.templates", "name": "3,600+ Legal & DPA Template Generator", "port": 8125, "endpoint": "/templates", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"index": {"type": "integer"}, "query": {"type": "string"}}}},
    {"id": "plugin.gov.scanner", "name": "App Vendor, SSP & SDK Compliance Scanner", "port": 8125, "endpoint": "/scan", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"target": {"type": "string"}}}},
    {"id": "plugin.gov.vr_consent", "name": "Cross-Device VR/XR AI Owner Consent Passport", "port": 8125, "endpoint": "/vr-share", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"devices": {"type": "string"}}}},
    {"id": "plugin.gov.bulk_whitelabel", "name": "Multi-Config Bulk White-Label, Geo & SSO Manager", "port": 8125, "endpoint": "/bulk-update", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"brand_name": {"type": "string"}, "primary_color": {"type": "string"}}}},
    {"id": "plugin.dealership.escrow", "name": "Wyler & DealersLink Virtual Card Escrow", "port": 8099, "endpoint": "/api/state", "method": "GET", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {}}},
    {"id": "plugin.cinema.renoise", "name": "Cinema 2.39:1 & Renoise OSC MCP Studio", "port": 8121, "endpoint": "/render", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "bpm": {"type": "number"}}}},
    {"id": "plugin.mesh.validator", "name": "10-Node Supercomputer 4-Gate Validator", "port": 8119, "endpoint": "/execute", "method": "POST", "auto_allow": True, "approval_required": False, "schema": {"type": "object", "properties": {"goal": {"type": "string"}}}},
]

def sync_plugins():
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    plugins = list(BUILTIN_PLUGINS)
    for fp in sorted(glob.glob(os.path.join(PLUGIN_DIR, "*.py"))):
        fname = os.path.basename(fp)
        if fname.startswith("_"):
            continue
        try:
            py_compile.compile(fp, doraise=True)
            mod_name = os.path.splitext(fname)[0]
            plugins.append({
                "id": f"plugin.custom.{mod_name}",
                "name": f"Custom Drop-In Plugin ({mod_name})",
                "file": fp,
                "auto_allow": True,
                "approval_required": False,
                "schema": {"type": "object", "properties": {"input": {"type": "string"}}},
            })
        except Exception:
            pass

    manifest = {
        "policy": "AUTO_ALLOW_ALL_VERIFIED_PLUGINS",
        "require_user_confirmation": False,
        "total_plugins": len(plugins),
        "updated_at": time.time(),
        "openai_tools_schema": [
            {
                "type": "function",
                "function": {
                    "name": p["id"].replace(".", "_"),
                    "description": p["name"],
                    "parameters": p["schema"],
                },
            }
            for p in plugins
        ],
        "plugins": plugins,
    }
    open(MANIFEST_PATH, "w", encoding="utf-8").write(json.dumps(manifest, indent=2))
    return manifest

def execute_plugin(plugin_id, args=None):
    args = args or {}
    manifest = sync_plugins()
    norm = (plugin_id or "").strip()
    target = None
    for p in manifest["plugins"]:
        if p["id"] == norm or p["id"].replace(".", "_") == norm:
            target = p
            break
    if not target:
        return {"status": "ERROR", "error": f"Unknown plugin: {plugin_id}", "available": [x["id"] for x in manifest["plugins"]]}

    if "file" in target:
        spec = importlib.util.spec_from_file_location("custom_plug", target["file"])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "run"):
            res = mod.run(args)
            return {"status": "EXECUTED_AUTO_ALLOWED", "plugin": target["id"], "result": res}
        return {"status": "LOADED_AUTO_ALLOWED", "plugin": target["id"], "note": "Define run(args) in plugin file to execute"}

    try:
        c = http.client.HTTPConnection("127.0.0.1", target["port"], timeout=8)
        if target["method"] == "POST":
            body = json.dumps(args).encode("utf-8")
            c.request("POST", target["endpoint"], body=body, headers={"Content-Type": "application/json"})
        else:
            c.request("GET", target["endpoint"])
        raw = c.getresponse().read().decode("utf-8", errors="ignore")
        parsed = json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}
        return {"status": "EXECUTED_AUTO_ALLOWED", "plugin": target["id"], "result": parsed}
    except Exception as e:
        return {"status": "RECOVERED_FALLBACK", "plugin": target["id"], "note": str(e)}

if __name__ == "__main__":
    m = sync_plugins()
    if len(sys.argv) > 2 and sys.argv[1] == "run":
        payload = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(execute_plugin(sys.argv[2], payload), indent=2))
    else:
        print(json.dumps({"status": "SYNCED", "policy": m["policy"], "total_plugins": m["total_plugins"], "plugin_ids": [p["id"] for p in m["plugins"]]}, indent=2))
