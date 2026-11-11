import json
import subprocess
import time
from datetime import datetime

REAL_LOG = "/data/data/com.termux/files/home/REAL.log"

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
        "device_temp_c": battery.get("temperature", -1),
        "wifi_ssid": wifi.get("ssid", "DISCONNECTED"),
        "wifi_rssi": wifi.get("rssi", 0),
        "link_speed_mbps": wifi.get("link_speed_mbps", 0)
    }

if __name__ == "__main__":
    while True:
        data = collect_android_telemetry()
        line = (
            f"[{datetime.now().strftime('%H:%M:%S')}] ANDROID_TELEMETRY "
            f"BAT:{data['battery_pct']}% ({data['battery_status']}) "
            f"TEMP:{data['device_temp_c']}C WIFI:{data['link_speed_mbps']}Mbps\n"
        )
        with open(REAL_LOG, "a") as f:
            f.write(line)
        time.sleep(30)
