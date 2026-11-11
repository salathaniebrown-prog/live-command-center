import os
import sys
import json
import subprocess
import time
from datetime import datetime

sys.path.append(os.path.expanduser("~/astra-memory-brain"))
from self_improve import generate_new_idea

REAL_LOG = os.path.expanduser("~/REAL.log")
COOLDOWN_SECONDS = 14400  # 4 hours between automated 177B synthesis runs
last_idea_ts = 0.0

def run_termux_cmd(cmd: list) -> dict:
    try:
        out = subprocess.check_output(cmd, timeout=5, stderr=subprocess.DEVNULL).decode("utf-8")
        return json.loads(out)
    except Exception:
        return {}

def collect_android_telemetry() -> dict:
    battery = run_termux_cmd(["termux-battery-status"])
    wifi = run_termux_cmd(["termux-wifi-connectioninfo"])
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "battery_pct": battery.get("percentage", -1),
        "battery_status": battery.get("status", "UNKNOWN"),
        "plugged": battery.get("plugged", "UNPLUGGED"),
        "device_temp_c": float(battery.get("temperature", -1)),
        "wifi_ssid": wifi.get("ssid", "DISCONNECTED"),
        "wifi_rssi": wifi.get("rssi", 0),
        "link_speed_mbps": int(wifi.get("link_speed_mbps", 0))
    }

def get_recent_telemetry(lines: int = 50) -> str:
    if not os.path.exists(REAL_LOG):
        return "System nominal. All 6 engines active."
    with open(REAL_LOG, "r", encoding="utf-8", errors="ignore") as f:
        return "".join(f.readlines()[-lines:])

if __name__ == "__main__":
    while True:
        data = collect_android_telemetry()
        now_str = datetime.now().strftime("%H:%M:%S")
        line = (
            f"[{now_str}] ANDROID_TELEMETRY "
            f"BAT:{data['battery_pct']}% ({data['battery_status']}/{data['plugged']}) "
            f"TEMP:{data['device_temp_c']}C WIFI:{data['link_speed_mbps']}Mbps\n"
        )
        with open(REAL_LOG, "a", encoding="utf-8") as f:
            f.write(line)

        # Automated Charging + Wi-Fi + Thermal Safety Trigger
        is_charging = data["battery_status"] in ("CHARGING", "FULL") or data["plugged"] != "UNPLUGGED"
        on_wifi = data["link_speed_mbps"] > 0 and data["wifi_ssid"] not in ("", "DISCONNECTED", "<unknown ssid>")
        cool_enough = data["device_temp_c"] < 42.0
        cooldown_ready = (time.time() - last_idea_ts) >= COOLDOWN_SECONDS

        if is_charging and on_wifi and cool_enough and cooldown_ready:
            with open(REAL_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{now_str}] 177B_AUTO_TRIGGER Device charging on Wi-Fi. Synthesizing blueprint...\n")
            try:
                snapshot = get_recent_telemetry(50)
                generate_new_idea(snapshot)
                last_idea_ts = time.time()
                with open(REAL_LOG, "a", encoding="utf-8") as f:
                    f.write(f"[{now_str}] 177B_AUTO_TRIGGER Blueprint saved to episodic_reflexion.db\n")
            except Exception as e:
                with open(REAL_LOG, "a", encoding="utf-8") as f:
                    f.write(f"[{now_str}] 177B_AUTO_TRIGGER_ERROR {str(e)}\n")

        time.sleep(30)
