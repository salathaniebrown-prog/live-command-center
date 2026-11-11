import http.server
import socketserver
import json
import urllib.request
import os
import time

PORT = 8090
AI_STUDIO_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

class RealTimeAIProxyHandler(http.server.BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_POST(self):
        if self.path == "/proxy/v1/generate":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "GEMINI_API_KEY environment variable not set on proxy."}).encode())
                return

            target_url = f"{AI_STUDIO_URL}?key={api_key}"
            req = urllib.request.Request(target_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            
            try:
                with urllib.request.urlopen(req) as resp:
                    response_data = resp.read()
                    self._set_headers(200)
                    self.wfile.write(response_data)
                    print(f"[{time.strftime('%H:%M:%S', time.gmtime())}] [SUCCESS] Real-Time AI Studio Proxy Forwarded & Settled.")
            except Exception as e:
                self._set_headers(502)
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                print(f"[{time.strftime('%H:%M:%S', time.gmtime())}] [ERROR] Proxy forwarding failed: {e}")
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found."}).encode())

if __name__ == "__main__":
    os.system("pkill -f live_ai_proxy.py")
    with socketserver.TCPServer(("", PORT), RealTimeAIProxyHandler) as httpd:
        print(f"[*] ALSTRA Real-Time Live AI Proxy active on port {PORT}")
        httpd.serve_forever()
