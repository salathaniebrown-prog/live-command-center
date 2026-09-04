"""
EAGLE EYES TELEMETRY CORE — ISOLATED TELEMETRY SPINE
Kafka/Redpanda ingestion -> WGS84 voxel projection -> spatial analysis -> WebSocket broadcast.

This service is intentionally isolated from the existing Node command center.
Satellite configuration is retained as an optional adapter but is not invoked in the
telemetry hot path until a real provider contract is configured and validated.
"""

import asyncio
import json
import logging
import math
import os
import struct
from collections import deque

import aiohttp
import numpy as np
import websockets
from aiokafka import AIOKafkaConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("EagleEyesTelemetrySpine")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TELEMETRY_TOPIC = os.getenv("TELEMETRY_TOPIC", "eagle.eyes.field.telemetry")
WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
WEBSOCKET_PORT = int(os.getenv("PORT", os.getenv("WEBSOCKET_PORT", "8080")))
VOXEL_ORIGIN_LAT = float(os.getenv("VOXEL_ORIGIN_LAT", "35.6895"))
VOXEL_ORIGIN_LON = float(os.getenv("VOXEL_ORIGIN_LON", "139.6917"))
SATELLITE_BASE_URL = os.getenv("SATELLITE_BASE_URL", "").rstrip("/")
SATELLITE_API_KEY = os.getenv("SATELLITE_API_KEY", "")

FRAME_FORMAT = ">Qddff"
FRAME_SIZE = struct.calcsize(FRAME_FORMAT)


class SpatialAIEngine:
    """Statistical spatial trajectory and terrain-state analysis."""

    def __init__(self, window_size: int = 20):
        self.position_history = deque(maxlen=window_size)

    def process_frame(self, vx: int, vy: int, vz: int, moisture: float) -> dict:
        current_vector = np.array([vx, vy, vz], dtype=np.float64)
        self.position_history.append(current_vector)

        metrics = {
            "anomaly_detected": False,
            "predicted_next_voxel": {"x": vx, "y": vy, "z": vz},
            "terrain_classification": "Stable Matrix",
        }

        if moisture > 0.45:
            metrics["terrain_classification"] = "Saturated Matrix"
        elif moisture < 0.15:
            metrics["terrain_classification"] = "Arid / High Structural Risk"

        if len(self.position_history) < 5:
            return metrics

        history = np.asarray(self.position_history, dtype=np.float64)
        velocities = np.diff(history, axis=0)
        mean_velocity = np.mean(velocities[-3:], axis=0)
        predicted = current_vector + mean_velocity

        metrics["predicted_next_voxel"] = {
            "x": int(round(float(predicted[0]))),
            "y": int(round(float(predicted[1]))),
            "z": int(round(float(predicted[2]))),
        }

        last_velocity = velocities[-1]
        variance = np.var(velocities, axis=0)
        deviation = np.abs(last_velocity - mean_velocity)
        threshold = np.sqrt(variance) * 3.0 + 1.0

        if np.any(deviation > threshold):
            metrics["anomaly_detected"] = True
            metrics["terrain_classification"] = "Anomaly/Jitter Detected"

        return metrics


class TokyoGridTransformer:
    """Project WGS84 coordinates into a local 10 cm voxel grid."""

    def __init__(
        self,
        origin_lat: float = VOXEL_ORIGIN_LAT,
        origin_lon: float = VOXEL_ORIGIN_LON,
    ):
        self.origin_lat = math.radians(origin_lat)
        self.origin_lon = math.radians(origin_lon)
        self.earth_radius_m = 6378137.0
        self.voxel_resolution_m = 0.10

    def wgs84_to_local_meters(self, lat: float, lon: float, alt: float):
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        dlat = lat_rad - self.origin_lat
        dlon = lon_rad - self.origin_lon

        x = self.earth_radius_m * dlon * math.cos(self.origin_lat)
        y = self.earth_radius_m * dlat
        return x, y, alt

    def project_to_voxel_grid(self, lat: float, lon: float, alt: float):
        x, y, z = self.wgs84_to_local_meters(lat, lon, alt)
        return (
            int(round(x / self.voxel_resolution_m)),
            int(round(y / self.voxel_resolution_m)),
            int(round(z / self.voxel_resolution_m)),
        )


