import asyncio
import json
import websockets

async def listen_stream():
    uri = "ws://127.0.0.1:8081"
    print(f"Connecting to live QASM stream at {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Listening for live QASM exports and telemetry pulses...")
            async for message in websocket:
                data = json.loads(message)
                print("\n--- Received Event ---")
                print(f"Event Type: {data.get('event')}")
                print(f"Active Nodes: {data.get('active_nodes')}")
                if "qasm_code" in data:
                    print("--- OpenQASM 3.0 Code ---")
                    print(data["qasm_code"])
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(listen_stream())
