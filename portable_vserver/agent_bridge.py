import asyncio, json, os, re, sqlite3, httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI()
DB_PATH = os.path.expanduser("~/portable_vserver/agent_memory.db")
VSERVER_URL = "http://127.0.0.1:8101"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE IF NOT EXISTS chat_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, message TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

init_db()
CODE_BLOCK_RE = re.compile(r"```(\w+)\s*\n([\s\S]*?)```")

async def dispatch_to_vserver(language: str, code: str) -> dict:
    async with httpx.AsyncClient(timeout=35.0) as client:
        resp = await client.post(f"{VSERVER_URL}/exec", json={"language": language, "code": code, "timeout": 30})
        resp.raise_for_status()
        return resp.json()

async def run_agent_reasoning(user_msg: str) -> str:
    match = CODE_BLOCK_RE.search(user_msg)
    if match:
        lang, code = match.group(1).lower(), match.group(2).strip()
        try:
            result = await dispatch_to_vserver(lang, code)
            out, err, ms = result.get("stdout", "").strip(), result.get("stderr", "").strip(), result.get("exec_ms", 0)
            parts = [f"[AGENT -> VSERVER 8101 | {lang.upper()} | {ms}ms]"]
            if out: parts.append(f"STDOUT:\n{out}")
            if err: parts.append(f"STDERR:\n{err}")
            return "\n".join(parts)
        except Exception as e:
            return f"[AGENT -> VSERVER 8101 ERROR] {str(e)}"
    if user_msg.strip().lower() in ("status", "health", "ping"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                h = (await client.get(f"{VSERVER_URL}/health")).json()
            return f"[AGENT ONLINE] Bridge 8099 -> Compute Node {h.get('node')} ({h.get('cpu_cores')} cores active)"
        except Exception as e:
            return f"[AGENT ONLINE] Warning: VServer 8101 unreachable ({e})"
    return f"[AGENT ACTIVE] Received: '{user_msg}'. Send a fenced code block to execute on VServer 8101."

@app.websocket("/ws/chat")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO chat_logs (sender, message) VALUES (?, ?)", ("USER", data))
            conn.commit()
            reply = await run_agent_reasoning(data)
            conn.execute("INSERT INTO chat_logs (sender, message) VALUES (?, ?)", ("AGENT", reply))
            conn.commit()
            conn.close()
            await websocket.send_text(json.dumps({"role": "agent", "content": reply}))
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099)
