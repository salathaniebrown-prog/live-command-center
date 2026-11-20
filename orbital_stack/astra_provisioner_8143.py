import hashlib, http.server, json, os, pathlib, socketserver, time

PORT = 8143
OUT_DIR = pathlib.Path.home() / "astra_blueprints"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATES = {
    "gpu_datacenter": {
        "docker-compose.gpu.yml": """services:
  astra-gpu-node:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    ports:
      - "8000:8000"
    restart: unless-stopped
""",
        "main.tf": """terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
resource "aws_instance" "astra_gpu_node" {
  ami           = "ami-0c7217cdde317cfec"
  instance_type = "g5.xlarge"
  tags = { Name = "ASTRA-GPU-Datacenter-Node", ManagedBy = "ASTRA-8143" }
}
"""
    },
    "supercomputer": {
        "ray-cluster.yaml": """cluster_name: astra-supercomputer
max_workers: 16
head_node_type: gpu_head
available_node_types:
  gpu_head:
    resources: {"CPU": 16, "GPU": 2}
  gpu_worker:
    resources: {"CPU": 32, "GPU": 4}
    min_workers: 2
    max_workers: 16
""",
        "slurm_submit.sh": """#!/usr/bin/env bash
#SBATCH --job-name=astra_hpc
#SBATCH --nodes=4
#SBATCH --gres=gpu:4
#SBATCH --time=24:00:00
srun python3 train_distributed.py
"""
    },
    "solar_edge": {
        "solar_controller.py": """import json, time
# Edge Solar + Battery MPPT Actuation Loop
def actuate(batt_pct, solar_w, load_w):
    if batt_pct < 25:
        return {"mode": "POWER_SAVE", "throttle_gpu": True, "relay": "OFF"}
    if solar_w > load_w and batt_pct > 85:
        return {"mode": "SURPLUS_COMPUTE", "throttle_gpu": False, "relay": "ON"}
    return {"mode": "BALANCED", "throttle_gpu": False, "relay": "ON"}

if __name__ == "__main__":
    print(json.dumps(actuate(92, 420, 180)))
""",
        "edge-systemd.service": """[Unit]
Description=ASTRA Solar Edge Telemetry & Actuator
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/astra/solar_controller.py
Restart=always

[Install]
WantedBy=multi-user.target
"""
    },
    "pc_node": {
        "cloud-init.yaml": """#cloud-config
hostname: astra-workstation
packages:
  - docker.io
  - python3-pip
  - nvidia-container-toolkit
runcmd:
  - systemctl enable --now docker
  - echo "ASTRA PC Node Provisioned" > /etc/motd
"""
    },
    "ai_agent": {
        "agent_manifest.json": json.dumps({
            "name": "astra-autonomous-agent",
            "control_plane": "http://127.0.0.1:8090",
            "memory_db": "sqlite+wal",
            "gpu_offload": True,
            "capabilities": ["provision", "self_heal", "telemetry", "crypto_sign"]
        }, indent=2)
    }
}

def provision(target, name="node"):
    if target not in TEMPLATES:
        return {"ok": False, "error": f"Unknown target '{target}'", "valid_targets": list(TEMPLATES.keys())}
    ts = int(time.time())
    safe_name = "".join(c for c in name if c.isalnum() or c in "-_")[:32] or "node"
    bundle_dir = OUT_DIR / f"{target}_{safe_name}_{ts}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fname, content in TEMPLATES[target].items():
        fpath = bundle_dir / fname
        fpath.write_text(content, encoding="utf-8")
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        written.append({"file": str(fpath), "sha256_16": sha, "bytes": len(content)})
    return {"ok": True, "target": target, "bundle_dir": str(bundle_dir), "artifacts": written}

class ProvisionerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _json(self, code, obj):
        raw = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        bundles = sorted([p.name for p in OUT_DIR.iterdir() if p.is_dir()])[-20:]
        self._json(200, {
            "ok": True,
            "service": "astra-provisioner-8143",
            "mode": "READ_WRITE_CONTROL_PLANE",
            "targets": list(TEMPLATES.keys()),
            "gpu_local_probe": os.path.exists("/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage"),
            "provisioned_bundles": bundles
        })

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        target = body.get("target", "gpu_datacenter")
        name = body.get("name", "alpha")
        res = provision(target, name)
        self._json(200 if res.get("ok") else 400, res)

if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("0.0.0.0", PORT), ProvisionerHandler).serve_forever()
