#!/usr/bin/env python3
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"{\"trust_center\":\"ONLINE\"}")
socketserver.ThreadingTCPServer(("127.0.0.1", 8117), H).serve_forever()