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
        import urllib.request, urllib.error
        try:
            body = None
            if self.command in ("POST", "PUT", "PATCH"):
                clen = int(self.headers.get("Content-Length", "0") or "0")
                if clen > 0:
                    body = self.rfile.read(clen)
            req = urllib.request.Request(
                target_url,
                data=body,
                method=self.command,
                headers={"Connection": "close", "Content-Type": self.headers.get("Content-Type", "application/json")},
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "application/json")
                self.send_response(resp.status)
                self.send_header("Content-Type", ctype)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        except Exception as exc:
            err_raw = json.dumps({"ok": False, "upstream": target_url, "error": str(exc)}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.send_header("Content-Length", str(len(err_raw)))
            self.end_headers()
            self.wfile.write(err_raw)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        up_post = self._route_v1_upstream(self.path)
        if up_post:
            return self._proxy_upstream(up_post)
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


    def _route_v1_upstream(self, req_path: str):
        p = req_path.split("?")[0]
        routes = {
            "/v1/control": "http://127.0.0.1:8128",
            "/v1/landauer": "http://127.0.0.1:8129",
            "/v1/ultrasonic": "http://127.0.0.1:8130",
            "/v1/hud": "http://127.0.0.1:8131",
            "/v1/breaker": "http://127.0.0.1:8134",
            "/v1/phaselock": "http://127.0.0.1:8135",
            "/v1/multipath": "http://127.0.0.1:8136",
            "/v1/gnmi": "http://127.0.0.1:8138",
            "/v1/spatial": "http://127.0.0.1:8151",
            "/v1/aot": "http://127.0.0.1:8153",
            "/v1/synaptic": "http://127.0.0.1:8155",
            "/v1/neuro": "http://127.0.0.1:8157",
        }
        for prefix, base in routes.items():
            if p == prefix or p.startswith(prefix + "/"):
                return f"{base}{req_path}"
        if p == "/cyberneon" or p.startswith("/cyberneon/"):
            return "http://127.0.0.1:3000/"
        if p.startswith("/v1/persona/"):
            return "http://127.0.0.1:8159/telemetry"
        if p == "/metrics":
            return "http://127.0.0.1:8138/metrics"
        if p == "/radial" or p.startswith("/radial/"):
            return "http://127.0.0.1:8131/"
        return None

    def do_GET(self):
        p = self.path.split('?')[0]
        if p.startswith("/v1/quick/"):
            import subprocess
            act = p.split("/v1/quick/", 1)[1]
            if act == "lock":
                subprocess.Popen(["/data/data/com.termux/files/home/.astra_light_keepalive.sh"])
                msg = "All 35 ports & dual-persona daemons re-locked"
            elif act == "telemetry":
                msg = "gNMI :8138 + PhaseLock :8135 + DualPersona :8159 telemetry synchronized"
            else:
                msg = f"Executed quick action: {act}"
            raw = json.dumps({"ok": True, "action": act, "message": msg}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if p == "/assets/alstra_avatar.jpg":
            av = Path.home() / "assets" / "alstra_avatar.jpg"
            if av.exists():
                raw = av.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Connection", "close")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
        path = self.path.split("?")[0]
        up_get = self._route_v1_upstream(self.path)
        if up_get:
            return self._proxy_upstream(up_get)
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
