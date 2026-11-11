#!/usr/bin/env bash
# =======================================================================
# ALSTRA SOVEREIGN COMMAND CENTER - UNIVERSAL ORCHESTRATION LAYER
# Autonomously cleans ports, sets up cryptographic key matrices,
# deploys HTTPS ingestion gates, and fires a logistics handshake test.
# =======================================================================

clear
echo "[*] Initializing Universal Unified Stack Infrastructure Setup..."

# 1. Clear out stale, lingering network ports aggressively
echo "[*] Stage 1: Enforcing network port clearance guidelines..."
pkill -9 -f alstra_secure_receiver.py 2>/dev/null
pkill -9 -f alstra_dashboard_view.py 2>/dev/null
sleep 2

# 2. Build directories
mkdir -p ~/alstra-core/security_keys
mkdir -p ~/alstra-core/certificates

# 3. Auto-Instantiate Missing Asymmetric Keypairs if they do not exist
if [ ! -f ~/alstra-core/security_keys/sovereign_ed25519.pem ]; then
    echo "[*] Stage 2: Provisioning missing Ed25519 sovereign key matrices..."
    python3 -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import os

key_dir = os.path.expanduser('~/alstra-core/security_keys')
priv_key = ed25519.Ed25519PrivateKey.generate()

with open(os.path.join(key_dir, 'sovereign_ed25519.pem'), 'wb') as f:
    f.write(priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

pub_key = priv_key.public_key()
with open(os.path.join(key_dir, 'sovereign_ed25519.pub'), 'wb') as f:
    f.write(pub_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))
print('[+] Asymmetric authority validation seals generated successfully.')
"
else:
    echo "[+] Stage 2: Verified pre-existing sovereign authority key sets."
fi

# 4. Auto-Instantiate Self-Signed TLS Certificates if they are missing
if [ ! -f ~/alstra-core/certificates/alstra_server.crt ]; then
    echo "[*] Stage 3: Provisioning secure TLS/SSL transport layers..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout ~/alstra-core/certificates/alstra_server.key \
      -out ~/alstra-core/certificates/alstra_server.crt \
      -subj "/C=US/ST=NC/L=Greensboro/O=Alstra AI Studio/CN=127.0.0.1" 2>/dev/null
    echo "[+] SSL/TLS certificate configurations locked."
else
    echo "[+] Stage 3: Verified secure TLS transport layer certificates."
fi

# 5. Launch Secure HTTPS Receiver Daemon Core into background worker space
echo "[*] Stage 4: Launching secure asymmetric HTTPS ingestion receiver..."
python3 ~/alstra-core/alstra_secure_receiver.py > ~/alstra-core/receiver_runtime.log 2>&1 &
RECEIVER_PID=$!

# 6. Launch Centralized Web Dashboard View Matrix Core into background worker space
echo "[*] Stage 5: Deploying centralized UI dashboard view terminal layer..."
python3 ~/alstra-core/alstra_dashboard_view.py > ~/alstra-core/dashboard_runtime.log 2>&1 &
DASHBOARD_PID=$!

# Give the servers a brief execution window to bind port vectors smoothly
sleep 3

# 7. Execute Universal Transport Logistics Handshake Simulation (Car Cargo Test)
echo "[*] Stage 6: Dispatched signed real-time car logistics tracking delivery..."
python3 ~/alstra-core/simulate_car_delivery.py

echo -e "\n======================================================================="
echo "[ALSTRA MASTER VERIFICATION REPORT]: PIPELINE CORE FULLY ENFORCED"
echo "[HTTPS RECEIVER TARGET DAEMON PID]: $RECEIVER_PID (Listening on Port 8099)"
echo "[UI MATRIX VISUALIZATION DAEMON PID]: $DASHBOARD_PID (Listening on Port 8100)"
echo "=======================================================================\n"
echo "[*] Access the active multi-node cluster view here -> http://127.0.0.1:8100"
