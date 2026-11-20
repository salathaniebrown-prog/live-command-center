import asyncio, os, sqlite3, subprocess, tempfile, time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
BASE_DIR = os.path.expanduser("~/portable_vserver")
DB_PATH = os.path.join(BASE_DIR, "vserver_state.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE IF NOT EXISTS execution_store (id INTEGER PRIMARY KEY AUTOINCREMENT, language TEXT, code TEXT, stdout TEXT, stderr TEXT, exec_ms REAL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

init_db()

class CodePayload(BaseModel):
    language: str
    code: str
    timeout: int = 30

def run_isolated_code(lang: str, code: str, timeout: int):
    start = time.perf_counter()
    lang = lang.lower().strip()
    with tempfile.TemporaryDirectory(dir=os.path.join(BASE_DIR, "workspaces")) as tmpdir:
        if lang in ("python", "py", "python3"):
            src = os.path.join(tmpdir, "main.py")
            with open(src, "w") as f: f.write(code)
            cmd = ["python3", src]
        elif lang in ("bash", "sh"):
            src = os.path.join(tmpdir, "run.sh")
            with open(src, "w") as f: f.write(code)
            cmd = ["bash", src]
        elif lang in ("javascript", "js", "node"):
            src = os.path.join(tmpdir, "index.js")
            with open(src, "w") as f: f.write(code)
            cmd = ["node", src]
        elif lang in ("c", "cpp", "c++"):
            ext = "c" if lang == "c" else "cpp"
            compiler = "gcc" if lang == "c" else "g++"
            src = os.path.join(tmpdir, f"prog.{ext}")
            bin_out = os.path.join(tmpdir, "prog")
            with open(src, "w") as f: f.write(code)
            comp = subprocess.run([compiler, src, "-O3", "-o", bin_out], capture_output=True, text=True)
            if comp.returncode != 0:
                return "", comp.stderr, round((time.perf_counter() - start) * 1000, 2)
            cmd = [bin_out]
        else:
            raise ValueError(f"Unsupported language: {lang}")
        res = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True, timeout=timeout)
        return res.stdout, res.stderr, round((time.perf_counter() - start) * 1000, 2)

@app.post("/exec")
async def execute_code(payload: CodePayload):
    try:
        stdout, stderr, exec_ms = await asyncio.to_thread(run_isolated_code, payload.language, payload.code, payload.timeout)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO execution_store (language, code, stdout, stderr, exec_ms) VALUES (?, ?, ?, ?, ?)", (payload.language, payload.code, stdout, stderr, exec_ms))
        conn.commit()
        conn.close()
        return {"status": "ok", "stdout": stdout, "stderr": stderr, "exec_ms": exec_ms}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
async def health():
    return {"node": "PORTABLE_VSERVER_8101", "status": "ONLINE", "cpu_cores": os.cpu_count()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8101)
