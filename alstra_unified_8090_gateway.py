#!/usr/bin/env python3
import http.server
import os
import socketserver
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("ALSTRA_SHADOW_PORT", "8090"))
HOME = Path.home()


class ThreadingReuseTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class UnifiedGatewayHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _serve_file(self, file_path: Path):
        if not file_path.exists():
            raw = f"<h1>Missing artifact: {file_path.name}</h1>".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        raw = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/spatial"):
            return self._serve_file(HOME / "ALSTRA_SPATIAL_3D_ENGINE.html")
        if path.startswith("/docs"):
            return self._serve_file(HOME / "ALSTRA_API_CONSOLE.html")
        if path.startswith("/forensic"):
            return self._serve_file(HOME / "ALSTRA_VERIFIED_EVIDENCE_BUNDLE" / "index.html")

        # Root unified dashboard: locked 8088 core UI + additive ~/.astra_ui_addons/*.html cards
        base_html = ""
        try:
            with urllib.request.urlopen("http://127.0.0.1:8088/", timeout=2.5) as r:
                base_html = r.read().decode("utf-8", errors="replace")
        except Exception:
            locked = HOME / ".astra_locked_core_ui.html"
            if locked.exists():
                base_html = locked.read_text(encoding="utf-8", errors="replace")
            else:
                base_html = "<!doctype html><html><body style='background:#020813;color:#d6f8ff;font-family:monospace;'><h2>JEV SYSTEM ONE // ALSTRA UNIFIED GATEWAY (:8090)</h2></body></html>"

        addons_dir = HOME / ".astra_ui_addons"
        addon_blocks = []
        if addons_dir.exists():
            for f in sorted(addons_dir.glob("*.html")):
                addon_blocks.append(f.read_text(encoding="utf-8", errors="replace"))

        injected = "\n".join(addon_blocks)
        if "</body>" in base_html:
            final_html = base_html.replace("</body>", f"\n{injected}\n</body>", 1)
        else:
            final_html = f"{base_html}\n{injected}"

        raw = final_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    with ThreadingReuseTCP(("0.0.0.0", PORT), UnifiedGatewayHandler) as srv:
        print(f"[✔] Alstra Unified Gateway active on 0.0.0.0:{PORT}")
        srv.serve_forever()
