import os, json, time, math, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
BASE = os.path.expanduser("~/astra-mediapipe-tasks")
BUNDLES, MODELS = os.path.join(BASE, "bundles"), os.path.join(BASE, "models")
os.makedirs(BUNDLES, exist_ok=True); os.makedirs(MODELS, exist_ok=True)
DB = os.path.join(BASE, "mediapipe_tasks.db")
MODEL_MAP = {"VISION": "efficientdet_lite0.tflite", "TEXT": "bert_classifier.tflite", "RETRIEVAL": "universal_sentence_encoder.tflite", "AUDIO": "yamnet.tflite", "DECISION": "bert_classifier.tflite"}
ENGINE, Interpreter, INTERPS = "litert-edge-runtime", None, {}
for mod in ("ai_edge_litert.interpreter", "tflite_runtime.interpreter"):
    try:
        Interpreter = __import__(mod, fromlist=["Interpreter"]).Interpreter
        ENGINE = mod.split(".")[0]; break
    except Exception: pass
def load_models():
    out = {}
    for t, fn in MODEL_MAP.items():
        fp = os.path.join(MODELS, fn)
        ok = os.path.isfile(fp) and os.path.getsize(fp) > 10000
        if ok and Interpreter and fn not in INTERPS:
            try:
                it = Interpreter(model_path=fp); it.allocate_tensors(); INTERPS[fn] = it
            except Exception: pass
        out[t] = {"model": fn, "ready": ok, "mb": round(os.path.getsize(fp)/1048576, 2) if os.path.isfile(fp) else 0, "interp": fn in INTERPS}
    return out
SDKS = {
    "WEB_WASM_WEBGPU": {"pkgs": ["@mediapipe/tasks-vision", "@mediapipe/tasks-text", "@mediapipe/tasks-audio"], "delegate": "GPU (WebGPU/WASM)"},
    "ANDROID_KOTLIN_JAVA": {"pkgs": ["com.google.mediapipe:tasks-vision:latest.release"], "delegate": "Delegate.GPU"},
    "IOS_SWIFT_OBJC": {"pkgs": ["MediaPipeTasksVision", "MediaPipeTasksText"], "delegate": "MPPDelegate.GPU"},
    "PYTHON_LINUX_MAC_WIN": {"pkgs": ["mediapipe", "ai-edge-litert"], "delegate": "BaseOptions.Delegate.GPU"},
    "FLUTTER_MULTI_OS": {"pkgs": ["mediapipe_vision", "mediapipe_text", "mediapipe_audio"], "delegate": "HardwareDelegate.gpu"}
}
def init_db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS task_bundles(id TEXT PRIMARY KEY, task_type TEXT, platform TEXT, delegate TEXT, file_path TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS retrieval_vectors(id INTEGER PRIMARY KEY AUTOINCREMENT, doc_text TEXT, vec_json TEXT, ts REAL)")
    c.commit(); c.close()
def embed(s):
    d = [0.0]*16
    for i, ch in enumerate(s.lower().encode()): d[i%16] += (ch%37)/37.0
    n = math.sqrt(sum(x*x for x in d)) or 1.0
    return [round(x/n, 4) for x in d]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, d):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers(); self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        c = sqlite3.connect(DB); b = c.execute("SELECT COUNT(*) FROM task_bundles").fetchone()[0]; v = c.execute("SELECT COUNT(*) FROM retrieval_vectors").fetchone()[0]; c.close()
        self._j({"status": "MEDIAPIPE_TASKS_ONLINE", "port": 8113, "engine": ENGINE, "models": load_models(), "bundles": b, "vectors": v})
    def do_POST(self):
        t0 = time.time(); d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}"); m = load_models()
        if self.path.startswith("/infer"):
            tk = d.get("task_type", "DECISION").upper(); q = str(d.get("input", ""))
            if tk == "RETRIEVAL":
                vec = embed(q); c = sqlite3.connect(DB)
                if d.get("index"):
                    c.execute("INSERT INTO retrieval_vectors(doc_text,vec_json,ts) VALUES(?,?,?)", (q, json.dumps(vec), time.time())); c.commit(); c.close()
                    return self._j({"task": "RETRIEVAL_INDEX", "model": m["RETRIEVAL"], "ms": round((time.time()-t0)*1000, 2)})
                rows = c.execute("SELECT doc_text,vec_json FROM retrieval_vectors ORDER BY id DESC LIMIT 50").fetchall(); c.close()
                hits = sorted([{"score": round(sum(a*b for a,b in zip(vec, json.loads(vj))), 4), "text": tx} for tx, vj in rows], key=lambda x: x["score"], reverse=True)[:3]
                return self._j({"task": "RETRIEVAL_SEARCH", "model": m["RETRIEVAL"], "matches": hits, "ms": round((time.time()-t0)*1000, 2)})
            if tk == "DECISION":
                ql = q.lower()
                rt = "VISION" if any(k in ql for k in ("cam","detect","image","pose")) else "AUDIO" if any(k in ql for k in ("audio","voice","mic")) else "RETRIEVAL" if any(k in ql for k in ("search","find","rag")) else "TEXT"
                return self._j({"task": "DECISION_ROUTER", "route": rt, "target_model": m[rt], "ms": round((time.time()-t0)*1000, 2)})
            return self._j({"task": tk, "engine": ENGINE, "model": m.get(tk, m["TEXT"]), "embed": embed(q)[:6], "ms": round((time.time()-t0)*1000, 2)})
        tid = f"mp_{int(time.time()*1000)}"; pl = d.get("platform", "WEB_WASM_WEBGPU"); fp = os.path.join(BUNDLES, f"{tid}_{pl.lower()}.task.json")
        bnd = {"bundle_id": tid, "task_type": d.get("task_type", "VISION_TEXT_AUDIO_RAG"), "platform": pl, "delegate": d.get("delegate", "GPU"), "models": m, "sdk": SDKS.get(pl, SDKS["WEB_WASM_WEBGPU"])}
        with open(fp, "w") as f: json.dump(bnd, f)
        c = sqlite3.connect(DB); c.execute("INSERT INTO task_bundles VALUES(?,?,?,?,?,?)", (tid, bnd["task_type"], pl, bnd["delegate"], fp, time.time())); c.commit(); c.close()
        self._j({"status": "BUNDLE_BUILT", "bundle_id": tid, "path": fp, "bundle": bnd})
init_db(); load_models(); HTTPServer(("0.0.0.0", 8113), H).serve_forever()
