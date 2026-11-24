#!/usr/bin/env python3
import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class AgentRouter:
    def __init__(self, pool_url: str = "http://127.0.0.1:8090/api/pool/route"):
        self.pool_url = pool_url
        self.agents = {
            "coder": {
                "name": "Coder",
                "prompt": "You write clean, production-ready Python and Bash scripts.",
                "endpoint": pool_url,
            },
            "reviewer": {
                "name": "Reviewer",
                "prompt": "You audit code for security flaws, socket leaks, and edge cases. Do not modify files.",
                "endpoint": pool_url,
            },
            "architect": {
                "name": "Architect",
                "prompt": "You design scalable multi-node systems, database schemas, and telemetry pipelines.",
                "endpoint": pool_url,
            },
        }
        self.active_agent = "coder"

    def switch(self, key: str) -> tuple[bool, str]:
        key = key.strip().lower()
        if key not in self.agents:
            return False, f"Unknown agent '{key}'. Available: {', '.join(self.agents.keys())}"
        self.active_agent = key
        return True, f"Switched active agent to {self.agents[key]['name']}"

    def _forward_to_pool(self, system_prompt: str, user_text: str) -> str:
        payload = {
            "prompt": user_text,
            "system": system_prompt,
            "use_system": True,
        }
        req = urllib.request.Request(
            self.pool_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=25.0) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
                if data.get("ok") and isinstance(data.get("routed"), dict):
                    return data["routed"].get("response") or "(empty response)"
                return f"[Offline Pool] {data.get('message') or json.dumps(data)}"
        except Exception as exc:
            return f"[Gateway Error] {exc}"

    def process(self, text: str, requested_agent: str | None = None) -> dict:
        if requested_agent and requested_agent.strip().lower() in self.agents:
            self.active_agent = requested_agent.strip().lower()

        raw = (text or "").strip()
        if raw.startswith("/switch "):
            target = raw.split(" ", 1)[1]
            _, msg = self.switch(target)
            return {"agent": self.active_agent, "reply": f"[System] {msg}"}

        if raw == "/agents":
            return {
                "agent": self.active_agent,
                "reply": f"[System] Agents: {', '.join(self.agents.keys())} (Active: {self.active_agent})",
            }

        agent = self.agents[self.active_agent]
        reply = self._forward_to_pool(agent["prompt"], raw)
        return {"agent": self.active_agent, "reply": f"[{agent['name'].upper()}]\n{reply}"}


ROUTER = AgentRouter()

HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Switcher Chat</title>
<style>
  body { font-family: monospace; background: #0d1117; color: #c9d1d9; margin: 0; display: flex; flex-direction: column; height: 100vh; }
  header { background: #161b22; padding: 12px 16px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 12px; }
  select, input, button { background: #0d1117; color: #58a6ff; border: 1px solid #30363d; padding: 8px 12px; border-radius: 6px; font-family: monospace; font-size: 14px; }
  #chat { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .msg { padding: 10px 14px; border-radius: 6px; max-width: 85%; line-height: 1.4; white-space: pre-wrap; }
  .user { background: #1f6feb; color: #fff; align-self: flex-end; }
  .bot { background: #161b22; border: 1px solid #30363d; align-self: flex-start; }
  footer { background: #161b22; padding: 12px 16px; border-top: 1px solid #30363d; display: flex; gap: 8px; }
  input { flex: 1; color: #c9d1d9; }
  button { background: #238636; color: #fff; border: none; cursor: pointer; font-weight: bold; }
  button:hover { background: #2ea043; }
</style>
</head>
<body>
<header>
  <span>ACTIVE AGENT:</span>
  <select id="agentSelect" onchange="switchViaDropdown()">
    <option value="coder">Coder (:8090 Pool)</option>
    <option value="reviewer">Reviewer (:8090 Pool)</option>
    <option value="architect">Architect (:8090 Pool)</option>
  </select>
</header>
<div id="chat"></div>
<footer>
  <input id="msgInput" type="text" placeholder="Type message or /switch reviewer..." onkeydown="if(event.key==='Enter') sendMsg()">
  <button onclick="sendMsg()">SEND</button>
</footer>
<script>
  const chat = document.getElementById('chat');
  const select = document.getElementById('agentSelect');
  const input = document.getElementById('msgInput');

  function addBubble(text, cls) {
    const div = document.createElement('div');
    div.className = 'msg ' + cls;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  async function switchViaDropdown() {
    await sendPayload('/switch ' + select.value);
  }

  async function sendMsg() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addBubble(text, 'user');
    await sendPayload(text);
  }

  async function sendPayload(text) {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ message: text, agent: select.value })
    });
    const data = await res.json();
    select.value = data.agent;
    addBubble(data.reply, 'bot');
  }
</script>
</body>
</html>"""


class ChatHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML_UI.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/chat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8", errors="ignore") or "{}")
        except json.JSONDecodeError:
            body = json.dumps({"error": "invalid_json"}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        result = ROUTER.process(payload.get("message", ""), payload.get("agent"))
        body = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8085), ChatHandler)
    print("Chat Switcher running on http://127.0.0.1:8085")
    server.serve_forever()
