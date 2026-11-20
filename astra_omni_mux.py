import asyncio, httpx, uvicorn
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import websockets

app = FastAPI(title="ASTRA // OMNI-PORT HTTPS MUX")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"]
)

LO = "127.0.0.1"
ALLOWED_PORTS = set(range(3000, 9000))

async def proxy_http(req: Request, port: int, subpath: str):
    if port not in ALLOWED_PORTS:
        return Response("Port blocked", status_code=403)
    qs = req.url.query
    tail = f"/{subpath}" if subpath else "/"
    if qs:
        tail += f"?{qs}"
    target = f"http://{LO}:{port}{tail}"
    body = await req.body()
    hdrs = {
        k: v for k, v in req.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    async with httpx.AsyncClient(timeout=60.0) as cl:
        try:
            r = await cl.request(
                req.method, target, content=body, headers=hdrs
            )
            out_h = {
                k: v for k, v in r.headers.items()
                if k.lower() not in (
                    "content-encoding", "transfer-encoding", "content-length"
                )
            }
            return Response(
                content=r.content, status_code=r.status_code, headers=out_h
            )
        except Exception as e:
            return Response(f"Upstream :{port} offline ({e})", status_code=502)

@app.api_route(
    "/p/{port:int}/{subpath:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def route_any_port(port: int, subpath: str, req: Request):
    return await proxy_http(req, port, subpath)

@app.api_route(
    "/p/{port:int}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def route_any_port_root(port: int, req: Request):
    return await proxy_http(req, port, "")

@app.api_route(
    "/8090/{subpath:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def shortcut_8090(subpath: str, req: Request):
    return await proxy_http(req, 8090, subpath)

@app.api_route("/8090", methods=["GET", "POST"])
async def shortcut_8090_root(req: Request):
    return await proxy_http(req, 8090, "")

@app.websocket("/p/{port:int}/{subpath:path}")
async def proxy_ws(ws: WebSocket, port: int, subpath: str):
    await ws.accept()
    uri = f"ws://{LO}:{port}/{subpath}"
    try:
        async with websockets.connect(uri) as upstream:
            async def c2u():
                while True:
                    await upstream.send(await ws.receive_text())
            async def u2c():
                while True:
                    await ws.send_text(await upstream.recv())
            await asyncio.gather(c2u(), u2c())
    except Exception:
        await ws.close()

@app.api_route(
    "/{subpath:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def default_8088(subpath: str, req: Request):
    return await proxy_http(req, 8088, subpath)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
