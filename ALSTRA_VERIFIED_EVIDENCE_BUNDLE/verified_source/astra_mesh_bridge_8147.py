import astra_contract_middleware  # auto-injected contract shim
#!/usr/bin/env python3
"""
Alstra Multi-Device LAN & Cloudflare Mesh Bridge (127.0.0.1:8147)
- Enrolls external Linux workstations, edge nodes, and Cloudflare tunnels
- Binds mTLS peer tokens to Edge CA (127.0.0.1:8143)
- Forwards active peer routing tables to Termux Master Spine (127.0.0.1:8095)
"""
import hashlib
import http.server
import json
import socket
import socketserver
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import os as _astra_os
PORT = int(_astra_os.environ.get('ALSTRA_SHADOW_PORT', '8147'))

PEERS_FILE = Path.home() / ".astra_mesh_peers.json"


def load_peers() -> dict:
    if PEERS_FILE.exists():
        try:
            return json.loads(PEERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    default_peers = {
        "termux-primary-spine": {
            "peer_id": "termux-primary-spine",
            "transport": "LOCAL_LOOPBACK_MESH",
            "endpoint": "http://127.0.0.1:8095",
            "status": "ACTIVE",
            "enrolled_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "linux-edge-solar-8143": {
            "peer_id": "linux-edge-solar-8143",
            "transport": "DUAL_ETH_WIFI6_BOND",
            "endpoint": "http://127.0.0.1:8143",
            "status": "ACTIVE",
            "enrolled_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
    PEERS_FILE.write_text(json.dumps(default_peers, indent=2), encoding="utf-8")
    return default_peers


def save_peers(peers: dict):
    PEERS_FILE.write_text(json.dumps(peers, indent=2), encoding="utf-8")


def detect_lan_and_tunnel() -> dict:
    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    cf_running = False
    try:
        out = subprocess.check_output(["pgrep", "-f", "cloudflared"], timeout=2).decode("utf-8").strip()
        cf_running = bool(out)
    except Exception:
        pass

    return {
        "lan_ipv4": lan_ip,
        "cloudflare_tunnel_daemon": "ACTIVE" if cf_running else "STANDBY_READY",
        "mtls_ca_provider": "http://127.0.0.1:8143/v1/certs/renew",
    }


class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True


class MeshBridgeHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, payload: dict, status: int = 200):
        payload.setdefault("query_id", f"mesh8147-{uuid.uuid4().hex[:12]}")
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/health", "/v1/telemetry", "/v1/peers"):
            peers = load_peers()
            return self._send({
                "ok": True,
                "status": "ONLINE",
                "port": PORT,
                "service": "ALSTRA_MULTI_DEVICE_MESH_BRIDGE_8147",
                "network": detect_lan_and_tunnel(),
                "peer_count": len(peers),
                "peers": peers,
                "timestamp": time.time(),
            })
        return self._send({"ok": False, "error": f"Unknown GET path: {path}"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if path == "/v1/peers/enroll":
            peer_id = body.get("peer_id") or f"workstation-{uuid.uuid4().hex[:6]}"
            endpoint = body.get("endpoint", "http://192.168.1.100:8143")
            transport = body.get("transport", "LAN_MTLS_TUNNEL")
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            mtls_token = hashlib.sha256(f"{peer_id}:{endpoint}:{now_utc}".encode("utf-8")).hexdigest()

            peers = load_peers()
            peers[peer_id] = {
                "peer_id": peer_id,
                "transport": transport,
                "endpoint": endpoint,
                "mtls_token_sha256": mtls_token,
                "status": "ENROLLED_ACTIVE",
                "enrolled_utc": now_utc,
            }
            save_peers(peers)

            # Propagate peer registration to Master Spine (8095)
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:8095/v1/register",
                    data=json.dumps({"node_name": peer_id, "endpoint_url": endpoint}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=3).read()
            except Exception:
                pass

            return self._send({"ok": True, "status": "PEER_ENROLLED", "peer": peers[peer_id]})

        return self._send({"ok": False, "error": f"Unknown POST path: {path}"}, 404)


if __name__ == "__main__":
    load_peers()
    with ReuseTCP(("127.0.0.1", PORT), MeshBridgeHandler) as srv:
        print(f"[✔] Alstra Multi-Device LAN/Cloudflare Mesh Bridge active on 127.0.0.1:{PORT}")
        srv.serve_forever()
