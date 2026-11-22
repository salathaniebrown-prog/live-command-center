#!/usr/bin/env python3
"""
Salathanie A.I — Trinity Assistant Core (The Heart, The Brain, The Driver)
Unified low-RAM control plane for Edge, GitHub, Linux, and VR/Spatial Telemetry.
"""
import json
import os
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv
from semantic_router import route_request

REPO = "/data/data/com.termux/files/home/live-command-center"
PREFERRED_PORT = 8126
ACTIVE_PORT = PREFERRED_PORT


class TheHeart:
    """Pulse, RAM Guard, and Zero-Copy HDC Ring / VR Data Frame emitter."""

    @staticmethod
    def mem_avail_mb() -> int:
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
        except OSError:
            pass
        return 0

    @classmethod
    def pulse(cls, event_label: str = "trinity:pulse") -> dict:
        mem_mb = cls.mem_avail_mb()
        safe_mode = 0 < mem_mb < 380
        ring = {"seq": 0, "hmac_ok": False, "active_nodes": {}}
        try:
            with HDCSharedMemoryBus() as bus:
                bus.publish("salathanie-trinity", ACTIVE_PORT, 200, deterministic_hv(event_label))
                ring["active_nodes"] = bus.snapshot_active_ports()
                with bus.read_latest_view() as rec:
                    if rec:
                        ring["seq"] = rec["seq"]
                        ring["hmac_ok"] = bool(rec.get("hmac_ok"))
        except Exception as e:
            ring["error"] = str(e)
        return {"ts": int(time.time()), "mem_avail_mb": mem_mb, "safe_mode": safe_mode, "ring": ring}

    @classmethod
    def vr_data_frame(cls) -> dict:
        """Emit a circular VR/Spatial telemetry frame of all active nodes."""
        p = cls.pulse("trinity:vr_frame")
        nodes = p["ring"].get("active_nodes", {})
        circle = []
        total = max(1, len(nodes))
        for idx, (name, info) in enumerate(nodes.items()):
            angle_deg = round((360.0 / total) * idx, 1)
            circle.append({
                "node": name,
                "port": info["port"],
                "seq": info["seq"],
                "angle_deg": angle_deg,
                "radius": 1.0 if info["status"] == 200 else 0.5,
            })
        return {
            "ts": p["ts"],
            "attested": p["ring"].get("hmac_ok", False),
            "mem_avail_mb": p["mem_avail_mb"],
            "vr_circle_nodes": circle,
        }


class TheBrain:
    """Semantic intent classifier & action planner."""

    @staticmethod
    def plan(command: str) -> dict:
        cmd_l = command.strip().lower()
        semantic = route_request(command)
        if any(k in cmd_l for k in ("git", "github", "commit", "push", "pull", "repo")):
            domain = "github"
        elif any(k in cmd_l for k in ("pm2", "edge", "tunnel", "recover", "heal", "restart")):
            domain = "edge"
        elif any(k in cmd_l for k in ("vr", "3d", "spatial", "circle", "frame")):
            domain = "vr_data"
        else:
            domain = "linux"
        return {"command": command, "domain": domain, "semantic_route": semantic}


class TheDriver:
    """Safe, allowlisted executor for Edge, GitHub, and Linux control."""

    @staticmethod
    def _run(args: list[str], cwd: str = REPO, timeout: int = 12) -> dict:
        try:
            res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            return {
                "ok": res.returncode == 0,
                "code": res.returncode,
                "stdout": res.stdout.strip()[-1200:],
                "stderr": res.stderr.strip()[-400:],
            }
        except Exception as e:
            return {"ok": False, "code": -1, "error": str(e)}

    @classmethod
    def execute(cls, plan: dict) -> dict:
        mem_mb = TheHeart.mem_avail_mb()
        if 0 < mem_mb < 350:
            return {"ok": False, "blocked": "RAM Safe-Mode active (<350MB free)"}

        domain = plan["domain"]
        cmd = plan["command"].lower()

        if domain == "github":
            if "pull" in cmd or "sync" in cmd:
                out = cls._run(["git", "pull", "--rebase", "origin", "main"])
            elif "log" in cmd:
                out = cls._run(["git", "log", "-n", "5", "--oneline"])
            else:
                out = cls._run(["git", "status", "-sb"])
        elif domain == "edge":
            if "recover" in cmd or "heal" in cmd:
                out = cls._run(["bash", f"{REPO}/salathanie_recover.sh"], timeout=20)
            else:
                out = cls._run(["pm2", "jlist"])
        elif domain == "vr_data":
            out = {"ok": True, "frame": TheHeart.vr_data_frame()}
        else:
            if "disk" in cmd or "df" in cmd:
                out = cls._run(["df", "-h", REPO])
            elif "uptime" in cmd:
                out = cls._run(["uptime"])
            else:
                out = cls._run(["free", "-m"])

        # Close the circle: write execution state back into The Heart
        TheHeart.pulse(f"driver:{domain}:{'ok' if out.get('ok') else 'err'}")
        return {"domain": domain, "result": out}


class TrinityHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/health", "/api/trinity/heart"):
            return self._send(200, {"service": "salathanie-trinity", "heart": TheHeart.pulse()})
        if parsed.path == "/api/trinity/vr-frame":
            return self._send(200, TheHeart.vr_data_frame())
        if parsed.path == "/api/trinity/dispatch":
            qs = urllib.parse.parse_qs(parsed.query)
            cmd = qs.get("cmd", ["linux free"])[0]
            plan = TheBrain.plan(cmd)
            exec_res = TheDriver.execute(plan)
            return self._send(200, {"brain": plan, "driver": exec_res})
        return self._send(404, {"error": "not_found"})


if __name__ == "__main__":
    with HDCSharedMemoryBus() as bus:
        ACTIVE_PORT = bus.allocate_port(PREFERRED_PORT)
        bus.publish("salathanie-trinity", ACTIVE_PORT, 200, deterministic_hv(f"trinity:{ACTIVE_PORT}:UP"))
    print(f"[OK] Salathanie Trinity (Heart/Brain/Driver) live on 0.0.0.0:{ACTIVE_PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", ACTIVE_PORT), TrinityHandler).serve_forever()
