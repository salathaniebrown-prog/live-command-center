#!/usr/bin/env python3
import json
import os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8080"))
API_BASE = os.environ.get("API_BASE", "").strip().rstrip("/")
ALLOWED_API_PATHS = {
    "/api/status",
    "/api/metrics",
    "/api/health",
    "/api/deployment",
}


class DashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/dashboard-health":
            return self._json(200, {
                "ok": True,
                "service": "railway-visual-dashboard",
                "mode": "read-only",
                "upstreamConfigured": bool(API_BASE),
            })

        if path == "/dashboard-meta":
            return self._json(200, {
                "name": "Salathaniel Command Center",
                "mode": "read-only",
                "realOnly": True,
                "allowedApiPaths": sorted(ALLOWED_API_PATHS),
            })

        if path.startswith("/api/"):
            if path not in ALLOWED_API_PATHS:
                return self._json(403, {"error": "endpoint not allowed", "path": path})
            if not API_BASE:
                return self._json(503, {"error": "API_BASE is not configured", "path": path})

            target = API_BASE + path
            try:
                req = Request(
                    target,
                    method="GET",
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Salathaniel-Command-Dashboard/1.0",
                    },
                )
                with urlopen(req, timeout=8) as response:
                    data = response.read()
                    self.send_response(response.status)
                    self.send_header(
                        "Content-Type",
                        response.headers.get("Content-Type", "application/json"),
                    )
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            except HTTPError as exc:
                return self._json(exc.code, {
                    "error": "upstream HTTP error",
                    "status": exc.code,
                    "path": path,
                })
            except (URLError, TimeoutError, OSError) as exc:
                return self._json(502, {
                    "error": "upstream unavailable",
                    "detail": str(exc),
                    "path": path,
                })
            return

        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        return self._json(405, {"error": "read-only dashboard"})

    def do_PUT(self):
        return self._json(405, {"error": "read-only dashboard"})

    def do_PATCH(self):
        return self._json(405, {"error": "read-only dashboard"})

    def do_DELETE(self):
        return self._json(405, {"error": "read-only dashboard"})

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        return str(STATIC / clean)

    def log_message(self, fmt, *args):
        print("dashboard:", fmt % args, flush=True)


if __name__ == "__main__":
    print(f"dashboard listening on {HOST}:{PORT}", flush=True)
    print(f"upstream configured: {bool(API_BASE)}", flush=True)
    ThreadingHTTPServer((HOST, PORT), DashboardHandler).serve_forever()
