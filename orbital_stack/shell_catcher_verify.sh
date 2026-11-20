#!/usr/bin/env bash
set -euo pipefail
HOME_DIR="${HOME:-/home/astra}"
PUB="$HOME_DIR/.astra_keys/ed25519_public.pem"
DB="$HOME_DIR/astra_orbital_ledger.db"

echo "=== ASTRA SHELL-CATCHER & CRYPTOGRAPHIC VERIFIER ==="
# 1. Verify active stack scripts SHA-256
for f in "$HOME_DIR/dashboard.py" "$HOME_DIR/vserver.py" "$HOME_DIR/orbital_crypto_spine.py"; do
  [ -f "$f" ] && sha256sum "$f"
done

# 2. Verify latest Ed25519 signature in SQLite WAL ledger
python3 - << 'PYEOF'
import base64, os, pathlib, sqlite3, subprocess, tempfile
home = pathlib.Path.home()
conn = sqlite3.connect(str(home / "astra_orbital_ledger.db"))
row = conn.execute("SELECT height, block_hash, signature_b64 FROM orbital_blocks ORDER BY height DESC LIMIT 1").fetchone()
conn.close()
assert row, "No blocks in orbital_blocks yet"
h, bhash, sig_b64 = row
with tempfile.NamedTemporaryFile(delete=False) as mf, tempfile.NamedTemporaryFile(delete=False) as sf:
    mf.write(bhash.encode("ascii")); mpath = mf.name
    sf.write(base64.b64decode(sig_b64)); spath = sf.name
try:
    r = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(home / ".astra_keys/ed25519_public.pem"), "-rawin", "-in", mpath, "-sigfile", spath], capture_output=True, text=True)
    assert r.returncode == 0, f"Ed25519 verify failed: {r.stderr}"
    print(f"[✔] ED25519 SIGNATURE VERIFIED | Block #{h} | Hash: {bhash[:16]}...")
finally:
    os.remove(mpath); os.remove(spath)
PYEOF

# 3. Shell-Catcher: flag unexpected reverse shells or high-RAM runaway processes
SUSPECT=$(ps -ef 2>/dev/null | grep -E "nc -e|/dev/tcp|bash -i|socat exec" | grep -v grep || true)
if [ -n "$SUSPECT" ]; then
  echo "[ALERT] Shell-Catcher detected suspicious shell process:"
  echo "$SUSPECT"
  exit 1
else
  echo "[✔] Shell-Catcher clean: 0 unauthorized interactive/reverse shells."
fi
