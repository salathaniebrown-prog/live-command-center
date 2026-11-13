import json, os, sqlite3, subprocess, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
DB = os.path.expanduser("~/astra-multimodal/multimodal.db")
c = sqlite3.connect(DB); c.execute("PRAGMA journal_mode=WAL")
c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,kind TEXT,content TEXT,analysis TEXT,ts REAL)"); c.commit(); c.close()
def sh(cmd):
    try: return subprocess.check_output(cmd, shell=True, timeout=4, stderr=subprocess.DEVNULL).decode().strip()
    except Exception: return ""
def analyze(kind, text):
    tag = "URL" if "http" in text else ("VIN" if len(text)==17 and text.isalnum() else ("CODE" if any(k in text for k in ("def ","import ","SELECT ","curl ")) else "TEXT"))
    return f"[{tag}] len={len(text)} | {text[:140]}"
def watcher():
    last = ""
    while True:
        clip = sh("termux-clipboard-get")
        if clip and clip != last:
            last = clip; conn = sqlite3.connect(DB); conn.execute("INSERT INTO events(kind,content,analysis,ts) VALUES(?,?,?,?)", ("CLIPBOARD", clip, analyze("CLIPBOARD", clip), time.time())); conn.commit(); conn.close()
        time.sleep(15)
class H(BaseHTTPRequestHandler):
    def _j(self, d, code=200):
        self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers(); self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
        if "/clipboard" in self.path:
            clip = sh("termux-clipboard-get") or "No Termux:API clipboard text"
            self._j({"status":"OK","clipboard":clip,"analysis":analyze("CLIPBOARD",clip)})
        elif "/screen" in self.path:
            shot = sh("ls -t /sdcard/Pictures/Screenshots/* /sdcard/DCIM/Screenshots/* 2>/dev/null | head -n 1")
            ocr = sh(f'tesseract "{shot}" stdout --psm 6') if shot else ""
            summary = analyze("SCREEN_OCR", ocr) if ocr else "No readable text or screenshot found"
            if ocr:
                conn.execute("INSERT INTO events(kind,content,analysis,ts) VALUES(?,?,?,?)", ("SCREEN_OCR", ocr[:2000], summary, time.time())); conn.commit()
            self._j({"status":"OK","latest_screenshot":shot or "None found","analysis":summary,"ocr_text":ocr[:1500]})
        else:
            rows = [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 10")]
            self._j({"status":"ONLINE","port":8110,"proactive_events":rows})
        conn.close()
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
        txt = data.get("text") or sh("termux-speech-to-text") or "Voice/Text prompt received"
        ans = analyze("VOICE_TEXT", txt)
        if data.get("speak"): sh(f"termux-tts-speak {json.dumps(ans)}")
        conn = sqlite3.connect(DB); conn.execute("INSERT INTO events(kind,content,analysis,ts) VALUES(?,?,?,?)", ("VOICE_TEXT", txt, ans, time.time())); conn.commit(); conn.close()
        self._j({"status":"OK","input":txt,"response":ans})
threading.Thread(target=watcher, daemon=True).start()
HTTPServer(("0.0.0.0", 8110), H).serve_forever()
