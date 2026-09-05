import json
import os
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
TOPIC = os.getenv("TELEMETRY_TOPIC", "planetary-simulation-stream")

OBSERVATION_AUTHORITY = {
    "authority": "observation",
    "commandEligible": False,
}
SAFE_OBSERVATION_ALLOWLIST = {
    "status",
    "metrics",
    "health",
    "world_data",
    "weather",
    "knowledge_search",
    "px4_telemetry",
}

FRAME_INGEST_COUNTER = Counter(
    "eagle_eyes_frames_ingested_total",
    "Total experimental telemetry frames accepted",
    ["data_class", "network_mode"],
)
PROCESSING_LATENCY_GAUGE = Gauge(
    "eagle_eyes_processing_latency_seconds",
    "Most recent ingest processing latency",
    ["data_class"],
)

producer: AIOKafkaProducer | None = None


def assert_observation_toolset(tools_registry: list[str]) -> bool:
    if not isinstance(tools_registry, list) or not tools_registry:
        raise ValueError("Registry must be a non-empty list")
    for tool in tools_registry:
        if tool not in SAFE_OBSERVATION_ALLOWLIST:
            raise PermissionError(f"Unauthorized observation tool: {tool}")
    return True


def _provenance(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def validate_and_mark_payload(payload: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("Payload must be an object")
    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        raise TypeError("Extra metadata must be an object")

    safe_extra = {
        key: value
        for key, value in extra.items()
        if key not in {"provenance", "authority", "commandEligible"}
    }

    return {
        **payload,
        **safe_extra,
        "provenance": {
            **_provenance(payload.get("provenance")),
            **_provenance(extra.get("provenance")),
        },
        **OBSERVATION_AUTHORITY,
    }


def validate_data_class(payload: dict[str, Any]) -> None:
    data_class = payload.get("dataClass")
    if data_class not in {"simulation", "observation"}:
        raise HTTPException(status_code=422, detail="dataClass must be simulation or observation")
    if data_class == "simulation" and payload.get("synthetic") is not True:
        raise HTTPException(status_code=422, detail="simulation payloads must set synthetic=true")
    if not _provenance(payload.get("provenance")).get("source"):
        raise HTTPException(status_code=422, detail="provenance.source is required")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global producer
    live_tools = [
        "status",
        "metrics",
        "health",
        "world_data",
        "weather",
        "knowledge_search",
        "px4_telemetry",
    ]
    assert_observation_toolset(live_tools)
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_SERVER)
    await producer.start()
    try:
        yield
    finally:
        if producer is not None:
            await producer.stop()
            producer = None


app = FastAPI(
    title="Eagle Eyes Experimental Observation Stack",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": producer is not None,
        "mode": "experimental",
        **OBSERVATION_AUTHORITY,
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/nasa/config")
async def nasa_config() -> dict[str, str]:
    target_date = (date.today() - timedelta(days=1)).isoformat()
    return {
        "dataClass": "observation",
        "source": "NASA GIBS",
        "date": target_date,
        "tile_url": (
            "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
            "MODIS_Terra_CorrectedReflectance_TrueColor/default/"
            f"{target_date}/GoogleMapsCompatible_Level9/{{z}}/{{y}}/{{x}}.jpg"
        ),
    }


@app.post("/api/v1/telemetry/ingest")
async def ingest(payload: dict[str, Any]) -> dict[str, Any]:
    global producer
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer is not ready")

    validate_data_class(payload)
    started = time.perf_counter()
    secured_payload = validate_and_mark_payload(payload)
    await producer.send_and_wait(TOPIC, json.dumps(secured_payload).encode("utf-8"))

    data_class = str(secured_payload.get("dataClass", "unknown"))
    network_mode = str(secured_payload.get("network_mode", "unspecified"))[:64]
    FRAME_INGEST_COUNTER.labels(data_class=data_class, network_mode=network_mode).inc()
    PROCESSING_LATENCY_GAUGE.labels(data_class=data_class).set(time.perf_counter() - started)

    return {
        "status": "accepted",
        "topic": TOPIC,
        "dataClass": data_class,
        **OBSERVATION_AUTHORITY,
    }


@app.websocket("/ws/stream")
async def stream(websocket: WebSocket) -> None:
    await websocket.accept()
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_SERVER,
        auto_offset_reset="latest",
        enable_auto_commit=False,
        group_id=None,
    )
    await consumer.start()
    try:
        async for message in consumer:
            await websocket.send_text(message.value.decode("utf-8"))
    except WebSocketDisconnect:
        pass
    finally:
        await consumer.stop()
