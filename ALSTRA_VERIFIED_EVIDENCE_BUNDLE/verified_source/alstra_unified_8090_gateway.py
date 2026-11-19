#!/usr/bin/env python3
import http.server
import os
import socketserver
import urllib.error
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

    def _proxy_upstream(self, target_url: str):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else None
        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "Accept": self.headers.get("Accept", "*/*"),
        }
        req = urllib.request.Request(target_url, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                raw = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                if "Content-Disposition" in resp.headers:
                    self.send_header("Content-Disposition", resp.headers["Content-Disposition"])
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        except urllib.error.HTTPError as e:
            raw = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except Exception as exc:
            raw = f'{{"ok":false,"error":"Upstream proxy error: {exc}"}}'.encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        if self.path.startswith("/v1/gnmi"):
            return self._proxy_upstream(f"http://127.0.0.1:8138{self.path}")
        if self.path.startswith("/v1/multipath"):
            return self._proxy_upstream(f"http://127.0.0.1:8136{self.path}")
        if self.path.startswith("/v1/phaselock"):
            return self._proxy_upstream(f"http://127.0.0.1:8135{self.path}")
        if self.path.startswith("/v1/breaker"):
            return self._proxy_upstream(f"http://127.0.0.1:8134{self.path}")
        if self.path.startswith("/v1/control"):
            return self._proxy_upstream(f"http://127.0.0.1:8128{self.path}")
        if self.path.startswith("/v1/landauer"):
            return self._proxy_upstream(f"http://127.0.0.1:8129{self.path}")
        if self.path.startswith("/v1/ultrasonic"):
            return self._proxy_upstream(f"http://127.0.0.1:8130{self.path}")
        if self.path.startswith("/v1/neuro"):
            return self._proxy_upstream(f"http://127.0.0.1:8157{self.path}")
        if self.path.startswith("/v1/synaptic"):
            return self._proxy_upstream(f"http://127.0.0.1:8155{self.path}")
        if self.path.startswith("/v1/aot"):
            return self._proxy_upstream(f"http://127.0.0.1:8153{self.path}")
        if self.path.startswith("/v1/spatial"):
            return self._proxy_upstream(f"http://127.0.0.1:8151{self.path}")
        return self._proxy_upstream(f"http://127.0.0.1:8088{self.path}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/v1/cluster/unify":
            import socket as _usock
            ports = [8088,8090,8095,8099,8108,8109,8111,8113,8115,8117,8119,8121,8123,8125,8127,8128,8129,8130,8131,8134,8135,8136,8137,8138,8139,8141,8143,8145,8147,8149,8151,8153,8155,8157]
            online = []
            for p in ports:
                s = _usock.socket(_usock.AF_INET, _usock.SOCK_STREAM)
                s.settimeout(0.08)
                try:
                    if s.connect_ex(("127.0.0.1", p)) == 0:
                        online.append(p)
                finally:
                    s.close()
            return self._send_json({"ok": True, "unified_cluster": "ALSTRA_JEV_SYSTEM_ONE", "online_count": len(online), "total_ports": len(ports), "online_ports": online, "views": ["/", "/spatial", "/radial", "/metrics", "/forensic", "/docs"]})
        if path.startswith("/v1/gnmi") or path == "/metrics":
            return self._proxy_upstream(f"http://127.0.0.1:8138{self.path}")
        if path.startswith("/v1/multipath"):
            return self._proxy_upstream(f"http://127.0.0.1:8136{self.path}")
        if path.startswith("/v1/phaselock"):
            return self._proxy_upstream(f"http://127.0.0.1:8135{self.path}")
        if path.startswith("/v1/breaker"):
            return self._proxy_upstream(f"http://127.0.0.1:8134{self.path}")
        if path.startswith("/v1/control"):
            return self._proxy_upstream(f"http://127.0.0.1:8128{self.path}")
        if path.startswith("/v1/landauer"):
            return self._proxy_upstream(f"http://127.0.0.1:8129{self.path}")
        if path.startswith("/v1/ultrasonic"):
            return self._proxy_upstream(f"http://127.0.0.1:8130{self.path}")
        if path.startswith("/v1/hud") or path.startswith("/radial"):
            target = "/" if path.startswith("/radial") else self.path
            return self._proxy_upstream(f"http://127.0.0.1:8131{target}")
        if path.startswith("/v1/neuro"):
            return self._proxy_upstream(f"http://127.0.0.1:8157{self.path}")
        if path.startswith("/v1/synaptic"):
            return self._proxy_upstream(f"http://127.0.0.1:8155{self.path}")
        if path.startswith("/v1/aot"):
            return self._proxy_upstream(f"http://127.0.0.1:8153{self.path}")
        if path.startswith("/v1/spatial") or path.startswith("/api/peppers-ghost"):
            return self._proxy_upstream(f"http://127.0.0.1:8151{self.path}")
        if path.startswith("/api/"):
            return self._proxy_upstream(f"http://127.0.0.1:8088{self.path}")
        if path.startswith("/spatial"):
            return self._serve_file(HOME / "ALSTRA_SPATIAL_3D_ENGINE.html")
        if path.startswith("/docs"):
            return self._serve_file(HOME / "ALSTRA_API_CONSOLE.html")
        if path.startswith("/forensic"):
            return self._serve_file(HOME / "ALSTRA_VERIFIED_EVIDENCE_BUNDLE" / "index.html")

        base_html = ""
        try:
            with urllib.request.urlopen("http://127.0.0.1:8088/", timeout=2.5) as r:
                base_html = r.read().decode("utf-8", errors="replace")
        except Exception:
            locked = HOME / ".astra_locked_core_ui.html"
            base_html = locked.read_text(encoding="utf-8", errors="replace") if locked.exists() else "<!doctype html><html><body><h2>JEV SYSTEM ONE (:8090)</h2></body></html>"

        addons_dir = HOME / ".astra_ui_addons"
        addon_blocks = [f.read_text(encoding="utf-8", errors="replace") for f in sorted(addons_dir.glob("*.html"))] if addons_dir.exists() else []
        injected = "\n".join(addon_blocks)
        final_html = base_html.replace("</body>", f"\n{injected}\n</body>", 1) if "</body>" in base_html else f"{base_html}\n{injected}"

        raw = final_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    with ThreadingReuseTCP(("0.0.0.0", PORT), UnifiedGatewayHandler) as srv:
        print(f"[✔] Alstra Unified Gateway (with /api/* & /v1/spatial/* pass-through) active on 0.0.0.0:{PORT}")
        srv.serve_forever()
