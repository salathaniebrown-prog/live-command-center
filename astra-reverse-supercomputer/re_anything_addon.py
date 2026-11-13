#!/usr/bin/env python3
import ast, base64, hashlib, json, os, re, urllib.parse

OUT_DIR = os.path.expanduser("~/astra-ownable-apps/re-builds")
os.makedirs(OUT_DIR, exist_ok=True)

def analyze_target(payload: str, mode: str = "auto") -> dict:
    digest = hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:12]
    report = {"id": digest, "detected_type": "raw_text_or_binary", "symbols": [], "urls_endpoints": [], "structure": []}
    report["urls_endpoints"] = list(set(re.findall(r'https?://[^\s\'"<>]+|/api/[a-zA-Z0-9_/-]+', payload)))
    try:
        tree = ast.parse(payload)
        report["detected_type"] = "python_ast"
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                report["symbols"].append(f"{type(node).__name__}:{node.name}")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", "") or ",".join(a.name for a in node.names)
                report["structure"].append(f"import:{mod}")
    except SyntaxError:
        if payload.strip().startswith(("{", "[")):
            report["detected_type"] = "json_schema_or_manifest"
            report["symbols"] = list(set(re.findall(r'"([a-zA-Z0-9_-]+)"\s*:', payload)))[:30]
        else:
            strings = re.findall(r'[A-Za-z0-9_./:-]{5,}', payload)
            report["symbols"] = list(dict.fromkeys(strings))[:35]
    return report

def generate_prompt_pack(analysis: dict, objective: str = "Clean-room clone & harden") -> dict:
    syms = ", ".join(analysis.get("symbols", [])[:20]) or "none_detected"
    eps = ", ".join(analysis.get("urls_endpoints", [])[:15]) or "none_detected"
    return {
        "pack_id": f"RE-PACK-{analysis['id']}",
        "target_type": analysis["detected_type"],
        "prompts": {
            "1_architecture_blueprint": f"Reverse-engineer this {analysis['detected_type']} artifact. Extracted symbols: [{syms}]. Endpoints: [{eps}]. Reconstruct the exact state machine, data flow, and storage schema.",
            "2_clean_room_rebuild": f"Objective: {objective}. Using symbols [{syms}] and routes [{eps}], write a self-contained, zero-dependency Python 3 microservice compatible with Termux + SQLite WAL.",
            "3_security_and_patch_audit": f"Audit extracted surface [{syms}] and [{eps}] for injection, auth bypass, or memory leaks. Output hardened drop-in replacement handlers."
        }
    }

def build_from_notes(notes: str, app_name: str = "astra_note_build") -> dict:
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', app_name.strip()) or "astra_note_build"
    lines = [l.strip("-*• \t") for l in notes.splitlines() if l.strip()]
    endpoints = [re.sub(r'[^a-zA-Z0-9_]', '_', l[:24]).lower() for l in lines[:8]]
    code = f'''#!/usr/bin/env python3
# Auto-synthesized from notes by Astra RE Supercomputer (Port 8105)
import http.server, json

NOTES_SPEC = {json.dumps(lines, indent=2)}

class NoteBuildHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({{"app": "{safe_name}", "routes": {json.dumps(endpoints)}, "spec": NOTES_SPEC}}).encode())

if __name__ == "__main__":
    http.server.HTTPServer(("127.0.0.1", 0), NoteBuildHandler).serve_forever()
'''
    out_path = os.path.join(OUT_DIR, f"{safe_name}.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    return {"status": "BUILT", "app_name": safe_name, "saved_path": out_path, "extracted_steps": len(lines), "generated_routes": endpoints}
