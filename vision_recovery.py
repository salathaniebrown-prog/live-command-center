import base64
import hashlib
import http.server
import json
import os
import pathlib
import re
import shutil
import socketserver
import sqlite3
import subprocess
import time
import uuid

PORT = 8104
HOME = pathlib.Path.home()
DB_PATH = HOME / "astra_vision_recovery_wal.db"
KEY_PATH = HOME / ".astra_vision_ed25519.json"
SYNTH_OUT_DIR = HOME / "astra_synthesized_telemetry"
UPLOAD_DIR = HOME / "astra_vision_uploads"

SYNTH_OUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def init_wal_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recovered_artifacts (
            id TEXT PRIMARY KEY,
            created_ts INTEGER NOT NULL,
            source_name TEXT,
            sha256_hex TEXT NOT NULL,
            ed25519_sig TEXT NOT NULL,
            ed25519_pub TEXT NOT NULL,
            ports_json TEXT NOT NULL,
            errors_json TEXT NOT NULL,
            synthesized_file TEXT NOT NULL,
            extracted_excerpt TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_or_create_signer():
    if KEY_PATH.exists():
        try:
            return json.loads(KEY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization

        priv = Ed25519PrivateKey.generate()
        priv_raw = priv.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption=serialization.NoEncryption(),
        ).hex()
        pub_raw = priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        data = {"scheme": "Ed25519", "priv_hex": priv_raw, "pub_hex": pub_raw}
        KEY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data
    except Exception:
        seed = hashlib.sha256(f"astra-ed25519-{os.getuid()}-8104".encode()).hexdigest()
        pub = hashlib.sha256(f"pub:{seed}".encode()).hexdigest()
        data = {"scheme": "Ed25519-SHA256-Fallback", "priv_hex": seed, "pub_hex": pub}
        KEY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


def sign_artifact(digest_hex: str, signer: dict) -> str:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(signer["priv_hex"]))
        return priv.sign(digest_hex.encode("utf-8")).hex()
    except Exception:
        return hashlib.sha256(f"{signer['priv_hex']}:{digest_hex}".encode("utf-8")).hexdigest()


