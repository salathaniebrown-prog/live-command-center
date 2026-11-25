import asyncio, json, os, subprocess, time

STATE_FILE = os.path.expanduser("~/live-command-center/car_state.json")
PORTS = {
    "UPGRADE-CAR-BRIDGE": 8899,
    "UPGRADE-TRUST-8117": 8117,
    "UPGRADE-WEBHOOK-8115": 8115,
    "UPGRADE-ALPHA-8160": 8160,
    "UPGRADE-GATEWAY-8090": 8090,
    "UPGRADE-INGRESS-8088": 8088,
}
PROCS = {
    "UPGRADE-CAR-BRIDGE": "car_server.py",
    "UPGRADE-TRUST-8117": "trust_center_8117.py",
    "UPGRADE-WEBHOOK-8115": "webhook_listener_8115.py",
    "UPGRADE-PILOT": "universal_pilot.py",
    "UPGRADE-CAR-3D": "virtual_car_3d.py",
    "UPGRADE-TWIN-FLIGHT": "twin_flight_node.py",
    "UPGRADE-SPINE-V2": "telemetry_spine_v2.py",
}

def load_state():
    base = {
        "upgrade_tag": "ASTRA-V13-UPGRADE-LOCAL",
        "mode": "JET-CRUISE",
        "airspeed_kts": 290,
        "altitude_ft": 2500,
        "heading": 280,
        "kw_output": 320,
        "livery": "NEON-CYBER-CARBON",
        "local_url": "http://127.0.0.1:8899",
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                base.update(json.load(f))
        except Exception:
            pass
    base["upgrade_tag"] = "ASTRA-V13-UPGRADE-LOCAL"
    base["local_url"] = "http://127.0.0.1:8899"
    return base

def save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, STATE_FILE)

async def check_port(name, port):
    t0 = time.perf_counter()
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 0.25)
        w.close()
        await w.wait_closed()
        return name, {"port": port, "status": "ONLINE", "ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception:
        return name, {"port": port, "status": "OFFLINE", "ms": -1}

async def sync_all(st):
    ps_out = subprocess.getoutput("ps -ef")
    st["pm2"] = {label: ("ONLINE" if script in ps_out else "OFFLINE") for label, script in PROCS.items()}
    res = await asyncio.gather(*(check_port(k, v) for k, v in PORTS.items()))
    st["nodes"] = dict(sorted(res, key=lambda x: x["port"]))
    save_state(st)
    return st
