#!/usr/bin/env python3
"""
Alstra Sovereign Secure HTTPS Receiver (V4 - Long-Term Aggregation Integrated)
Validates Ed25519 seals, updates live node matrices, and appends every transit
milestone to an immutable historical SQLite ledger.
"""

import os
import json
import sqlite3
import time
import sys
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer
from cryptography.hazmat.primitives import serialization

DB_PATH = os.path.expanduser("~/alstra-core/alstra_core.db")
KEY_DIR = os.path.expanduser("~/alstra-core/security_keys")
CERT_DIR = os.path.expanduser("~/alstra-core/certificates")
ERROR_LOG = os.path.expanduser("~/alstra-core/secure_receiver_errors.log")
HOST = "0.0.0.0"
PORT = 8099

class SecureWebhookHandler(BaseHTTPRequestHandler):
    def _log_security_incident(self, message: str):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(ERROR_LOG, "a") as f:
            f.write(f"[{timestamp}] SECURITY EXCEPTION: {message}\n")

    def _verify_crypto_seal(self, signature_hex: str, payload_string: str) -> bool:
        pub_path = os.path.join(KEY_DIR, "sovereign_ed25519.pub")
        if not os.path.exists(pub_path):
            return False
        try:
            with open(pub_path, "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
            public_key.verify(bytes.fromhex(signature_hex), payload_string.encode('utf-8'))
            return True
        except Exception as e:
            self._log_security_incident(f"Signature mismatch verification failure: {e}")
            return False

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        signature_hex = self.headers.get('X-Alstra-Signature-Ed25519', 'UNSIGNED')
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        if self.path == "/api/global_transit":
            vin = payload.get("vin_id", "UNKNOWN_VIN")
            status = payload.get("transit_status", "STAGING")
            coords = payload.get("gps_coordinates", "0.0000,0.0000")
            authority = payload.get("operator_authority", "Salathaniel S A Brown Sr.")
            nonce = str(payload.get("nonce_sequence", ""))

            verification_string = f"{nonce}:{vin}:{status}"
            if not self._verify_crypto_seal(signature_hex, verification_string):
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"status":"REJECTED","reason":"CRYPTO_SEAL_INVALID"}')
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            
            # 1. Update Current Live Snapshot
            cursor.execute("""
                INSERT INTO asset_delivery_ledger (vin_id, operator_authority, transit_status, gps_coordinates, last_handshake_utc, payload_signature)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(vin_id) DO UPDATE SET
                    transit_status=excluded.transit_status,
                    gps_coordinates=excluded.gps_coordinates,
                    last_handshake_utc=excluded.last_handshake_utc,
                    payload_signature=excluded.payload_signature
            """, (vin, authority, status, coords, timestamp, signature_hex))

            # 2. Append Immutable Long-Term Historical Record
            cursor.execute("""
                INSERT INTO asset_transit_history (vin_id, operator_authority, transit_status, gps_coordinates, recorded_at_utc, payload_signature)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (vin, authority, status, coords, timestamp, signature_hex))
            
            # 3. Update Cluster Mesh Status
            cursor.execute("""
                INSERT INTO node_cluster_states (node_id, node_type, status, latency, last_seen)
                VALUES (?, 'External Transit Array', 'status-syncing', '24ms', ?)
                ON CONFLICT(node_id) DO UPDATE SET status='status-syncing', last_seen=excluded.last_seen
            """, (f"CAR-DELIVERY-{vin[-6:]}", timestamp))
            
            conn.commit()
            conn.close()

            print(f"[⚡] ARCHIVED & SYNCED -> VIN: {vin} | STATUS: {status} | COORDS: {coords}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"GLOBAL_TRANSIT_ARCHIVED_AND_COMMITTED"}')
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args): return

def launch_receiver():
    server = HTTPServer((HOST, PORT), SecureWebhookHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=os.path.join(CERT_DIR, "alstra_server.crt"), keyfile=os.path.join(CERT_DIR, "alstra_server.key"))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"[⚡] Secure Global Ingestion & Archive Server active on -> https://localhost:{PORT}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass

if __name__ == "__main__": launch_receiver()
