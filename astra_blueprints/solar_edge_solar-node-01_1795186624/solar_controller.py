import json, time
# Edge Solar + Battery MPPT Actuation Loop
def actuate(batt_pct, solar_w, load_w):
    if batt_pct < 25:
        return {"mode": "POWER_SAVE", "throttle_gpu": True, "relay": "OFF"}
    if solar_w > load_w and batt_pct > 85:
        return {"mode": "SURPLUS_COMPUTE", "throttle_gpu": False, "relay": "ON"}
    return {"mode": "BALANCED", "throttle_gpu": False, "relay": "ON"}

if __name__ == "__main__":
    print(json.dumps(actuate(92, 420, 180)))
