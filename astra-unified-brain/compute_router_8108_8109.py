import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

def make_handler(service_name, port_num):
    class NodeHandler(BaseHTTPRequestHandler):
        def _json(self, code, data):
            body = json.dumps(data).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._json(200, {"ok": True})

        def do_GET(self):
            self._json(200, {"service": service_name, "port": port_num, "status": "ONLINE"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw)
            self._json(200, {
                "service": service_name,
                "port": port_num,
                "status": "ROUTED",
                "target": "ANDROID_EDGE_AND_8GPU_CLUSTER",
                "echo": payload
            })
    return NodeHandler

if __name__ == "__main__":
    t1 = threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", 8108), make_handler("STUDIO_PRO_ENGINE", 8108)).serve_forever(),
        daemon=True
    )
    t2 = threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", 8109), make_handler("AUTO_ASTRA_MODEL_ROUTER", 8109)).serve_forever(),
        daemon=True
    )
    t1.start()
    t2.start()
    while True:
        time.sleep(60)
