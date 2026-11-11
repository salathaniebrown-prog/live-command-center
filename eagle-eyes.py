import time
import json
import random
import urllib.request

class EagleEyesDroneDaemon:
    def __init__(self):
        self.drone_id = "DRONE-EAGLE-EYES-01"
        self.ports = [3000, 3001]

    def get_telemetry_packet(self):
        return {
            "drone_id": self.drone_id,
            "altitude_m": round(random.uniform(120.5, 155.0), 2),
            "velocity_mps": round(random.uniform(12.0, 18.5), 2),
            "gps_lat": round(36.0726 + random.uniform(-0.001, 0.001), 6),
            "gps_lng": round(-79.7920 + random.uniform(-0.001, 0.001), 6),
            "battery_pct": round(random.uniform(88.0, 99.5), 1),
            "status": "PATROL_ACTIVE",
            "timestamp": time.time()
        }

    def dispatch_packet(self):
        packet = self.get_telemetry_packet()
        data = json.dumps(packet).encode('utf-8')
        for port in self.ports:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/logs", 
                    data=data, 
                    headers={'Content-Type': 'application/json'}
                )
                urllib.request.urlopen(req, timeout=1)
            except Exception:
                pass
        print(f"[{time.strftime('%X')}] Packet Sent: Alt {packet['altitude_m']}m | Batt {packet['battery_pct']}%")

if __name__ == "__main__":
    daemon = EagleEyesDroneDaemon()
    while True:
        daemon.dispatch_packet()
        time.sleep(3)
