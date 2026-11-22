#!/usr/bin/env python3
"""
Salathanie A.I — Zero-Dependency Multi-Provider LLM Bridge
Supports Gemini API, OpenAI API, or Local Edge OpenAI-compatible endpoints
with automatic offline fallback. Secrets live outside Git in ~/.salathanie_llm.json (0600).
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

CFG_PATH = Path.home() / ".salathanie_llm.json"

SYSTEM_PROMPTS = {
    "devexa_ceo_seo": "You are Devexa, an elite CEO strategist, trading executive, and technical SEO architect. Be sharp, concrete, and concise.",
    "virtual_dev": "You are a Staff Software Engineer. Output clean, production-ready architecture notes and minimal bug-free code.",
    "uxui_designer": "You are a Principal UX/UI Designer. Provide high-contrast mobile-first design specs and component hierarchy.",
    "aiml_dev": "You are a Principal Edge AI/ML Engineer specializing in Android/Termux, quantization, and telemetry pipelines.",
    "ebook_builder": "Extract actionable software architecture modules and MVP milestones from this ebook content.",
    "copy_jasper": "Write punchy, high-conversion marketing copy with headline, hook, and CTA.",
    "notion_ai": "Convert this note into concise code structure, visual prompt, and 3-scene short video script.",
    "claude_doc": "Produce an executive summary and 3-5 crisp bullet takeaways.",
    "grammarly": "Rewrite for maximum clarity, authority, and zero filler words. Return only the improved text and 2 brief notes.",
    "perplexity_pro": "Synthesize key technical facts, actionable next steps, and edge-device integration tips.",
    "tome_pitch": "Draft a tight 4-slide investor pitch outline with concrete numbers/milestones.",
    "durable_web": "Draft crisp landing page copy (hero, 3 value props, CTA) for this local small business.",
}


def load_cfg() -> dict:
    cfg = {}
    if CFG_PATH.exists():
        try:
            cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    # Environment variables take precedence
    if os.getenv("GEMINI_API_KEY"):
        cfg["provider"] = "gemini"
        cfg["gemini_key"] = os.getenv("GEMINI_API_KEY")
        cfg["gemini_model"] = os.getenv("GEMINI_MODEL", cfg.get("gemini_model", "gemini-2.5-flash"))
    elif os.getenv("OPENAI_API_KEY"):
        cfg["provider"] = "openai"
        cfg["openai_key"] = os.getenv("OPENAI_API_KEY")
        cfg["openai_model"] = os.getenv("OPENAI_MODEL", cfg.get("openai_model", "gpt-4o-mini"))
    elif os.getenv("LOCAL_LLM_URL"):
        cfg["provider"] = "local"
        cfg["local_url"] = os.getenv("LOCAL_LLM_URL")
        cfg["local_model"] = os.getenv("LOCAL_LLM_MODEL", cfg.get("local_model", "local-edge"))
    return cfg


def save_cfg(updates: dict):
    cfg = load_cfg()
    cfg.update({k: v for k, v in updates.items() if v is not None})
    fd = os.open(str(CFG_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(cfg, indent=2).encode("utf-8"))
    finally:
        os.close(fd)


def llm_status() -> dict:
    cfg = load_cfg()
    prov = cfg.get("provider", "offline_stdlib")
    configured = (
        (prov == "gemini" and bool(cfg.get("gemini_key")))
        or (prov == "openai" and bool(cfg.get("openai_key")))
        or (prov == "local" and bool(cfg.get("local_url")))
    )
    return {
        "provider": prov if configured else "offline_stdlib",
        "configured": configured,
        "model": cfg.get(f"{prov}_model", "stdlib-deterministic") if configured else "stdlib-deterministic",
        "config_file": str(CFG_PATH),
    }


def _call_gemini(key: str, model: str, sys_prompt: str, user_text: str, timeout: float = 8.0) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_text[:3000]}]}],
        "generationConfig": {"maxOutputTokens": 450, "temperature": 0.4},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _call_openai_compat(base_url: str, key: str, model: str, sys_prompt: str, user_text: str, timeout: float = 8.0) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_text[:3000]},
        ],
        "max_tokens": 450,
        "temperature": 0.4,
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def enhance_with_llm(agent: str, user_text: str, base_out: dict) -> dict:
    cfg = load_cfg()
    prov = cfg.get("provider", "offline_stdlib")
    sys_prompt = SYSTEM_PROMPTS.get(agent, f"You are the {agent} specialist inside Salathanie A.I. Respond concisely.")
    t0 = time.perf_counter()

    try:
        if prov == "gemini" and cfg.get("gemini_key"):
            model = cfg.get("gemini_model", "gemini-2.5-flash")
            reply = _call_gemini(cfg["gemini_key"], model, sys_prompt, user_text)
        elif prov == "openai" and cfg.get("openai_key"):
            model = cfg.get("openai_model", "gpt-4o-mini")
            base = cfg.get("openai_base_url", "https://api.openai.com/v1")
            reply = _call_openai_compat(base, cfg["openai_key"], model, sys_prompt, user_text)
        elif prov == "local" and cfg.get("local_url"):
            model = cfg.get("local_model", "local-edge")
            reply = _call_openai_compat(cfg["local_url"], cfg.get("local_key", ""), model, sys_prompt, user_text)
        else:
            base_out["llm_backend"] = "offline_stdlib"
            return base_out

        base_out["llm_backend"] = prov
        base_out["llm_model"] = model
        base_out["llm_latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        base_out["llm_response"] = reply
    except Exception as e:
        base_out["llm_backend"] = "offline_stdlib_fallback"
        base_out["llm_error"] = str(e)[:140]
    return base_out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Configure Salathanie A.I LLM Bridge")
    p.add_argument("--provider", choices=["gemini", "openai", "local", "offline"])
    p.add_argument("--key", help="API key for Gemini or OpenAI")
    p.add_argument("--model", help="Model name (e.g. gemini-2.5-flash, gpt-4o-mini)")
    p.add_argument("--url", help="Base URL for local OpenAI-compatible server (e.g. http://127.0.0.1:11434/v1)")
    p.add_argument("--test", help="Send a quick test prompt")
    args = p.parse_args()

    if args.provider == "offline":
        save_cfg({"provider": "offline_stdlib"})
    elif args.provider == "gemini":
        save_cfg({"provider": "gemini", "gemini_key": args.key, "gemini_model": args.model or "gemini-2.5-flash"})
    elif args.provider == "openai":
        save_cfg({"provider": "openai", "openai_key": args.key, "openai_model": args.model or "gpt-4o-mini"})
    elif args.provider == "local":
        save_cfg({"provider": "local", "local_url": args.url or "http://127.0.0.1:11434/v1", "local_model": args.model or "local-edge"})

    print(json.dumps(llm_status(), indent=2))
    if args.test:
        print(json.dumps(enhance_with_llm("devexa_ceo_seo", args.test, {"ok": True}), indent=2))