def extract_text_from_image(img_path: pathlib.Path) -> str:
    texts = []
    if shutil.which("tesseract"):
        try:
            res = subprocess.run(
                ["tesseract", str(img_path), "stdout", "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            if res.stdout and res.stdout.strip():
                texts.append(res.stdout.strip())
        except Exception:
            pass

    if not texts:
        try:
            raw = img_path.read_bytes()
            printable = re.findall(rb"[ -~]{5,}", raw)
            if printable:
                texts.append("\n".join(x.decode("ascii", errors="ignore") for x in printable[-80:]))
        except Exception:
            pass

    return "\n".join(texts).strip()


def parse_telemetry_and_errors(text: str):
    ports_found = sorted(set(int(m) for m in re.findall(r":(3000|80\d\d|81\d\d|82\d\d)\b", text)))
    http_codes = re.findall(r"\bHTTP\s+(\d{3})\b", text)
    ram_matches = re.findall(r"(\d+(?:\.\d+)?%)\s*ram", text, flags=re.IGNORECASE)
    error_lines = []
    for line in text.splitlines():
        if re.search(r"(Traceback|Error|Exception|Errno|FAILED|errored|waiting restart|stopped|000000)", line):
            error_lines.append(line.strip()[:240])
    return {
        "ports": ports_found,
        "http_codes": http_codes,
        "ram_samples": ram_matches,
        "errors": error_lines[:30],
    }


def synthesize_self_healing_module(artifact_id: str, parsed: dict) -> pathlib.Path:
    out_file = SYNTH_OUT_DIR / f"heal_{artifact_id}.py"
    ports_literal = json.dumps(parsed.get("ports", [8088, 8090, 8143, 8169]))
    errors_literal = json.dumps(parsed.get("errors", []))
    code = f'''"""Auto-synthesized self-healing telemetry module for artifact {artifact_id}."""
import json
import socket
import subprocess
import time

TARGET_PORTS = {ports_literal}
DETECTED_ERRORS = {errors_literal}


def check_port(port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def heal_cycle() -> dict:
    offline = [p for p in TARGET_PORTS if not check_port(p)]
    healed = False
    if offline:
        try:
            subprocess.run(
                ["pm2", "resurrect"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
            healed = True
        except Exception:
            healed = False
    still_down = [p for p in TARGET_PORTS if not check_port(p)]
    return {{
        "artifact_id": "{artifact_id}",
        "ts": int(time.time()),
        "checked_ports": TARGET_PORTS,
        "initially_offline": offline,
        "resurrect_invoked": healed,
        "remaining_offline": still_down,
        "known_error_patterns": DETECTED_ERRORS[:10],
    }}


if __name__ == "__main__":
    print(json.dumps(heal_cycle(), indent=2))
'''
    out_file.write_text(code, encoding="utf-8")
    return out_file


class VisionHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, code: int, obj: dict):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        signer = get_or_create_signer()
        conn = init_wal_db()
        try:
            count = conn.execute("SELECT COUNT(*) FROM recovered_artifacts").fetchone()[0]
            rows = conn.execute(
                """
                SELECT id, created_ts, source_name, sha256_hex, ed25519_sig, ports_json, errors_json, synthesized_file
                FROM recovered_artifacts ORDER BY created_ts DESC LIMIT 20
                """
            ).fetchall()
        finally:
            conn.close()

        if path in ("/", "/health", "/api/vision/status"):
            return self._json(200, {
                "ok": True,
                "service": "astra-vision-recovery-8104",
                "port": PORT,
                "wal_db": str(DB_PATH),
                "signer_scheme": signer["scheme"],
                "signer_pub": signer["pub_hex"],
                "tesseract_available": bool(shutil.which("tesseract")),
                "artifacts_sealed": count,
            })

        if path == "/api/vision/ledger":
            items = [
                {
                    "id": r[0],
                    "created_ts": r[1],
                    "source_name": r[2],
                    "sha256": r[3],
                    "ed25519_sig": r[4],
                    "ports": json.loads(r[5]),
                    "errors": json.loads(r[6]),
                    "synthesized_file": r[7],
                }
                for r in rows
            ]
            return self._json(200, {"ok": True, "count": len(items), "items": items})

        return self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
        try:
            body = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"invalid_json: {e}"})

        path = self.path.split("?", 1)[0]
        if path != "/api/vision/recover":
            return self._json(404, {"ok": False, "error": "unknown_post_path"})

        artifact_id = "vis_" + uuid.uuid4().hex[:12]
        now = int(time.time())
        source_name = str(body.get("filename") or f"{artifact_id}.png")[:120]
        extracted_text = str(body.get("text") or "")

        b64 = body.get("image_base64")
        if b64:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            try:
                img_bytes = base64.b64decode(b64, validate=False)
                img_file = UPLOAD_DIR / f"{artifact_id}_{pathlib.Path(source_name).name}"
                img_file.write_bytes(img_bytes)
                ocr_text = extract_text_from_image(img_file)
                if ocr_text:
                    extracted_text = (extracted_text + "\n" + ocr_text).strip()
            except Exception as e:
                extracted_text = (extracted_text + f"\n[IMAGE_DECODE_NOTE] {e}").strip()

        parsed = parse_telemetry_and_errors(extracted_text)
        synth_path = synthesize_self_healing_module(artifact_id, parsed)

        seal_payload = json.dumps({
            "id": artifact_id,
            "ts": now,
            "ports": parsed["ports"],
            "errors": parsed["errors"],
            "synth_file": str(synth_path),
            "excerpt": extracted_text[:2000],
        }, sort_keys=True).encode("utf-8")
        sha256_hex = hashlib.sha256(seal_payload).hexdigest()
        signer = get_or_create_signer()
        ed_sig = sign_artifact(sha256_hex, signer)

        conn = init_wal_db()
        try:
            conn.execute(
                """
                INSERT INTO recovered_artifacts
                (id, created_ts, source_name, sha256_hex, ed25519_sig, ed25519_pub, ports_json, errors_json, synthesized_file, extracted_excerpt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    now,
                    source_name,
                    sha256_hex,
                    ed_sig,
                    signer["pub_hex"],
                    json.dumps(parsed["ports"]),
                    json.dumps(parsed["errors"]),
                    str(synth_path),
                    extracted_text[:4000],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return self._json(200, {
            "ok": True,
            "artifact_id": artifact_id,
            "port": PORT,
            "parsed": parsed,
            "synthesized_module": str(synth_path),
            "sha256": sha256_hex,
            "ed25519_sig": ed_sig,
            "wal_db": str(DB_PATH),
        })


class ReusableThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    init_wal_db()
    get_or_create_signer()
    srv = ReusableThreadingHTTPServer(("127.0.0.1", PORT), VisionHandler)
    print(f"[ASTRA VISION RECOVERY 8104] Listening on 127.0.0.1:{PORT}")
    srv.serve_forever()
