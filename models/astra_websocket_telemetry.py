import asyncio, json, random, time, hashlib, base64

def make_ws_frame(message):
    data = message.encode('utf-8')
    length = len(data)
    if length <= 125:
        header = bytes([129, length])
    elif length <= 65535:
        header = bytes([129, 126]) + length.to_bytes(2, 'big')
    else:
        header = bytes([129, 127]) + length.to_bytes(8, 'big')
    return header + data

async def handle_client(reader, writer):
    try:
        request_data = await reader.read(2048)
        request_text = request_data.decode('utf-8', errors='ignore')
        
        key = None
        for line in request_text.split('\r\n'):
            if line.lower().startswith('sec-websocket-key:'):
                key = line.split(':', 1)[1].strip()
                break
                
        if key:
            guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            sha1 = hashlib.sha1((key + guid).encode('utf-8')).digest()
            accept_key = base64.b64encode(sha1).decode('utf-8')
            
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
            )
            writer.write(response.encode('utf-8'))
            await writer.drain()

            while True:
                payload = {
                    "event": "TELEMETRY_PULSE",
                    "assistant_status": "ONLINE",
                    "active_nodes": 10248,
                    "gpu_memory_used_mb": random.randint(3200, 4800),
                    "network_latency_ms": round(random.uniform(12.1, 24.5), 1),
                    "timestamp": time.time()
                }
                writer.write(make_ws_frame(json.dumps(payload)))
                await writer.drain()
                await asyncio.sleep(2)
        else:
            writer.close()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except:
            pass

async def main():
    while True:
        try:
            server = await asyncio.start_server(handle_client, '0.0.0.0', 8081)
            print("[WebSocket] Native Telemetry Server running on port 8081")
            async with server:
                await server.serve_forever()
        except Exception as e:
            print(f"[WebSocket Restarting] Error: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
