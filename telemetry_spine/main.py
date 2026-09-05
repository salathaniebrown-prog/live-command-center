import asyncio
import json
import logging
import os
import struct
import time

from aiohttp import web
import websockets
from aiokafka import AIOKafkaProducer

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
    <div class="card"><div class="label">Moisture</div><div id="moisture" class="value">—</div></div>
    <div class="card"><div class="label">Spatial AI</div><div id="ai" class="value">WAITING</div></div>
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
    document.getElementById('moisture').textContent=Number.isFinite(m)?`${(m*100).toFixed(2)}%`:'—';
    document.getElementById('ai').textContent=t.spatial_ai_layer?.terrain_classification ?? '—';
    const g=t.raw_geodetic||{},v=t.grid_coordinates||{};
    document.getElementById('geo').textContent=Number.isFinite(g.lat)?`${g.lat.toFixed(6)}, ${g.lon.toFixed(6)} • ${Number(g.alt).toFixed(1)} m`:'—';
    document.getElementById('grid').textContent=(v.x!==undefined)?`X ${v.x} • Y ${v.y} • Z ${v.z}`:'—';
    if(v.x!==undefined){target.hidden=false;target.style.left=`${50+Math.max(-45,Math.min(45,v.x/50))}%`;target.style.top=`${50+Math.max(-45,Math.min(45,-v.y/50))}%`;}
    log.textContent=`Last frame ${new Date().toLocaleTimeString()}\n${JSON.stringify(t,null,2)}`;
  };
}
connect();
</script>
</body></html>"""


class AiohttpTelemetryRuntime:
    def __init__(self):
        self.server = TelemetrySpineServer()
        self.clients: set[web.WebSocketResponse] = set()
        self.server.broadcast = self.broadcast
        self.runner = None

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
        return web.json_response({
            "ok": True,
            "service": "eagle-eyes-telemetry-v2",
            "kafka_connected": self.server.consumer is not None,
            "assigned_partitions": assignment,
            "topic": TELEMETRY_TOPIC,
            "frame_size": FRAME_SIZE,
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

    async def start_http(self):
        app = web.Application()
        app.router.add_get("/", self.dashboard)
        app.router.add_get("/index.html", self.dashboard)
        app.router.add_get("/health", self.health)
        app.router.add_get("/ws", self.websocket_handler)

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
    consumer_task = asyncio.create_task(runtime.server.process_and_broadcast())

    try:
        if SELF_TEST_FRAMES > 0:
            await run_end_to_end_self_test(runtime, SELF_TEST_FRAMES)
        await consumer_task
    finally:
        if not consumer_task.done():
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
        await runtime.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
