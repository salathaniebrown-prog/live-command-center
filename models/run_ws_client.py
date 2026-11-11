import asyncio
import json
import websockets

async def test_client():
    uri = "ws://127.0.0.1:8081"
    async with websockets.connect(uri) as websocket:
        payload = {"command": "get_telemetry_status"}
        await websocket.send(json.dumps(payload))
        response = await websocket.recv()
        print(f"Received from server: {response}")

if __name__ == "__main__":
    asyncio.run(test_client())
