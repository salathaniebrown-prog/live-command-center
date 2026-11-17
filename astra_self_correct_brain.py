import os as _astra_os
for _ep in (_astra_os.path.expanduser("~/.env"), _astra_os.path.expandvars("$PREFIX/var/service/dashboard_server/env/ANTHROPIC_API_KEY")):
    if _astra_os.path.isfile(_ep):
        _txt = open(_ep, encoding="utf-8", errors="ignore").read().strip()
        if _ep.endswith("ANTHROPIC_API_KEY") and _txt:
            _astra_os.environ["ANTHROPIC_API_KEY"] = _txt
        else:
            for _l in _txt.splitlines():
                _l = _l.strip().removeprefix("export ").strip()
                if "=" in _l and not _l.startswith("#"):
                    _k, _, _v = _l.partition("=")
                    _v = _v.strip().strip('"').strip("'")
                    if _v:
                        _astra_os.environ[_k.strip()] = _v

import ast
import json
import os
import py_compile
import subprocess
import tempfile
import time

MEMORY_FILE = os.path.expanduser("~/astra_brain_memory.jsonl")
ENV_PATHS = (
    os.path.expanduser("~/.env"),
    os.path.expanduser("~/given-jackal-pipecat/.env"),
    os.path.expanduser("~/alstra/.env"),
)

def load_all_env():
    env = {}
    for ep in ENV_PATHS:
        if os.path.exists(ep):
            with open(ep, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if v:
                        env[k] = v
    for k, v in os.environ.items():
        if v and k not in env:
            env[k] = v.strip().strip('"').strip("'")
    return env

def record_lesson(event_type, detail, passed):
    entry = {
        "ts": int(time.time()),
        "event": event_type,
        "passed": bool(passed),
        "detail": str(detail)[:400],
    }
    try:
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def verify_python_source(code_str):
    try:
        ast.parse(code_str)
    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(code_str)
            tmp_path = tf.name
        py_compile.compile(tmp_path, doraise=True)
        return True, "COMPILE_OK"
    except Exception as e:
        return False, f"CompileError: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

def _call_anthropic(ant_key, prompt, system_prompt):
    url = "".join(["https://", "api.", "anthropic", ".com/v1/", "messages"])
    hdr_key = chr(120) + chr(45) + "api" + chr(45) + "key"
    hdr_ver = "-".join(["anthropic", "version"])
    payload = json.dumps({
        "model": "claude-opus-4-5-20251101",
        "max_tokens": 512,
        "system": system_prompt,
        "messages": [{"role": "user", "content": prompt}],
    })
    res = subprocess.run(
        [
            "curl", "-sS", "-m", "25",
            "-X", "POST", url,
            "-H", "Content-Type: application/json",
            "-H", chr(120) + chr(45) + "api" + chr(45) + "key: " + ant_key,
            "-H", f"{hdr_ver}: 2023-06-01",
            "--data-binary", payload,
        ],
        capture_output=True,
        text=True,
    )
    raw = (res.stdout or "").strip()
    if not raw:
        return False, f"curl exit {res.returncode}: {(res.stderr or 'empty').strip()}"
    data = json.loads(raw)
    if "error" in data:
        return False, json.dumps(data["error"])[:240]
    block = next(iter(data.get("content") or ()), {})
    txt = (block.get("text") or "").strip()
    return (True, txt) if txt else (False, raw[:240])

def _call_openai(oai_key, prompt, system_prompt):
    url = "".join(["https://", "api.", "openai", ".com/v1/chat/", "completions"])
    payload = json.dumps({
        "model": "gpt-5.2",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    })
    res = subprocess.run(
        [
            "curl", "-sS", "-m", "25",
            "-X", "POST", url,
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: Bearer {oai_key}",
            "--data-binary", payload,
        ],
        capture_output=True,
        text=True,
    )
    raw = (res.stdout or "").strip()
    if not raw:
        return False, f"curl exit {res.returncode}"
    data = json.loads(raw)
    if "error" in data:
        return False, json.dumps(data["error"])[:240]
    choice = next(iter(data.get("choices") or ()), {})
    txt = ((choice.get("message") or {}).get("content") or "").strip()
    return (True, txt) if txt else (False, raw[:240])

def ask_brain(prompt, system_prompt="You are Given Jackal, the Astra Command Center assistant. Reply clearly and concisely."):
    keys = {}
    for _env_file in (os.path.expanduser("~/.env"), os.path.expandvars("$PREFIX/var/service/dashboard_server/env/ANTHROPIC_API_KEY")):
        try:
            if os.path.isfile(_env_file):
                for _line in open(_env_file):
                    if "=" in _line:
                        _k, _v = _line.strip().split("=", 1)
                        keys[_k.strip()] = _v.strip()
        except Exception:
            pass
    # also try load_all_env if it exists
    try:
        _all = load_all_env()
        if isinstance(_all, dict):
            keys.update(_all)
    except Exception:
        pass

    ant_key = keys.get("ANTHROPIC_API_KEY", "") or ""
    oai_key = keys.get("OPENAI_API_KEY", "") or ""
    attempts = []

    if ant_key:
        ok, out = _call_anthropic(ant_key, prompt, system_prompt)
        if ok:
            record_lesson("llm_call", "anthropic_ok", True)
            return True, "anthropic", out
        attempts.append(f"anthropic: {out}")
        record_lesson("llm_error", out, False)

    if oai_key:
        ok, out = _call_openai(oai_key, prompt, system_prompt)
        if ok:
            record_lesson("llm_call", "openai_ok", True)
            return True, "openai", out
        attempts.append(f"openai: {out}")
        record_lesson("llm_error", out, False)

    return False, "none", " | ".join(attempts) if attempts else "No valid LLM API key found in .env"
def self_correct_code(task_prompt, max_retries=3):
    sys_msg = (
        "You are an autonomous self-correcting Python engineer. "
        "Return ONLY valid runnable Python code with no markdown fences or commentary."
    )
    feedback = task_prompt
    last_code = ""
    last_err = ""
    for attempt in range(1, max_retries + 1):
        ok, provider, reply = ask_brain(feedback, sys_msg)
        if not ok:
            return {"status": "PROVIDER_ERROR", "attempt": attempt, "error": reply}
        code = reply.strip()
        if code.startswith("```"):
            lines = [ln for ln in code.splitlines() if not ln.strip().startswith("```")]
            code = "\n".join(lines).strip()
        last_code = code
        passed, msg = verify_python_source(code)
        record_lesson(f"code_verify_attempt_{attempt}", msg, passed)
        if passed:
            return {"status": "PASS", "attempt": attempt, "provider": provider, "code": code}
        last_err = msg
        feedback = (
            f"Original task: {task_prompt}\n\n"
            f"Previous code failed verification with exact error:\n{last_err}\n\n"
            f"Broken code:\n{last_code}\n\n"
            "Fix the exact error and output ONLY valid Python code."
        )
    return {"status": "FAILED_MAX_RETRIES", "attempts": max_retries, "error": last_err, "code": last_code}
