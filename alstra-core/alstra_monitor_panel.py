#!/usr/bin/env python3
"""
Alstra Studio Terminal Monitor Interface
Listens for incoming signed visual alert webhooks and renders them live on-screen.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class VisualTelemetryHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))
        
        # Extract signing parameters from visual engine headers
        signature = self.headers.get('X-Alstra-Signature-Ed25519', 'UNSIGNED')
        
        print("\n" + "="*70)
        print(f" 🖥️  [LIVE COMMAND CENTER VISUAL ALERT] | LEVEL: {payload.get('alert_level', 'UNKNOWN')}")
        print(f" TIME: {payload.get('timestamp')} | AUTH: {payload.get('root_authority')}")
        print(f" MSG:  {payload.get('message')}")
        print("-"*70)
        print(f" ENGINE MATRIX STATE: {json.dumps(payload.get('system_state'), indent=2)}")
        print(f" CRYPTO AUTHENTICITY SEAL: {signature[:32]}...")
        print("="*70 + "\n")
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"RENDERED_SUCCESSFULLY"}')

    def log_message(self, format, *args):
        return # Mutes default network request formatting junk to keep your dashboard clean

def run_panel_server():
    server_address = ('127.0.0.1', 8099)
    httpd = HTTPServer(server_address, VisualTelemetryHandler)
    print("[*] Dashboard monitor listening live on http://127.0.0.1:8099...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Dashboard view sleep sequence engaged.")

if __name__ == "__main__":
    run_panel_server()
