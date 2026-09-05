import asyncio
import os
import struct

from aiokafka import AIOKafkaProducer

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:19092")
TELEMETRY_TOPIC = os.getenv("TELEMETRY_TOPIC", "eagle.eyes.field.telemetry")
FRAME_FORMAT = ">Qddff"


async def simulate_uplink():
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
    await producer.start()
    print(f"Uplink active -> {KAFKA_BROKER} / {TELEMETRY_TOPIC}")

    seq_id = 0
    lat, lon, alt = 35.6895, 139.6917, 120.0
    moisture = 0.35

    try:
        while True:
            seq_id += 1
            lat += 0.00001
            lon += 0.000015
            alt += 0.05

            packet = struct.pack(
                FRAME_FORMAT,
                seq_id,
                lat,
                lon,
                alt,
                moisture,
            )
            await producer.send_and_wait(TELEMETRY_TOPIC, packet)

            if seq_id % 20 == 0:
                print(f"Dispatched frame {seq_id}")

            await asyncio.sleep(0.05)
    finally:
        await producer.stop()


if __name__ == "__main__":
    try:
        asyncio.run(simulate_uplink())
    except KeyboardInterrupt:
        print("Uplink simulator stopped")
