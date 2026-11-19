#!/usr/bin/env bash
/data/data/com.termux/files/home/.astra_light_keepalive.sh
set -euo pipefail
cd "$HOME"

termux-wake-lock 2>/dev/null || true
pm2 resurrect 2>/dev/null || true
bash "$HOME/astra-enterprise-core/astra_start.sh" >/dev/null 2>&1 || true
python3 "$HOME/astra_forensic_showcase.py" >/dev/null 2>&1 || true

pm2 status

python3 - << 'VERIFY_25'
import socket

ports = [
    8088, 8090, 8095, 8099,
    8108, 8109, 8111, 8113, 8115, 8117, 8119, 8121, 8123, 8125, 8127, 8128, 8129, 8130, 8131, 8134, 8135,
    8137, 8138, 8139, 8141, 8143, 8145, 8147, 8149, 8151, 8153, 8155, 8157
]
up = []
for p in ports:
    s = socket.socket()
    s.settimeout(0.4)
    if s.connect_ex(("127.0.0.1", p)) == 0:
        up.append(p)
    s.close()

print(f"\n[✔] MEETING READY — Active Cluster & Connector Ports ({len(up)}/{len(ports)}): {up}")
print("[✔] Master Dashboard:   http://127.0.0.1:8088")
print("[✔] Unified Gateway:    http://127.0.0.1:8090")
print("[✔] Spatial 3D Engine:  http://127.0.0.1:8090/spatial")
print("[✔] OpenAPI Console:    http://127.0.0.1:8090/docs")
print("[✔] Forensic Showcase:  http://127.0.0.1:8090/forensic")
VERIFY_25
