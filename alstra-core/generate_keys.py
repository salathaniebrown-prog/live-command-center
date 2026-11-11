from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import os

# Generate keys
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Save Private Key
with open("alstra_private_key.pem", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

# Save Public Key
with open("alstra_public_key.pem", "wb") as f:
    f.write(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))

print("[+] SOVEREIGN KEYS GENERATED: alstra_private_key.pem & alstra_public_key.pem")
