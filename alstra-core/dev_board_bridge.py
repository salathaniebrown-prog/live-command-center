#!/usr/bin/env python3
import json
import random
import urllib.request
import time

TELEMETRY_ENDPOINT = "http://127.0.0.1:8099/api/agent/command"

class DevBoardHardwareBridge:
    def __init__(self, port_name="/dev/ttyACM0", baud_rate=115200):
        self.port_name = port_name
        self.baud_rate = baud_rate

    def poll_dev_board_sensors(self):
        # Simulated multi-protocol hardware packet (I2C / SPI / UART bus)
        return {
            "i2c_sensor_bus": {
                "temperature_c": round(random.uniform(24.5, 31.2), 2),
                "humidity_pct": round(random.uniform(40.0, 55.0), 2),
                "pressure_hpa": 1013.25
            },
            "spi_high_speed_bus": {
                "dac_output_v": round(random.uniform(1.2, 3.3), 3),
                "buffer_latency_us": 12.4
            },
            "uart_serial_stream": {
                "packet_id": random.randint(1000, 9999),
                "signal_integrity": "100_PERCENT_LOCKED"
            }
        }

    def sync_to_edge_daemon(self):
        hardware_metrics = self.poll_dev_board_sensors()
        
        payload = {
            "bridge_source": "DEV_BOARD_HARDWARE_INTERFACE",
            "communication_protocols": ["I2C", "SPI", "UART"],
            "metrics": hardware_metrics,
            "status": "SYNCHRONIZED_ZERO_ERROR"
        }

        data = json.dumps({
            "command": "Dev board multi-protocol hardware telemetry synchronized successfully",
            "speak": False,
            "payload": payload
        }).encode('utf-8')

        req = urllib.request.Request(
            TELEMETRY_ENDPOINT, 
            data=data, 
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode())
                print(f"[DEV BOARD BRIDGE]: {res.get('status')} -> Ingested multi-protocol hardware data.")
        except Exception as e:
            print(f"[!] Dev board bridge warning: Daemon unreachable ({e})")

if __name__ == "__main__":
    bridge = DevBoardHardwareBridge()
    bridge.sync_to_edge_daemon()
