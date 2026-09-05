import asyncio
import json
import logging
import os
import struct
import time

import websockets
from aiokafka import AIOKafkaProducer

from eagle_eyes_telemetry_spine import (
    FRAME_FORMAT,
    KAFKA_BROKER,
    TELEMETRY_TOPIC,
    WEBSOCKET_PORT,
    TelemetrySpineServer,
)

logger = logging.getLogger("EagleEyesTelemetrySmokeTest")
SELF_TEST_FRAMES = int(os.getenv("TELEMETRY_SELF_TEST_FRAMES", "0"))


async def wait_for_consumer(server: TelemetrySpineServer, timeout_s: float = 20.0):
    deadline = asyncio.get_running_loop().time() + timeout_s
    while server.consumer is None:
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("telemetry consumer did not become ready")
        await asyncio.sleep(0.1)


async def run_end_to_end_self_test(server: TelemetrySpineServer, frame_count: int):
    await wait_for_consumer(server)

    websocket_url = f"ws://127.0.0.1:{WEBSOCKET_PORT}"
    sequence_base = int(time.time() * 1000) * 1000
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)

    await producer.start()
    try:
        async with websockets.connect(websocket_url, open_timeout=10) as socket:
            passed = 0
            lat, lon, alt = 35.6895, 139.6917, 120.0
            moisture = 0.35

            for index in range(frame_count):
                sequence_id = sequence_base + index + 1
                lat += 0.00001
                lon += 0.000015
                alt += 0.05

                packet = struct.pack(
                    FRAME_FORMAT,
                    sequence_id,
                    lat,
                    lon,
                    alt,
                    moisture,
                )
                await producer.send_and_wait(TELEMETRY_TOPIC, packet)

                while True:
                    raw_message = await asyncio.wait_for(socket.recv(), timeout=5)
                    message = json.loads(raw_message)
                    if message.get("sequence_id") == sequence_id:
                        break

                if message.get("grid_coordinates") is None:
                    raise RuntimeError("self-test frame missing grid_coordinates")
                if message.get("spatial_ai_layer") is None:
                    raise RuntimeError("self-test frame missing spatial_ai_layer")

                passed += 1
                await asyncio.sleep(0.05)

            logger.info(
                "TELEMETRY SELF-TEST PASS frames=%d rate_hz=20 broker=%s topic=%s websocket=%s",
                passed,
                KAFKA_BROKER,
                TELEMETRY_TOPIC,
                websocket_url,
            )
    finally:
        await producer.stop()


async def main():
    server = TelemetrySpineServer()
    server_task = asyncio.create_task(server.run())

    try:
        if SELF_TEST_FRAMES > 0:
            await run_end_to_end_self_test(server, SELF_TEST_FRAMES)
        await server_task
    finally:
        if not server_task.done():
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
