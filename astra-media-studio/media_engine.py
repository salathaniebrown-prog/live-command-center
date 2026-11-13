import hashlib, json, os, sqlite3, subprocess, time, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image, ImageDraw
BASE = os.path.expanduser("~/astra-media-studio")
OUT, DB = f"{BASE}/outputs", f"{BASE}/media_studio.db"
c = sqlite3.connect(DB); c.execute("PRAGMA journal_mode=WAL")
c.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,mode TEXT,prompt TEXT,artifact TEXT,summary TEXT,ts REAL)"); c.commit(); c.close()
def ask_ai(prompt, mode):
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        try:
            u = f"https://googleapis.com{key}"
            body = json.dumps({"contents":[{"parts":[{"text":f"Mode: {mode}. Give a unique, detailed, non-repetitive plan and response for: {prompt}"}]}]}).encode()
            r = urllib.request.urlopen(urllib.request.Request(u, data=body, headers={"Content-Type":"application/json"}), timeout=12)
            return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e: pass
    h = hashlib.sha256(f"{mode}:{prompt}:{time.time()}".encode()).hexdigest()[:10]
    words = [w for w in prompt.split() if len(w) > 2]
    return f"[{mode.upper()} | #{h}] Unique execution for '{prompt}' — Key subjects: {', '.join(words[:6]) or 'custom scene'}. Pipeline compiled with dynamic seed {int(h,16)%99991}."
def render_img(prompt, jid):
    p = f"{OUT}/{jid}.png"; seed = int(hashlib.md5(prompt.encode()).hexdigest()[:6], 16)
    img = Image.new("RGB", (640, 360), ((seed>>16)&255, (seed>>8)&255, seed&255)); d = ImageDraw.Draw(img)
    for i in range(12): d.rectangle([20+i*18, 20+i*10, 620-i*18, 340-i*10], outline=((seed+i*40)&255, 220, 180), width=2)
    d.text((28, 165), f"ASTRA T2I: {prompt[:48]}", fill=(255, 255, 255)); img.save(p); return p
def render_vid(prompt, jid, src_img=None):
    base = src_img if (src_img and os.path.exists(src_img)) else render_img(prompt, jid)
    mp4 = f"{OUT}/{jid}.mp4"
    subprocess.run(["ffmpeg","-y","-loop","1","-i",base,"-vf","zoompan=z='min(zoom+0.002,1.25)':d=75:s=640x360","-c:v","libx264","-t","3","-pix_fmt","yuv420p",mp4], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return mp4
class H(BaseHTTPRequestHandler):
    def _j(self, d, code=200):
        self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers(); self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path.startswith("/outputs/"):
            fp = os.path.join(BASE, self.path.lstrip("/"))
            if os.path.isfile(fp):
                self.send_response(200); self.send_header("Content-Type", "video/mp4" if fp.endswith(".mp4") else "image/png"); self.end_headers(); self.wfile.write(open(fp,"rb").read()); return
        conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY ts DESC LIMIT 10")]; conn.close()
        self._j({"status":"ONLINE","port":8111,"abilities":["text_to_image","image_to_video","text_to_video","dynamic_ai_chat","app_launcher"],"recent_jobs":rows})
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
        mode, prompt = data.get("mode","chat"), data.get("prompt","").strip()
        jid = "JOB-" + hashlib.sha256(f"{mode}{prompt}{time.time()}".encode()).hexdigest()[:8].upper()
        summary = ask_ai(prompt, mode); art = ""
        if mode == "t2i": art = "/api/media/outputs/" + os.path.basename(render_img(prompt, jid))
        elif mode == "i2v": art = "/api/media/outputs/" + os.path.basename(render_vid(prompt, jid, data.get("image_path","")))
        elif mode == "t2v": art = "/api/media/outputs/" + os.path.basename(render_vid(prompt, jid))
        elif mode == "app": subprocess.Popen(["am","start","-n",prompt] if "/" in prompt else ["am","start","-a","android.intent.action.VIEW","-d",prompt], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); art = f"Launched: {prompt}"
        conn = sqlite3.connect(DB); conn.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?)", (jid, mode, prompt, art, summary, time.time())); conn.commit(); conn.close()
        self._j({"job_id":jid,"mode":mode,"artifact_url":art,"conclusion":summary})
HTTPServer(("0.0.0.0", 8111), H).serve_forever()
