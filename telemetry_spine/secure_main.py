import asyncio
import json
import logging
import os

from aiohttp import web

import main as base
from signed_ingest import (
    ALLOWED_SOURCE_MODES,
    ReplayDetectedError,
    SignatureError,
    SignedTelemetryError,
    SignedTelemetryLedger,
    build_live_observation_packet,
    validate_payload,
    verify_signature,
)

logger = logging.getLogger("EagleEyesSecureTelemetryRuntime")
SIGNED_TELEMETRY_HMAC_SECRET = os.getenv(
    "SIGNED_TELEMETRY_HMAC_SECRET", ""
).strip()
SIGNED_TELEMETRY_DB_PATH = os.getenv(
    "SIGNED_TELEMETRY_DB_PATH", "eagle_eyes_signed_telemetry.db"
).strip()
SIGNED_TELEMETRY_MAX_CLOCK_SKEW_S = int(
    os.getenv("SIGNED_TELEMETRY_MAX_CLOCK_SKEW_S", "60")
)
SIGNED_TELEMETRY_MAX_BODY_BYTES = 64 * 1024


class SecureTelemetryRuntime(base.AiohttpTelemetryRuntime):
    def __init__(self):
        super().__init__()
        self.signed_secret = (
            SIGNED_TELEMETRY_HMAC_SECRET.encode("utf-8")
            if SIGNED_TELEMETRY_HMAC_SECRET
            else b""
        )
        self.signed_ledger = (
            SignedTelemetryLedger(SIGNED_TELEMETRY_DB_PATH)
            if self.signed_secret
            else None
        )

    async def health(self, request):
        response = await super().health(request)
        payload = json.loads(response.text)
        payload.update(
            {
                "signed_ingest_configured": bool(
                    self.signed_secret and self.signed_ledger
                ),
                "signed_ingest_schema": "eagle-eyes.signed-telemetry.v1",
                "signed_ingest_modes": sorted(ALLOWED_SOURCE_MODES),
                "signed_live_publish_rule": (
                    "sourceMode=LIVE and simulated=false only"
                ),
                "signed_replay_protection": "sourceId+nonce unique ledger key",
                "signed_ledger_wal": bool(self.signed_ledger),
            }
        )
        if self.signed_ledger is not None:
            try:
                payload["signed_ledger_records"] = await asyncio.to_thread(
                    self.signed_ledger.stats
                )
            except Exception:
                logger.exception("Signed ledger health stats failed")
                payload["signed_ledger_records"] = "UNAVAILABLE"
        return web.json_response(payload)

    async def ingest_signed(self, request):
        if not self.signed_secret or self.signed_ledger is None:
            return web.json_response(
                {
                    "ok": False,
                    "accepted": False,
                    "error": "Signed telemetry ingest is not configured",
                },
                status=503,
            )

        try:
            raw_body = await request.read()
            if len(raw_body) > SIGNED_TELEMETRY_MAX_BODY_BYTES:
                return web.json_response(
                    {
                        "ok": False,
                        "accepted": False,
                        "error": "Signed telemetry payload exceeds 64 KiB",
                    },
                    status=413,
                )

            signature_header = request.headers.get(
                "X-Eagle-Eyes-Signature"
            )
            timestamp_header = request.headers.get(
                "X-Eagle-Eyes-Timestamp"
            )
            payload_sha256 = verify_signature(
                self.signed_secret,
                raw_body,
                signature_header,
                timestamp_header,
                max_clock_skew_s=SIGNED_TELEMETRY_MAX_CLOCK_SKEW_S,
            )

            payload = validate_payload(json.loads(raw_body))
            signature = (signature_header or "").strip().lower()
            if signature.startswith("sha256="):
                signature = signature[7:]

            receipt = await asyncio.to_thread(
                self.signed_ledger.append,
                payload,
                payload_sha256=payload_sha256,
                signature=signature,
            )

            publish_live = (
                payload["sourceMode"] == "LIVE"
                and payload["simulated"] is False
            )
            if publish_live:
                outbound = build_live_observation_packet(payload, receipt)
                position = payload["position"]
                lat = position["latitude"]
                lon = position["longitude"]
                alt = position.get("altitudeM")
                vx, vy, vz = self.server.transformer.project_to_voxel_grid(
                    lat,
                    lon,
                    alt if alt is not None else 0.0,
                )
                outbound["raw_geodetic"] = {
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                }
                outbound["grid_coordinates"] = {
                    "x": vx,
                    "y": vy,
                    "z": vz if alt is not None else None,
                }
                outbound["spatial_ai_layer"] = {
                    "anomaly_detected": False,
                    "predicted_next_voxel": outbound["grid_coordinates"],
                    "terrain_classification": "Signed Live Observation",
                    "analysis_mode": "verified-signed-observation",
                }
                await self.broadcast(outbound)

            logger.info(
                "Signed telemetry accepted source=%s target=%s mode=%s ledger_id=%d published_live=%s",
                payload["sourceId"],
                payload["target"],
                payload["sourceMode"],
                receipt.ledger_id,
                publish_live,
            )
            return web.json_response(
                {
                    "ok": True,
                    "accepted": True,
                    "schemaVersion": payload["schemaVersion"],
                    "sourceMode": payload["sourceMode"],
                    "simulated": payload["simulated"],
                    "publishedLive": publish_live,
                    "ledgerId": receipt.ledger_id,
                    "payloadSha256": receipt.payload_sha256,
                    "authority": {
                        "type": "observation",
                        "commandEligible": False,
                    },
                },
                status=202,
            )
        except ReplayDetectedError as exc:
            logger.warning("Rejected replayed signed telemetry: %s", exc)
            return web.json_response(
                {
                    "ok": False,
                    "accepted": False,
                    "error": "Signed telemetry replay rejected",
                },
                status=409,
            )
        except SignatureError as exc:
            logger.warning("Rejected signed telemetry authentication: %s", exc)
            return web.json_response(
                {
                    "ok": False,
                    "accepted": False,
                    "error": "Signed telemetry authentication failed",
                },
                status=401,
            )
        except (json.JSONDecodeError, UnicodeDecodeError, SignedTelemetryError) as exc:
            return web.json_response(
                {
                    "ok": False,
                    "accepted": False,
                    "error": str(exc),
                },
                status=400,
            )
        except Exception:
            logger.exception("Signed telemetry ingest failed")
            return web.json_response(
                {
                    "ok": False,
                    "accepted": False,
                    "error": "Signed telemetry ingest unavailable",
                },
                status=503,
            )

    async def start_http(self):
        app = web.Application(client_max_size=256 * 1024)
        app.router.add_get("/", self.dashboard)
        app.router.add_get("/index.html", self.dashboard)
        app.router.add_get("/health", self.health)
        app.router.add_get("/ws", self.websocket_handler)
        app.router.add_post("/ingest/px4", self.ingest_px4)
        app.router.add_post("/ingest/signed", self.ingest_signed)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(
            self.runner,
            base.WEBSOCKET_HOST,
            base.WEBSOCKET_PORT,
        )
        await site.start()
        logger.info(
            "Secure telemetry HTTP/WebSocket listening host=%s port=%d signed_ingest=%s",
            base.WEBSOCKET_HOST,
            base.WEBSOCKET_PORT,
            bool(self.signed_secret),
        )


async def main():
    runtime = SecureTelemetryRuntime()
    logger.info(
        "Secure telemetry entrypoint started self_test_frames=%d signed_ingest=%s",
        base.SELF_TEST_FRAMES,
        bool(runtime.signed_secret),
    )

    await runtime.start_http()
    await runtime.server.start_kafka_consumer()
    await runtime.start_px4_kafka()

    binary_task = asyncio.create_task(runtime.server.process_and_broadcast())
    px4_task = asyncio.create_task(runtime.process_px4())

    try:
        if base.SELF_TEST_FRAMES > 0:
            await base.run_end_to_end_self_test(
                runtime,
                base.SELF_TEST_FRAMES,
            )
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
