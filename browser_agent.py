import os
import json
import urllib.parse
import urllib.request
import html.parser
from http.server import BaseHTTPRequestHandler, HTTPServer

class AgentParser(html.parser.HTMLParser):
    def __init__(_self):
        super().__init__()
        self.links = []
        self.text = []
        self.in_script = False

    def handle_starttag(_self, tag, attrs):
        if tag == 'script' or tag == 'style':
            self.in_script = True
        if tag == 'a':
            for name, value in attrs:
                if name == 'href':
                    self.links.append(value)

    def handle_endtag(_self, tag):
        if tag == 'script' or tag == 'style':
            self.in_script = False

    def handle_data(_self, data):
        if not self.in_script:
            cleaned = data.strip()
            if cleaned:
                self.text.append(cleaned)

class BrowserAgentHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b'browser_agent_active')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        task = post_data.get('task')
        url = post_data.get('url')
        result = "{}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'AstraAgent/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                parser = AgentParser()
                parser.feed(html)
                if task == 'extract_links':
                    result = json.dumps({'status': 'ok', 'links': parser.links})
                elif task == 'extract_text':
                    result = json.dumps({'status': 'ok', 'text': ' '.join(parser.text[:50])})
                else:
                    result = json.dumps({'status': 'ok', 'message': 'Unknown task'})
        except Exception as e:
            result = json.dumps({'status': 'error', 'message': str(e)})
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.write(result.encode('utf-8'))

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    PORT = 8116
    print(f"[BROWSER AGENT] Listening on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), BrowserAgentHandler)
    server.serve_forever()
