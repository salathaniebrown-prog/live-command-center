import glob, http.server, json, os, pathlib, socketserver, subprocess, time, urllib.parse

PORT = 8101
VAULT_PATH = pathlib.Path.home() / ".astra_teleport_vault.json"

def read_file_safe(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None

def get_hw_telemetry():
    # Memory
    total, avail = 1, 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"): total = int(line.split()[1])
                elif line.startswith("MemAvailable:"): avail = int(line.split()[1]); break
    except OSError:
        pass
    ram_pct = round(((total - avail) / max(total, 1)) * 100.0, 1)

    # Thermal (sysfs thermal zones)
    temps = []
    for p in glob.glob("/sys/class/thermal/thermal_zone*/temp")[:12]:
        v = read_file_safe(p)
        if v and v.lstrip("-").isdigit():
            c = int(v) / 1000.0 if int(v) > 200 else float(v)
            if 10.0 < c < 115.0:
                temps.append(c)
    soc_temp_c = round(max(temps), 1) if temps else None

    # Battery (sysfs fallback -> termux-battery-status optional)
    batt_pct = read_file_safe("/sys/class/power_supply/battery/capacity")
    batt_temp = read_file_safe("/sys/class/power_supply/battery/temp")
    batt_pct = int(batt_pct) if batt_pct and batt_pct.isdigit() else None
    batt_temp_c = round(int(batt_temp) / 10.0, 1) if batt_temp and batt_temp.lstrip("-").isdigit() else None

    # GPU / NPU probe (Adreno kgsl / Mali / generic devfreq)
    gpu_busy = read_file_safe("/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage")
    if gpu_busy:
        gpu_pct = float(gpu_busy.replace("%", "").strip())
    else:
        gpu_pct = None
    npu_present = any(os.path.exists(p) for p in ("/dev/adsprpc-smd", "/dev/npu0", "/sys/class/devfreq"))

    # Network I/O
    rx, tx = 0, 0
    try:
        with open("/proc/net/dev", "r") as f:
            for line in f.readlines()[2:]:
                if ":" in line:
                    iface, rest = line.split(":", 1)
                    if iface.strip() != "lo":
                        cols = rest.split()
                        if len(cols) >= 9:
                            rx += int(cols[0]); tx += int(cols[8])
    except OSError:
        pass

    try:
        load1 = round(os.getloadavg()[0], 2)
    except OSError:
        load1 = 0.0

    return {
        "ts": int(time.time()),
        "ram_pct": ram_pct,
        "ram_avail_mb": avail // 1024,
        "load1": load1,
        "cores": os.cpu_count() or 1,
        "soc_temp_c": soc_temp_c,
        "batt_pct": batt_pct,
        "batt_temp_c": batt_temp_c,
        "gpu_pct": gpu_pct,
        "npu_ready": npu_present,
        "net_rx_kb": rx // 1024,
        "net_tx_kb": tx // 1024,
    }

def load_vault():
    if VAULT_PATH.exists():
        try:
            return json.loads(VAULT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"default": {"state": {}, "updated_at": 0, "device": "astra-termux"}}

def save_vault(data):
    tmp = VAULT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, VAULT_PATH)

class VServerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _json(self, code, obj):
        raw = json.dumps(obj).encode("utf-8")
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
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/health", "/api/hw"):
            return self._json(200, {"ok": True, "service": "astra-vserver-8101", "hw": get_hw_telemetry()})
        if u.path in ("/teleport/pull", "/pull"):
            slot = urllib.parse.parse_qs(u.query).get("slot", ["default"])[0]
            vault = load_vault()
            entry = vault.get(slot)
            if not entry:
                return self._json(404, {"ok": False, "error": f"Slot '{slot}' not found", "slots": list(vault.keys())})
            return self._json(200, {"ok": True, "slot": slot, **entry})
        self._json(404, {"ok": False, "error": "Not Found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        if self.path in ("/teleport/push", "/push"):
            slot = str(body.get("slot", "default"))[:64]
            vault = load_vault()
            vault[slot] = {
                "state": body.get("state", body),
                "device": body.get("device", "astra-termux"),
                "updated_at": int(time.time()),
            }
            save_vault(vault)
            return self._json(200, {"ok": True, "action": "pushed", "slot": slot, "updated_at": vault[slot]["updated_at"]})
        if self.path == "/run":
            code = body.get("code", "")
            p = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=6)
            return self._json(200, {"ok": p.returncode == 0, "output": (p.stdout + p.stderr).strip()})
        self._json(404, {"ok": False, "error": "Not Found"})

if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer(("0.0.0.0", PORT), VServerHandler).serve_forever()
