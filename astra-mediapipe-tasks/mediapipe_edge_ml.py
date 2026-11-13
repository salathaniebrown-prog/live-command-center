import os, json, time, sqlite3, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-mediapipe-tasks")
BUNDLES = f"{BASE}/bundles"
DB = f"{BASE}/mediapipe_tasks.db"

SDK_TEMPLATES = {
    "WEB_WASM_WEBGPU": 'import { FilesetResolver, LlmInference } from "@mediapipe/tasks-genai";\nconst genai = await FilesetResolver.forGenAiTasks("https://jsdelivr.net");\nconst llm = await LlmInference.createFromOptions(genai, { baseOptions: { modelAssetPath: "/bundles/gemma4_gpu.task", delegate: "GPU" } });',
    "ANDROID_KOTLIN_JAVA": 'val options = LlmInference.LlmInferenceOptions.builder().setModelPath("/data/local/tmp/llm/gemma4.task").setMaxTokens(1024).setPreferredBackend(LlmInference.Backend.GPU).build()\nval llm = LlmInference.createFromOptions(context, options)',
    "IOS_SWIFT_OBJC": 'let options = LlmInferenceOptions(modelPath: Bundle.main.path(forResource: "gemma4", ofType: "task")!)\noptions.maxTokens = 1024\nlet llm = try LlmInference(options: options)',
    "FLUTTER_DART": 'final engine = await MediaPipeGenAi.create(modelPath: "assets/gemma4.task", delegate: Delegate.gpu);\nfinal out = await engine.generateResponse(prompt);',
    "PYTHON_LINUX_MAC_WIN": 'import mediapipe as mp\nfrom mediapipe.tasks import python\nfrom mediapipe.tasks.python import text\noptions = text.TextClassifierOptions(base_options=python.BaseOptions(model_asset_path="astra_bundle.task", delegate=python.BaseOptions.Delegate.GPU))'
}

def init():
    os.makedirs(BUNDLES, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS task_bundles(id TEXT PRIMARY KEY, task_type TEXT, platform TEXT, delegate TEXT, file_path TEXT, ts REAL)")
    c.commit(); c.close()

def build_task_bundle(task_type="VISION_TEXT_AUDIO_RAG", platform="WEB_WASM_WEBGPU", delegate="GPU"):
    tid = "MPT-" + hashlib.sha256(f"{task_type}:{platform}:{time.time()}".encode()).hexdigest()[:6].upper()
    meta = {
        "task_bundle_id": tid,
        "architecture": "MediaPipe Tasks (.task FlatBuffer + TFLite + Metadata)",
        "domain": task_type,
        "target_platform": platform,
        "accelerator_delegate": delegate,
        "capabilities": ["Vision (Object/Pose/OCR)", "Text (Gemma 4 / Embedding)", "Audio (Whisper/Classifier)", "Retrieval (Vector Cosine)", "Decision-Models (OODA Router)"],
        "sdk_code": SDK_TEMPLATES.get(platform, SDK_TEMPLATES["WEB_WASM_WEBGPU"])
    }
    fp = os.path.join(BUNDLES, f"{tid}_{platform.lower()}.task.json")
    open(fp, "w", encoding="utf-8").write(json.dumps(meta, indent=2))
    c = sqlite3.connect(DB); c.execute("INSERT INTO task_bundles VALUES(?,?,?,?,?,?)", (tid, task_type, platform, delegate, fp, time.time())); c.commit(); c.close()
    return meta

class Handler(BaseHTTPRequestHandler):
    def _j(self, d):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        c = sqlite3.connect(DB); n = c.execute("SELECT COUNT(*) FROM task_bundles").fetchone()[0]; c.close()
        self._j({"status": "MEDIAPIPE_TASKS_ONLINE", "port": 8112, "bundles_built": n, "platforms": list(SDK_TEMPLATES.keys())})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        self._j(build_task_bundle(d.get("task_type", "VISION_TEXT_AUDIO_RAG"), d.get("platform", "WEB_WASM_WEBGPU"), d.get("delegate", "GPU")))

init()
HTTPServer(("0.0.0.0", 8112), Handler).serve_forever()
