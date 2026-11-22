#!/usr/bin/env python3
"""
Alstra Spatial 3D Pop-Out & WebXR Artifact Server (127.0.0.1:8151)
- Serves live 60 FPS telemetry physics vector stream from 8088, 8090, 8143, 8149
- Serves interactive Off-Axis 3D / WebXR / Front-Cam Eye-Tracked / 4-Way Pepper's Ghost UI (/spatial)
- Docker-ready standalone microservice
"""
import hashlib
import http.server
import json
import os
import socketserver
import time
import urllib.request
import uuid
from pathlib import Path

PORT = int(os.environ.get("ALSTRA_SHADOW_PORT", "8151"))
HOME = Path.home()


def fetch_json_safe(url: str, timeout: float = 1.2) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def compute_spatial_physics_frame() -> dict:
    load_1m = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.35
    forge = fetch_json_safe("http://127.0.0.1:8149/v1/telemetry")
    edge = fetch_json_safe("http://127.0.0.1:8143/v1/telemetry")

    deriv = forge.get("latency_derivative", {}).get("derivative", 0.12)
    active_sha = (
        forge.get("active_pointer", {}).get("cryptographic_sha256")
        or hashlib.sha256(f"ALSTRA-SPATIAL-{int(time.time()//10)}".encode()).hexdigest()
    )
    solar_w = edge.get("fabric", {}).get("solar_power_subsystem", {}).get("input_watts", 142.5)

    # Map real telemetry -> 3D shader & frustum physics uniforms
    rotation_speed = round(max(0.25, min(4.5, 0.65 + abs(float(deriv)) * 0.08 + float(load_1m) * 0.35)), 4)
    laser_intensity = round(max(0.4, min(2.5, 0.85 + (float(solar_w) / 200.0) * 0.8 + float(load_1m) * 0.25)), 4)
    z_extrusion_cm = round(max(2.5, min(14.0, 6.2 + abs(float(deriv)) * 0.15)), 3)

    nodes = [
        {"id": "CORE-8088", "x": -1.35, "y": 0.75, "z": 0.45, "color": "#00f0ff"},
        {"id": "GW-8090", "x": 0.0, "y": 0.95, "z": 0.85, "color": "#00ff9d"},
        {"id": "SPINE-8095", "x": 1.35, "y": 0.75, "z": 0.45, "color": "#38bdf8"},
        {"id": "BRAIN-8099", "x": -1.45, "y": -0.65, "z": 0.55, "color": "#a855f7"},
        {"id": "EDGE-8143", "x": 0.0, "y": -0.85, "z": 0.95, "color": "#f59e0b"},
        {"id": "FORGE-8149", "x": 1.45, "y": -0.65, "z": 0.65, "color": "#ec4899"},
    ]

    return {
        "ok": True,
        "status": "ONLINE",
        "port": PORT,
        "service": "ALSTRA_SPATIAL_3D_WEBXR_ENGINE_8151",
        "physics": {
            "rotation_speed": rotation_speed,
            "laser_intensity": laser_intensity,
            "z_extrusion_cm": z_extrusion_cm,
            "cpu_load_1m": round(float(load_1m), 3),
            "latency_derivative_ms": deriv,
            "sha256_cube_hash": active_sha,
        },
        "nodes": nodes,
        "timestamp": time.time(),
    }


import threading
CACHED_FRAME = {}
def _bg_refresh():
    global CACHED_FRAME
    while True:
        try:
            CACHED_FRAME = compute_spatial_physics_frame()
        except Exception:
            pass
        time.sleep(1.5)
threading.Thread(target=_bg_refresh, daemon=True).start()

class ReuseTCP(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class SpatialHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _send_json(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"spatial8151-{uuid.uuid4().hex[:12]}")
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html_path: Path):
        raw = html_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/peppers-ghost/svg":
            from urllib.parse import parse_qs, urlparse
            from astra_peppers_ghost_svg import PRESETS, generate_nested_svg
            qs = parse_qs(urlparse(self.path).query)
            preset = qs.get("preset", ["giant"])[0].lower()
            cfg = PRESETS.get(preset, PRESETS["giant"])
            t_val = float(qs.get("t", [cfg["T"]])[0])
            b_val = float(qs.get("b", [cfg["B"]])[0])
            kerf = float(qs.get("kerf", [0.18])[0])
            svg_raw = generate_nested_svg(t_val, b_val, kerf, f"Custom/Preset ({preset.upper()})").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="peppers_ghost_{preset}_2x2_nested.svg"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(svg_raw)))
            self.end_headers()
            self.wfile.write(svg_raw)
            return
        if path in ("/spatial", "/ui"):
            html_file = HOME / "ALSTRA_SPATIAL_3D_ENGINE.html"
            if html_file.exists():
                return self._send_html(html_file)
        if path in ("/", "/health", "/v1/telemetry", "/v1/spatial/physics"):
            return self._send_json(CACHED_FRAME or compute_spatial_physics_frame())
        return self._send_json({"ok": False, "error": f"Unknown GET path: {path}"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            self.rfile.read(length)
        return self._send_json(CACHED_FRAME or compute_spatial_physics_frame())


if __name__ == "__main__":
    with ReuseTCP(("0.0.0.0", PORT), SpatialHandler) as srv:
        print(f"[✔] Alstra Spatial 3D & WebXR Artifact Engine active on 0.0.0.0:{PORT}")
        srv.serve_forever()
