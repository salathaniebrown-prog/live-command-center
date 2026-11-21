import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("ASTRA_HOST", "127.0.0.1")
PORT = int(os.environ.get("ASTRA_SVC_8182_PORT", "8182"))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/health", "/"):
            body = json.dumps({"status": "ok", "service": "astra-svc-8182", "port": PORT}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
