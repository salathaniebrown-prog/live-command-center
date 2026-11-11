import asyncio
import json
import websockets
from astra_telemetry import AstraTelemetryDashboard
from qasm_exporter import OpenQASMExporter

dashboard = AstraTelemetryDashboard(port=8081)

async def telemetry_broadcast():
    while True:
        await asyncio.sleep(2)
        if dashboard.active_connections:
            exporter = OpenQASMExporter(num_qubits=2, num_clbits=2)
            exporter.add_gate("h", 0)
            exporter.add_gate("cx", 0, 1)
            
            payload = {
                "event": "QASM_STREAM",
                "qasm_code": exporter.export(),
                "active_nodes": 10248
            }
            message = json.dumps(payload)
            await asyncio.gather(
                *[conn.send(message) for conn in dashboard.active_connections],
                return_exceptions=True
            )

async def main():
    async with websockets.serve(dashboard.handle_client, dashboard.host, dashboard.port):
        print(f"Telemetry & QASM WebSocket server running on ws://{dashboard.host}:{dashboard.port}")
        await telemetry_broadcast()

if __name__ == "__main__":
    asyncio.run(main())
