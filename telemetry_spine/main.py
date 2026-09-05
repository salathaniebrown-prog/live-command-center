import asyncio
import hmac
import json
import logging
import math
import os
import struct
import time

from aiohttp import web
import websockets
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from eagle_eyes_telemetry_spine import (
    FRAME_FORMAT,
    FRAME_SIZE,
    KAFKA_BROKER,
    TELEMETRY_TOPIC,
    WEBSOCKET_HOST,
    WEBSOCKET_PORT,
    TelemetrySpineServer,
)

logger = logging.getLogger("EagleEyesTelemetryEntrypoint")
SELF_TEST_FRAMES = int(os.getenv("TELEMETRY_SELF_TEST_FRAMES", "0"))
PX4_TELEMETRY_TOPIC = os.getenv(
    "PX4_TELEMETRY_TOPIC",
    "eagle.eyes.px4.telemetry",
)
TELEMETRY_RELAY_TOKEN = os.getenv("TELEMETRY_RELAY_TOKEN", "").strip()
PX4_SCHEMA_VERSION = "eagle-eyes.px4-telemetry.v1"

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#070706">
<title>Eagle Eyes • Live Telemetry</title>
<style>
:root{color-scheme:dark;--bg:#070706;--panel:#11100d;--line:#4b3a20;--gold:#f2c66d;--text:#f7f1e7;--muted:#9f9789;--green:#73e58c;--red:#ff6f71}
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:Inter,system-ui,sans-serif;color:var(--text);background:radial-gradient(circle at 50% -10%,#3a2a0f55,transparent 32rem),linear-gradient(#0c0b09,#050505)}
main{width:min(1100px,calc(100% - 24px));margin:0 auto;padding:24px 0 40px}
.top{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:18px}.eyebrow{color:var(--gold);font-size:10px;letter-spacing:.2em;text-transform:uppercase}
h1{font-size:clamp(24px,5vw,48px);margin:7px 0}.sub{color:var(--muted);font-size:12px}
.badge{display:flex;align-items:center;gap:8px;border:1px solid var(--line);padding:9px 12px;border-radius:999px;font-size:11px;color:var(--muted)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--red);box-shadow:0 0 14px currentColor}.dot.ok{background:var(--green);color:var(--green)}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}.card{grid-column:span 3;background:linear-gradient(180deg,#15130f,#0b0a08);border:1px solid var(--line);border-radius:16px;padding:16px;min-height:112px}
.card.wide{grid-column:span 6}.label{color:var(--muted);font-size:9px;letter-spacing:.14em;text-transform:uppercase}.value{font-size:clamp(18px,3vw,30px);margin-top:10px;font-variant-numeric:tabular-nums}
.stage{margin-top:12px;min-height:280px;border:1px solid var(--line);border-radius:18px;position:relative;overflow:hidden;background:radial-gradient(circle,#f2c66d18 0 2px,transparent 3px),repeating-radial-gradient(circle,transparent 0 39px,#f2c66d12 40px 41px),linear-gradient(#0a0907,#060605)}
.cross{position:absolute;left:50%;top:50%;width:12px;height:12px;border:1px solid var(--gold);border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 25px #f2c66d99}
.target{position:absolute;width:12px;height:12px;background:var(--green);border-radius:50%;box-shadow:0 0 22px var(--green);transform:translate(-50%,-50%);transition:left .12s linear,top .12s linear}
.log{margin-top:12px;border:1px solid var(--line);border-radius:16px;background:#080807;padding:14px;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#cfc6b8;min-height:76px;white-space:pre-wrap}
@media(max-width:760px){.card,.card.wide{grid-column:span 6}.top{align-items:flex-start;flex-direction:column}}@media(max-width:480px){.card,.card.wide{grid-column:1/-1}}
</style>
</head>
<body>
<main>
  <div class="top">
    <div><div class="eyebrow">Eagle Eyes • Telemetry Spine V2</div><h1>Live Digital Twin Feed</h1><div class="sub">Redpanda → spatial processor → secure WebSocket → this interface</div></div>
    <div class="badge"><span id="dot" class="dot"></span><span id="state">CONNECTING</span></div>
  </div>
  <section class="grid">
    <div class="card"><div class="label">Packet sequence</div><div id="seq" class="value">—</div></div>
    <div class="card"><div class="label">Frames received</div><div id="frames" class="value">0</div></div>
    <div class="card"><div class="label">Source / moisture</div><div id="source" class="value">—</div></div>
    <div class="card"><div class="label">Spatial analysis</div><div id="ai" class="value">WAITING</div></div>
    <div class="card wide"><div class="label">WGS84 position</div><div id="geo" class="value">—</div></div>
    <div class="card wide"><div class="label">10 cm voxel position</div><div id="grid" class="value">—</div></div>
  </section>
  <div class="stage"><div class="cross"></div><div id="target" class="target" hidden></div></div>
  <div id="log" class="log">Waiting for telemetry frames…</div>
</main>
<script>
const dot=document.getElementById('dot'),state=document.getElementById('state'),target=document.getElementById('target'),log=document.getElementById('log');
let frames=0,retry=0;
function connect(){
  const proto=location.protocol==='https:'?'wss:':'ws:';
  const ws=new WebSocket(`${proto}//${location.host}/ws`);
  ws.onopen=()=>{dot.classList.add('ok');state.textContent='LIVE';retry=0;};
  ws.onclose=()=>{dot.classList.remove('ok');state.textContent='RECONNECTING';setTimeout(connect,Math.min(10000,1000*2**retry++));};
  ws.onerror=()=>ws.close();
  ws.onmessage=e=>{
    const t=JSON.parse(e.data);frames++;
    document.getElementById('frames').textContent=frames.toLocaleString();
    document.getElementById('seq').textContent=t.sequence_id ?? '—';
    const m=t.soil_metrics?.moisture_fraction;
    const source=t.source_type==='px4'?`PX4${t.vehicle_id?` • ${t.vehicle_id}`:''}`:(Number.isFinite(m)?`FIELD • ${(m*100).toFixed(2)}%`:'FIELD');
    document.getElementById('source').textContent=source;
    document.getElementById('ai').textContent=t.spatial_ai_layer?.terrain_classification ?? '—';
    const g=t.raw_geodetic||{},v=t.grid_coordinates||{};
    const alt=Number.isFinite(g.alt)?`${Number(g.alt).toFixed(1)} m`:'alt N/A';
    document.getElementById('geo').textContent=Number.isFinite(g.lat)?`${g.lat.toFixed(6)}, ${g.lon.toFixed(6)} • ${alt}`:'—';
    const z=Number.isFinite(v.z)?v.z:'N/A';
    document.getElementById('grid').textContent=Number.isFinite(v.x)?`X ${v.x} • Y ${v.y} • Z ${z}`:'—';
    if(Number.isFinite(v.x)&&Number.isFinite(v.y)){target.hidden=false;target.style.left=`${50+Math.max(-45,Math.min(45,v.x/50))}%`;target.style.top=`${50+Math.max(-45,Math.min(45,-v.y/50))}%`;}else{target.hidden=true;}
    log.textContent=`Last frame ${new Date().toLocaleTimeString()}\n${JSON.stringify(t,null,2)}`;
  };
}
connect();
</script>
</body></html>"""


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_px4_snapshot(payload):
    if not isinstance(payload, dict):
        raise ValueError("PX4 relay payload must be a JSON object")

    if payload.get("schemaVersion") != PX4_SCHEMA_VERSION:
        raise ValueError(f"schemaVersion must be {PX4_SCHEMA_VERSION}")

    if payload.get("simulated") is not False:
        raise ValueError("PX4 relay accepts validated non-simulated telemetry only")

    vehicle_id = payload.get("vehicleId")
    if not isinstance(vehicle_id, str) or not vehicle_id.strip() or len(vehicle_id.strip()) > 64:
        raise ValueError("vehicleId is required and must be at most 64 characters")

    position = payload.get("position")
    if position is not None:
        if not isinstance(position, dict):
            raise ValueError("position must be an object")
        lat = position.get("latitude")
        lon = position.get("longitude")
        if not _finite_number(lat) or not -90 <= lat <= 90:
            raise ValueError("position.latitude must be a valid latitude")
        if not _finite_number(lon) or not -180 <= lon <= 180:
            raise ValueError("position.longitude must be a valid longitude")
        altitude = position.get("altitudeM")
        if altitude is not None and not _finite_number(altitude):
            raise ValueError("position.altitudeM must be finite when supplied")

    return payload


class AiohttpTelemetryRuntime:
    def __init__(self):
        self.server = TelemetrySpineServer()
        self.clients: set[web.WebSocketResponse] = set()
        self.server.broadcast = self.broadcast
        self.runner = None
        self.px4_producer = None
        self.px4_consumer = None

    async def broadcast(self, outbound_data: dict):
        if not self.clients:
            return

        message = json.dumps(outbound_data, separators=(",", ":"))
        dead = []
        for client in list(self.clients):
            try:
                await client.send_str(message)
            except Exception:
                dead.append(client)

        for client in dead:
            self.clients.discard(client)

    async def dashboard(self, request):
        return web.Response(
            text=DASHBOARD_HTML,
            content_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def health(self, request):
        assignment = []
        if self.server.consumer is not None:
            assignment = [str(item) for item in self.server.consumer.assignment()]
        px4_assignment = []
        if self.px4_consumer is not None:
            px4_assignment = [str(item) for item in self.px4_consumer.assignment()]
        return web.json_response({
            "ok": True,
            "service": "eagle-eyes-telemetry-v2",
            "kafka_connected": self.server.consumer is not None,
            "assigned_partitions": assignment,
            "topic": TELEMETRY_TOPIC,
            "frame_size": FRAME_SIZE,
            "px4_relay_configured": bool(TELEMETRY_RELAY_TOKEN),
            "px4_kafka_connected": self.px4_consumer is not None,
            "px4_assigned_partitions": px4_assignment,
            "px4_topic": PX4_TELEMETRY_TOPIC,
            "websocket_clients": len(self.clients),
        })

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        self.clients.add(ws)
        logger.info("Public telemetry WebSocket connected active=%d", len(self.clients))
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.ERROR:
                    logger.warning("Public telemetry WebSocket error=%s", ws.exception())
                    break
        finally:
            self.clients.discard(ws)
            logger.info("Public telemetry WebSocket disconnected active=%d", len(self.clients))
        return ws

    async def ingest_px4(self, request):
        if not TELEMETRY_RELAY_TOKEN:
            return web.json_response(
                {"ok": False, "accepted": False, "error": "PX4 relay is not configured"},
                status=503,
            )

        authorization = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            return web.json_response(
                {"ok": False, "accepted": False, "error": "Unauthorized"},
                status=401,
            )

        received_token = authorization[len(prefix):].strip()
        if not received_token or not hmac.compare_digest(received_token, TELEMETRY_RELAY_TOKEN):
            return web.json_response(
                {"ok": False, "accepted": False, "error": "Unauthorized"},
                status=401,
            )

        if self.px4_producer is None:
            return web.json_response(
                {"ok": False, "accepted": False, "error": "PX4 Kafka producer is not ready"},
                status=503,
            )

        try:
            payload = validate_px4_snapshot(await request.json())
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            metadata = await self.px4_producer.send_and_wait(PX4_TELEMETRY_TOPIC, encoded)
            logger.info(
                "PX4 relay accepted vehicle=%s topic=%s partition=%s offset=%s",
                payload["vehicleId"],
                PX4_TELEMETRY_TOPIC,
                metadata.partition,
                metadata.offset,
            )
            return web.json_response(
                {
                    "ok": True,
                    "accepted": True,
                    "simulated": False,
                    "schemaVersion": PX4_SCHEMA_VERSION,
                    "vehicleId": payload["vehicleId"],
                    "topic": PX4_TELEMETRY_TOPIC,
                    "partition": metadata.partition,
                    "offset": metadata.offset,
                },
                status=202,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return web.json_response(
                {"ok": False, "accepted": False, "error": str(exc)},
                status=400,
            )
        except Exception as exc:
            logger.exception("PX4 relay publish failed")
            return web.json_response(
                {"ok": False, "accepted": False, "error": "PX4 relay publish failed"},
                status=503,
            )

    async def start_px4_kafka(self):
        self.px4_producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
        self.px4_consumer = AIOKafkaConsumer(
            PX4_TELEMETRY_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            group_id="eagle_eyes_px4_spine_v1",
            enable_auto_commit=True,
            auto_offset_reset="latest",
        )
        await self.px4_producer.start()
        await self.px4_consumer.start()
        logger.info(
            "PX4 Kafka relay connected broker=%s topic=%s",
            KAFKA_BROKER,
            PX4_TELEMETRY_TOPIC,
        )

    async def process_px4(self):
        async for msg in self.px4_consumer:
            try:
                payload = validate_px4_snapshot(json.loads(msg.value.decode("utf-8")))
                position = payload.get("position") or {}
                lat = position.get("latitude")
                lon = position.get("longitude")
                alt = position.get("altitudeM")

                raw_geodetic = None
                grid_coordinates = None
                if _finite_number(lat) and _finite_number(lon):
                    raw_geodetic = {
                        "lat": float(lat),
                        "lon": float(lon),
                        "alt": float(alt) if _finite_number(alt) else None,
                    }
                    vx, vy, vz = self.server.transformer.project_to_voxel_grid(
                        float(lat),
                        float(lon),
                        float(alt) if _finite_number(alt) else 0.0,
                    )
                    grid_coordinates = {
                        "x": vx,
                        "y": vy,
                        "z": vz if _finite_number(alt) else None,
                    }

                flight_mode = payload.get("flightMode") or "N/A"
                analysis = {
                    "anomaly_detected": False,
                    "predicted_next_voxel": grid_coordinates,
                    "terrain_classification": (
                        "PX4 Position Track" if grid_coordinates else "PX4 Telemetry — Position Waiting"
                    ),
                    "analysis_mode": "validated-px4-observation",
                }

                outbound = {
                    "source_type": "px4",
                    "sequence_id": msg.offset,
                    "sequence_namespace": f"{PX4_TELEMETRY_TOPIC}:{msg.partition}",
                    "timestamp": msg.timestamp,
                    "vehicle_id": payload["vehicleId"],
                    "grid_coordinates": grid_coordinates,
                    "raw_geodetic": raw_geodetic,
                    "spatial_ai_layer": analysis,
                    "px4_telemetry": {
                        "schemaVersion": payload.get("schemaVersion"),
                        "simulated": False,
                        "flightMode": flight_mode,
                        "armed": payload.get("armed"),
                        "landed": payload.get("landed"),
                        "gps": payload.get("gps"),
                        "attitude": payload.get("attitude"),
                        "velocity": payload.get("velocity"),
                        "battery": payload.get("battery"),
                        "link": payload.get("link"),
                        "sourceObservedAt": payload.get("sourceObservedAt"),
                        "receivedAt": payload.get("receivedAt"),
                    },
                    "satellite_adapter_configured": self.server.satellite.configured,
                }
                await self.broadcast(outbound)
            except ValueError as exc:
                logger.warning("Dropped invalid PX4 relay snapshot: %s", exc)
            except Exception:
                logger.exception("PX4 relay processing failed")

    async def start_http(self):
        app = web.Application(client_max_size=256 * 1024)
        app.router.add_get("/", self.dashboard)
        app.router.add_get("/index.html", self.dashboard)
        app.router.add_get("/health", self.health)
        app.router.add_get("/ws", self.websocket_handler)
        app.router.add_post("/ingest/px4", self.ingest_px4)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, WEBSOCKET_HOST, WEBSOCKET_PORT)
        await site.start()
        logger.info(
            "Telemetry public HTTP/WebSocket listening host=%s port=%d",
            WEBSOCKET_HOST,
            WEBSOCKET_PORT,
        )

    async def stop(self):
        if self.server.consumer is not None:
            await self.server.consumer.stop()
        if self.px4_consumer is not None:
            await self.px4_consumer.stop()
        if self.px4_producer is not None:
            await self.px4_producer.stop()
        if self.runner is not None:
            await self.runner.cleanup()


async def wait_for_partition(runtime: AiohttpTelemetryRuntime, timeout_s: float = 45.0):
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        consumer = runtime.server.consumer
        if consumer is not None and consumer.assignment():
            logger.info(
                "Telemetry consumer owns partitions=%s",
                [str(item) for item in consumer.assignment()],
            )
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("telemetry consumer did not receive a Kafka partition")
        await asyncio.sleep(0.25)


async def run_end_to_end_self_test(runtime: AiohttpTelemetryRuntime, frame_count: int):
    logger.info(
        "TELEMETRY SELF-TEST START frames=%d broker=%s topic=%s",
        frame_count,
        KAFKA_BROKER,
        TELEMETRY_TOPIC,
    )
    await wait_for_partition(runtime)

    websocket_url = f"ws://127.0.0.1:{WEBSOCKET_PORT}/ws"
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
    runtime = AiohttpTelemetryRuntime()
    logger.info("Telemetry entrypoint started self_test_frames=%d", SELF_TEST_FRAMES)

    await runtime.start_http()
    await runtime.server.start_kafka_consumer()
    await runtime.start_px4_kafka()

    binary_task = asyncio.create_task(runtime.server.process_and_broadcast())
    px4_task = asyncio.create_task(runtime.process_px4())

    try:
        if SELF_TEST_FRAMES > 0:
            await run_end_to_end_self_test(runtime, SELF_TEST_FRAMES)
        await asyncio.gather(binary_task, px4_task)
    finally:
        for task in (binary_task, px4_task):
            if not task.done():
                task.cancel()
        for task in (binary_task, px4_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        await runtime.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
