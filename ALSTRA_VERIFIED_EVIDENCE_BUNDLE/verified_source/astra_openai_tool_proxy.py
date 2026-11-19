#!/usr/bin/env python3
import json, time, uuid, http.server, socketserver, urllib.request

class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True

class Proxy(http.server.BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        raw = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if self.path.startswith("/v1/models"):
            return self._send({"object": "list", "data": [{"id": "astra-sovereign-tool-router-v1", "object": "model", "created": int(time.time()), "owned_by": "astra-local"}]})
        return self._send({"status": "ONLINE", "endpoint": "http://127.0.0.1:8139/v1"})
    def do_POST(self):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8137/api/context/unified", timeout=5.0) as r:
                ctx = json.loads(r.read().decode())
        except Exception as e:
            ctx = {"error": str(e)}
        return self._send({
            "id": f"chatcmpl-{uuid.uuid4().hex[:10]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "astra-sovereign-tool-router-v1",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(ctx)}, "finish_reason": "stop"}]
        })

if __name__ == "__main__":
    with ReuseTCP(("127.0.0.1", 8139), Proxy) as s:
        s.serve_forever()
