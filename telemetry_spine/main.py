import asyncio

from eagle_eyes_telemetry_spine import TelemetrySpineServer


if __name__ == "__main__":
    try:
        asyncio.run(TelemetrySpineServer().run())
    except KeyboardInterrupt:
        pass
