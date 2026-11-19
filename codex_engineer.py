import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Gemini 1.5/3.6 Flash Endpoint (using standard v1beta API)
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

def ask_ai_to_fix(filepath, error_msg):
    with open(filepath, 'r') as f:
        code = f.read()

    prompt = f"Fix the following Python code. The error is: {error_msg}\n\nCode:\n{code}\n\nReturn ONLY the complete, corrected Python code. Do not use markdown blocks or explanations."

    # Gemini payload structure
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        req = urllib.request.Request(API_URL, data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            # Extract text from Gemini response
            fixed_code = result['candidates'][0]['content']['parts'][0]['text'].strip()

            # Clean up markdown formatting if the AI added it
            if fixed_code.startswith("```python"):
                fixed_code = fixed_code[9:]
            if fixed_code.startswith("```"):
                fixed_code = fixed_code[3:]
            if fixed_code.endswith("```"):
                fixed_code = fixed_code[:-3]

            with open(filepath, 'w') as f:
                f.write(fixed_code.strip())
            return True, "Code fixed successfully."
    except Exception as e:
        return False, str(e)

class CodexHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

        filepath = post_data.get('filepath')
        error_msg = post_data.get('error')

        success, message = ask_ai_to_fix(filepath, error_msg)

        self.send_response(200 if success else 500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"success": success, "message": message}).encode('utf-8'))
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    PORT = 8122
    print(f"[CODEX ENGINEER] Listening on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), CodexHandler)
    server.serve_forever()
