import os
import asyncio
from aiohttp import web, ClientSession, ClientTimeout

FAST_LOCAL_UPSTREAM = "http://127.0.0.1:11434/api/generate"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
HEAVY_CLOUD_UPSTREAM = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={GEMINI_API_KEY}"

async def forward_request(target_url: str, payload: dict, timeout_sec: int = 8):
    timeout = ClientTimeout(total=timeout_sec)
    async with ClientSession(timeout=timeout) as session:
        async with session.post(target_url, json=payload) as resp:
            return resp.status, await resp.json()

async def route_fast_8108(request: web.Request) -> web.Response:
    payload = await request.json()
    try:
        status, data = await forward_request(FAST_LOCAL_UPSTREAM, payload, timeout_sec=4)
        return web.json_response({"routed_via": "8108-local", "data": data}, status=status)
    except Exception as e:
        status, data = await forward_request("http://127.0.0.1:8109/infer", payload, timeout_sec=15)
        return web.json_response({"routed_via": "8108->8109-failover", "reason": str(e), "data": data}, status=status)

async def route_heavy_8109(request: web.Request) -> web.Response:
    payload = await request.json()
    status, data = await forward_request(HEAVY_CLOUD_UPSTREAM, payload, timeout_sec=20)
    return web.json_response({"routed_via": "8109-heavy", "data": data}, status=status)

async def start_routers():
    app_8108 = web.Application()
    app_8108.router.add_post("/infer", route_fast_8108)

    app_8109 = web.Application()
    app_8109.router.add_post("/infer", route_heavy_8109)

    runner_8108 = web.AppRunner(app_8108)
    runner_8109 = web.AppRunner(app_8109)
    await runner_8108.setup()
    await runner_8109.setup()

    await web.TCPSite(runner_8108, "127.0.0.1", 8108).start()
    await web.TCPSite(runner_8109, "127.0.0.1", 8109).start()
    print("Studio Pro Routers online: 8108 (Fast/Failover) & 8109 (Heavy)")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_routers())
