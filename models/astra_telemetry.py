import asyncio
import json

class AstraTelemetryDashboard:
    def __init__(self, host="127.0.0.1", port=8081):
        self.host = host
        self.port = port
        self.active_connections = set()

    async def register(self, websocket):
        self.active_connections.add(websocket)

    async def unregister(self, websocket):
        self.active_connections.remove(websocket)

    async def handle_client(self, websocket, path=None):
        await self.register(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                response = {"status": "received", "echo": data.get("command")}
                await websocket.send(json.dumps(response))
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            await self.unregister(websocket)
