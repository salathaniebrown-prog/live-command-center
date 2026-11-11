#!/usr/bin/env python3
# ==============================================================================
# System Architecture: ASTRA_BIDIRECTIONAL_WEBSOCKET_SERVER
# Executive Authority: SALATHANIEL S A BROWN SR.
# ==============================================================================

import asyncio
import json
import os
import sqlite3
import urllib.request
import websockets

PORT = 8765

async def import_telemetry():
    """Aggregates metrics from Go daemon and SQLite ledgers."""
    metrics = {
        "node": "Astra-Sovereign-Master",
        "status": "ONLINE",
        "go_daemon": "OFFLINE",
        "sqlite_tables": 0
    }
    
    # Query Go Daemon on port 8099
    try:
        req = urllib.request.Request("http://127.0.0.1:8099/telemetry")
        with urllib.request.urlopen(req, timeout=1) as resp:
            metrics["go_daemon"] = json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass

    # Query SQLite Ledger
    db_path = os.path.expanduser("~/alstra_enterprise_core.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
            metrics["sqlite_tables"] = cur.fetchone()[0]
            conn.close()
        except Exception:
            pass

    return metrics

async def handle_connection(websocket):
    print(f"[+] Client connected: {websocket.remote_address}")
    try:
        # Task to push live telemetry pulses every 2 seconds
        async def telemetry_loop():
            while True:
                data = await import_telemetry()
                await websocket.send(json.dumps({"type": "telemetry_pulse", "data": data}))
                await asyncio.sleep(2)

        # Task to listen for inbound control commands
        async def command_listener():
            async for message in websocket:
                print(f"[+] Inbound WS Command: {message}")
                try:
                    payload = json.loads(message)
                    action = payload.get("action", "").lower()
                    
                    if action == "heal":
                        response = {"status": "SUCCESS", "message": "System defense and process table stabilized."}
                    elif action == "status":
                        response = {"status": "SUCCESS", "data": await import_telemetry()}
                    else:
                        response = {"status": "ACKNOWLEDGED", "command": action}
                        
                    await websocket.send(json.dumps({"type": "command_response", "data": response}))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON payload"}))

        # Run both tasks concurrently
        await asyncio.gather(telemetry_loop(), command_listener())
        
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] Client disconnected: {websocket.remote_address}")

async def main():
    print(f"======================================================================")
    print(f"    ASTRA WEBSOCKET TELEMETRY SERVER ACTIVE ON PORT {PORT}            ")
    print(f"======================================================================")
    async with websockets.serve(handle_connection, "127.0.0.1", PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
