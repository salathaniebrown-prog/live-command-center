import hashlib
import http.server
import json
import pathlib
import socketserver
import time
import uuid

PORT = 8173
LEDGER_PATH = pathlib.Path.home() / "astra_dual_model_ledger.json"

MODEL_PAIRS = {
    "alstra_core_dual": ("alstra-core-primary", "alstra-core-secondary"),
    "telemetry_vision_dual": ("gemma4-litert-edge", "vision-ocr-merkle-8157"),
    "exec_ledger_dual": ("rw-ledger-8169", "sovereign-pr-8171"),
}


def load_ledger():
    if LEDGER_PATH.exists():
        try:
            return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    init = {"created_at": int(time.time()), "runs": []}
    LEDGER_PATH.write_text(json.dumps(init, indent=2), encoding="utf-8")
    return init


def save_ledger(data):
    data["updated_at"] = int(time.time())
    tmp = LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(LEDGER_PATH)


class DualRouterHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
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
        st = load_ledger()
        if path in ("/", "/health", "/api/dual/status"):
            return self._json(200, {
                "ok": True,
                "service": "astra-dual-model-router-8173",
                "port": PORT,
                "mode": "READ_WRITE_DUAL_MODEL",
                "presets": MODEL_PAIRS,
                "total_runs": len(st.get("runs", [])),
                "ledger": str(LEDGER_PATH),
            })
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
        try:
            body = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"invalid_json: {e}"})

        path = self.path.split("?", 1)[0]
        if path != "/api/dual/dispatch":
            return self._json(404, {"ok": False, "error": "unknown_endpoint"})

        preset = str(body.get("preset", "alstra_core_dual"))
        m1, m2 = MODEL_PAIRS.get(preset, MODEL_PAIRS["alstra_core_dual"])
        model_a = str(body.get("model_a") or m1)
        model_b = str(body.get("model_b") or m2)
        prompt = str(body.get("prompt") or body.get("goal") or "DUAL_MODEL_SYNC")
        now = int(time.time())
        run_id = "dual_" + uuid.uuid4().hex[:10]

        out_a = {
            "model": model_a,
            "role": "PRIMARY",
            "digest": hashlib.sha256(f"{model_a}:{prompt}".encode()).hexdigest()[:16],
            "status": "COMMITTED",
        }
        out_b = {
            "model": model_b,
            "role": "SECONDARY_PARALLEL",
            "digest": hashlib.sha256(f"{model_b}:{prompt}".encode()).hexdigest()[:16],
            "status": "COMMITTED",
        }
        record = {
            "id": run_id,
            "ts": now,
            "preset": preset,
            "prompt": prompt[:500],
            "models": [out_a, out_b],
        }
        st = load_ledger()
        st["runs"].append(record)
        save_ledger(st)

        return self._json(200, {
            "ok": True,
            "run": record,
            "total_runs": len(st["runs"]),
            "ledger": str(LEDGER_PATH),
        })


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    load_ledger()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), DualRouterHandler)
    print(f"[ALSTRA DUAL MODEL ROUTER 8173] Listening on 127.0.0.1:{PORT}")
    srv.serve_forever()
