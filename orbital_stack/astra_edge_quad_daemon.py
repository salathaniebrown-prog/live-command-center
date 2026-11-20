import http.server, json, os, pathlib, socketserver, subprocess, threading, time

HOME = pathlib.Path.home()
REPO = HOME / "live-command-center"

def make_handler(service_name, port):
    class QuadHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): pass

        def _json(self, code, obj):
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

        def do_GET(self):
            ts = int(time.time())
            if port == 8113:
                return self._json(200, {
                    "ok": True, "service": service_name, "port": port, "ts": ts,
                    "runtime": "Edge-WASM-WebGPU", "tasks": ["vision", "text", "audio", "rag"], "status": "READY"
                })
            if port == 8137:
                return self._json(200, {
                    "ok": True, "service": service_name, "port": port, "ts": ts,
                    "vr_bridge": "WebGL2/WebXR", "hud3d_link": "http://127.0.0.1:8090/hud3d", "status": "SYNCED"
                })
            if port == 8139:
                if self.path.startswith("/v1/models"):
                    return self._json(200, {"object": "list", "data": [{"id": "astra-jev-v1", "object": "model", "owned_by": "astra"}]})
                return self._json(200, {
                    "ok": True, "service": service_name, "port": port, "ts": ts,
                    "endpoints": ["/v1/models", "/v1/chat/completions"], "status": "ONLINE"
                })
            if port == 8141:
                head, dirty = "unknown", False
                try:
                    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True, timeout=2).strip()
                    dirty = bool(subprocess.check_output(["git", "-C", str(REPO), "status", "--porcelain"], text=True, timeout=2).strip())
                except Exception:
                    pass
                return self._json(200, {
                    "ok": True, "service": service_name, "port": port, "ts": ts,
                    "repo": "salathaniebrown-prog/live-command-center", "commit": head, "dirty": dirty, "status": "WATCHING"
                })
            self._json(200, {"ok": True, "service": service_name, "port": port, "ts": ts})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            ts = int(time.time())
            if port == 8139 and self.path.startswith("/v1/chat/completions"):
                msgs = body.get("messages", [])
                last = msgs[-1].get("content", "") if msgs else ""
                return self._json(200, {
                    "id": f"astra-{ts}", "object": "chat.completion", "created": ts,
                    "model": body.get("model", "astra-jev-v1"),
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": f"[ASTRA :8139 PROXY] Routed: {last}"}, "finish_reason": "stop"}]
                })
            self._json(200, {"ok": True, "service": service_name, "port": port, "ts": ts, "received": body})
    return QuadHandler

def serve_port(name, port):
    class ReusableServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    ReusableServer(("127.0.0.1", port), make_handler(name, port)).serve_forever()

if __name__ == "__main__":
    services = [
        ("mediapipe-edge-8113", 8113),
        ("context-vr-8137", 8137),
        ("openai-proxy-8139", 8139),
        ("github-watchdog-8141", 8141),
    ]
    for name, port in services[:-1]:
        threading.Thread(target=serve_port, args=(name, port), daemon=True).start()
    serve_port(*services[-1])
