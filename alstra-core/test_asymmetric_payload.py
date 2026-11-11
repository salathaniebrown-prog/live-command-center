#!/usr/bin/env python3
"""
Alstra Sovereign Infrastructure Matrix Test Client
Signs a simulation payload using your localized Ed25519 private authority key
and pipes it directly into the running visual dashboard panel listener.
"""

import os
import json
import time
import urllib.request
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

KEY_DIR = os.path.expanduser("~/alstra-core/security_keys")
TARGET_URL = "http://127.0.0.1:8099"

def fire_signed_test_payload():
    private_key_path = os.path.join(KEY_DIR, "sovereign_ed25519.pem")
    
    # 1. Verify that your authority keypair has been provisioned
    if not os.path.exists(private_key_path):
        print("[!] Execution error: Ed25519 authority private key file not found.")
        print("[*] Please run 'python3 ~/alstra-core/alstra_crypto_gate.py' first to generate keys.")
        return

    # 2. Extract key data from storage
    with open(private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    # 3. Assemble simulation world-building tracking data
    test_nonce = int(time.time())
    test_command = "SIMULATE_WORLD_GRID_INITIALIZATION"
    
    payload_data = {
        "alert_level": "SUCCESS_VERIFIED",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root_authority": "Salathaniel S A Brown Sr.",
        "message": "Manual pipeline validation ping across local host interface.",
        "system_state": {
            "target_node": "TERMUX-NODE-PRIMARY",
            "active_command_vector": test_command,
            "nonce_sequence": test_nonce,
            "simulation_matrix_depth": "8_WORKER_PIPELINES_SATURATED"
        }
    }
    
    # 4. Generate asymmetric cryptographic signature matching your engine specs
    signing_bytes = f"{test_nonce}:{test_command}".encode('utf-8')
    signature_hex = private_key.sign(signing_bytes).hex()
    
    # 5. Route payload data across local network sockets
    json_bytes = json.dumps(payload_data).encode('utf-8')
    req = urllib.request.Request(TARGET_URL, data=json_bytes, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Alstra-Signature-Ed25519", signature_hex)

    print(f"[*] Dispatching signed simulation packet to monitor panel at {TARGET_URL}...")
    print(f"[*] Cryptographic Signature Prefix: {signature_hex[:32]}...")

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            print(f"\n[⚡] PORT RESPONSE: HTTP {status_code}")
            print(f"[⚡] RETURNED LEDGER CORE STATUS: {response_body}")
    except Exception as e:
        print(f"\n[!] Delivery failed: {e}")
        print("[*] Ensure your monitor dashboard is active by running: python3 ~/alstra-core/alstra_monitor_panel.py")

if __name__ == "__main__":
    fire_signed_test_payload()