class CommercialSatelliteIngest:
    """Optional XYZ tile adapter; not used until a real provider is configured."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.zoom_level = 19

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def wgs84_to_xyz_tile(self, lat: float, lon: float, zoom: int):
        bounded_lat = max(-85.05112878, min(85.05112878, lat))
        lat_rad = math.radians(bounded_lat)
        n = 2.0**zoom
        xtile = int((lon + 180.0) / 360.0 * n)
        ytile = int(
            (
                1.0
                - math.log(
                    math.tan(lat_rad) + (1.0 / math.cos(lat_rad))
                )
                / math.pi
            )
            / 2.0
            * n
        )
        return xtile, ytile

    async def fetch_tile(self, lat: float, lon: float):
        if not self.configured:
            return None

        x, y = self.wgs84_to_xyz_tile(lat, lon, self.zoom_level)
        url = (
            f"{self.base_url}/{self.zoom_level}/{x}/{y}.png"
            f"?api_key={self.api_key}"
        )

        timeout = aiohttp.ClientTimeout(total=15)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.warning("Satellite provider returned HTTP %s", response.status)
        except Exception:
            logger.exception("Satellite provider connection failed")
        return None


class TelemetrySpineServer:
    def __init__(self):
        self.transformer = TokyoGridTransformer()
        self.ai_engine = SpatialAIEngine()
        self.satellite = CommercialSatelliteIngest(
            SATELLITE_BASE_URL,
            SATELLITE_API_KEY,
        )
        self.connected_clients = set()
        self.consumer = None

    async def register_client(self, websocket):
        self.connected_clients.add(websocket)
        logger.info(
            "WebSocket client connected; active=%d",
            len(self.connected_clients),
        )
        try:
            await websocket.wait_closed()
        finally:
            self.connected_clients.discard(websocket)
            logger.info(
                "WebSocket client disconnected; active=%d",
                len(self.connected_clients),
            )

    async def start_kafka_consumer(self):
        while True:
            consumer = AIOKafkaConsumer(
                TELEMETRY_TOPIC,
                bootstrap_servers=KAFKA_BROKER,
                group_id="eagle_eyes_spine_processor_v2",
                enable_auto_commit=True,
                auto_offset_reset="latest",
            )
            try:
                await consumer.start()
                self.consumer = consumer
                logger.info(
                    "Kafka consumer connected broker=%s topic=%s",
                    KAFKA_BROKER,
                    TELEMETRY_TOPIC,
                )
                return
            except Exception:
                logger.exception(
                    "Kafka startup failed; retrying in 3 seconds broker=%s",
                    KAFKA_BROKER,
                )
                try:
                    await consumer.stop()
                except Exception:
                    pass
                await asyncio.sleep(3)

    @staticmethod
    def decode_frame(payload: bytes):
        if len(payload) != FRAME_SIZE:
            raise ValueError(
                f"invalid telemetry frame size: got {len(payload)}, expected {FRAME_SIZE}"
            )

        seq_id, lat, lon, alt, moisture = struct.unpack(FRAME_FORMAT, payload)

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError("invalid latitude/longitude")
        if not all(math.isfinite(v) for v in (lat, lon, alt, moisture)):
            raise ValueError("non-finite telemetry value")

        return seq_id, lat, lon, alt, moisture

    async def broadcast(self, outbound_data: dict):
        if not self.connected_clients:
            return

        message = json.dumps(outbound_data, separators=(",", ":"))
        clients = list(self.connected_clients)
        results = await asyncio.gather(
            *(client.send(message) for client in clients),
            return_exceptions=True,
        )

        for client, result in zip(clients, results):
            if isinstance(result, Exception):
                self.connected_clients.discard(client)

    async def process_and_broadcast(self):
        async for msg in self.consumer:
            try:
                seq_id, lat, lon, alt, moisture = self.decode_frame(msg.value)
                vx, vy, vz = self.transformer.project_to_voxel_grid(lat, lon, alt)
                ai_analysis = self.ai_engine.process_frame(vx, vy, vz, moisture)

                outbound_data = {
                    "sequence_id": seq_id,
                    "timestamp": msg.timestamp,
                    "grid_coordinates": {"x": vx, "y": vy, "z": vz},
                    "raw_geodetic": {"lat": lat, "lon": lon, "alt": alt},
                    "soil_metrics": {"moisture_fraction": float(moisture)},
                    "spatial_ai_layer": ai_analysis,
                    "satellite_adapter_configured": self.satellite.configured,
                }
                await self.broadcast(outbound_data)
            except ValueError as exc:
                logger.warning("Dropped malformed telemetry frame: %s", exc)
            except Exception:
                logger.exception("Telemetry frame processing failed")

    async def run(self):
        websocket_server = websockets.serve(
            self.register_client,
            WEBSOCKET_HOST,
            WEBSOCKET_PORT,
            ping_interval=20,
            ping_timeout=20,
            max_size=1024 * 1024,
        )

        async with websocket_server:
            logger.info(
                "Telemetry WebSocket listening host=%s port=%d frame_size=%d",
                WEBSOCKET_HOST,
                WEBSOCKET_PORT,
                FRAME_SIZE,
            )
            await self.start_kafka_consumer()
            try:
                await self.process_and_broadcast()
            finally:
                if self.consumer is not None:
                    await self.consumer.stop()


if __name__ == "__main__":
    try:
        asyncio.run(TelemetrySpineServer().run())
    except KeyboardInterrupt:
        logger.info("Telemetry spine stopped")
