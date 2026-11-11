import os
import json
import urllib.request
import urllib.error

LLM_API_URL = os.environ.get("LLM_177B_ENDPOINT", "https://openai.com")
LLM_API_KEY = os.environ.get("LLM_177B_API_KEY", "")
MODEL_177B = os.environ.get("LLM_177B_MODEL", "qwen-max-177b-moe")

def compress_context(text: str, max_chars: int = 12000) -> str:
    """Space-efficient sliding window: preserves system rules and latest logs."""
    if len(text) <= max_chars:
        return text
    head = text[:3000]
    tail = text[-(max_chars - 3000):]
    return f"{head}\n\n...[COMPRESSED TELEMETRY SLICE]...\n\n{tail}"

def query_177b(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    if not LLM_API_KEY:
        return "[OFFLINE_FALLBACK] Set LLM_177B_API_KEY to enable 177B cloud reasoning."

    payload = {
        "model": MODEL_177B,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": compress_context(system_prompt, 4000)},
            {"role": "user", "content": compress_context(user_prompt, 10000)}
        ]
    }

    req = urllib.request.Request(
        LLM_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:
        return f"[177B_ROUTER_ERROR] {str(e)}"
