import os
import time
import sqlite3
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

DB_PATH = "/tmp/astra_deepspace_ledger.db"
TELEMETRY_LOG = "/tmp/telemetry_clean.log"

class TelemetryPacket(BaseModel):
    event_type: str
    payload: str
    quantum_fidelity: float = 0.99485

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try: await connection.send_text(message)
            except Exception: pass

manager = ConnectionManager()

async def automated_log_cleanup_loop():
    while True:
        try:
            if os.path.exists(TELEMETRY_LOG):
                statinfo = os.stat(TELEMETRY_LOG)
                if statinfo.st_size > 5 * 1024 * 1024:
                    with open(TELEMETRY_LOG, 'r') as f:
                        lines = f.readlines()
                    with open(TELEMETRY_LOG, 'w') as f:
                        f.writelines(lines[-1000:])
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("INSERT INTO master_events (event_type, payload, quantum_fidelity, timestamp) VALUES (?, ?, ?, ?)",
                              ("LOG_ROTATION_EVENT", "Telemetry file exceeded 5MB. Executed rotation.", 1.0, time.time()))
                    conn.commit()
                    conn.close()
        except Exception as e:
            print(f"[!] Log cleanup error: {e}")
        await asyncio.sleep(60)

# Modern lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(automated_log_cleanup_loop())
    print("[*] Telemetry automated log rotation loop successfully dispatched via Lifespan.")
    yield
    cleanup_task.cancel()

app = FastAPI(title="Sovereign Log Bridge Node", lifespan=lifespan)

@app.post("/api/hardware")
async def ingest_telemetry_packet(packet: TelemetryPacket, authorization: Optional[str] = Header(None)):
    timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    log_entry = f"[{timestamp_str}] {packet.event_type} | Fidelity: {packet.quantum_fidelity} | {packet.payload}\n"
    with open(TELEMETRY_LOG, "a") as log_file:
        log_file.write(log_entry)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO master_events (event_type, payload, quantum_fidelity, timestamp) VALUES (?, ?, ?, ?)",
                  (packet.event_type, packet.payload, packet.quantum_fidelity, time.time()))
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database write failure: {e}")
    await manager.broadcast(log_entry.strip())
    return {"status": "SUCCESS", "message": "Telemetry packet bridged to data layers."}

@app.websocket("/ws/telemetry")
async def telemetry_websocket_route(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        if os.path.exists(TELEMETRY_LOG):
            with open(TELEMETRY_LOG, 'r') as f:
                history = f.readlines()[-15:]
                for entry in history:
                    await websocket.send_text(entry.strip())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sovereign Monitor UI</title>
        <style>
            body { background: #000; color: #00ffcc; font-family: monospace; padding: 20px; }
            h2 { border-bottom: 2px solid #00ffcc; padding-bottom: 10px; color: #fff; }
            #console { background: #050505; border: 1px solid #333; padding: 15px; height: 400px; overflow-y: auto; box-shadow: 0 0 10px #00ffcc; }
            .entry { padding: 4px 0; border-bottom: 1px solid #111; font-size: 13px; }
        </style>
    </head>
    <body>
        <h2>NEXUS-BROWN HIGH-FIDELITY TELEMETRY RADIAL STREAM</h2>
        <div id="console"></div>
        <script>
            const ws = new WebSocket(`ws://${window.location.host}/ws/telemetry`);
            const consoleDiv = document.getElementById('console');
            ws.onmessage = function(event) {
                const item = document.createElement('div');
                item.className = 'entry';
                item.innerText = event.data;
                consoleDiv.appendChild(item);
                consoleDiv.scrollTop = consoleDiv.scrollHeight;
            };
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3001)
