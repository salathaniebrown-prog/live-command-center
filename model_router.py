#!/usr/bin/env python3
"""
Local Pool + Failover + Diagnostics + Raw/Open-Weights Router.
Supports Gemma 4 31B default, reusable system prefix caching, JSON-schema outputs,
vision/image content blocks, and live web search context.
"""
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

DEFAULT_POOL_MODEL = sys.intern(os.environ.get("ASTRA_POOL_MODEL", "models/gemma-4-31b-it"))
DEFAULT_SYSTEM_PREFIX = sys.intern(
    os.environ.get(
        "ASTRA_SYSTEM_PREFIX",
        "You are an engineering and systems collaborator for Astra Command Center. Be concise, technical, and deterministic.",
    )
)
POOL_TIMEOUT_SEC = float(os.environ.get("ASTRA_POOL_TIMEOUT", "25.0"))
WEB_SEARCH_TIMEOUT_SEC = float(os.environ.get("ASTRA_WEB_SEARCH_TIMEOUT", "6.0"))
_DEFAULT_URLS = os.environ.get(
    "ASTRA_MODEL_POOL",
    "http://192.168.1.68:12434,http://127.0.0.1:11434",
)


def _build_response_format(json_schema: dict | None, response_format: dict | None) -> dict | None:
    if isinstance(response_format, dict) and response_format:
        return response_format
    if isinstance(json_schema, dict) and json_schema:
        schema_name = str(json_schema.get("name") or "astra_structured_output")
        schema_body = json_schema.get("schema") if isinstance(json_schema.get("schema"), dict) else json_schema
        strict_flag = bool(json_schema.get("strict", True))
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": strict_flag,
                "schema": schema_body,
            },
        }
    return None


def _normalize_image_url(item) -> str | None:
    if isinstance(item, dict):
        if isinstance(item.get("image_url"), dict):
            u = item["image_url"].get("url")
            return str(u).strip() if u else None
        for k in ("url", "image_url", "data_url", "base64"):
            if item.get(k):
                val = str(item[k]).strip()
                if k == "base64" and not val.startswith("data:"):
                    return f"data:image/jpeg;base64,{val}"
                return val
        return None
    if isinstance(item, str):
        s = item.strip()
        if not s:
            return None
        if s.startswith(("http://", "https://", "data:image/")):
            return s
        return f"data:image/jpeg;base64,{s}"
    return None


def _extract_images(payload: dict) -> list[str]:
    out: list[str] = []
    if payload.get("image_url"):
        u = _normalize_image_url(payload["image_url"])
        if u:
            out.append(u)
    raw_imgs = payload.get("images")
    if isinstance(raw_imgs, list):
        for entry in raw_imgs:
            u = _normalize_image_url(entry)
            if u:
                out.append(u)
    return out


def _ddg_html_search(q: str, limit: int) -> list[dict]:
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=WEB_SEARCH_TIMEOUT_SEC) as resp:
        raw_html = resp.read().decode("utf-8", errors="ignore")

    link_matches = re.findall(
        r'<a[^>]*class="[^"]*result__(?:a|title-link)[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        raw_html,
        flags=re.S | re.I,
    )
    if not link_matches:
        link_matches = re.findall(
            r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            raw_html,
            flags=re.S | re.I,
        )
        link_matches = [
            (h, t) for (h, t) in link_matches
            if "duckduckgo.com" not in urllib.parse.urlparse(h).netloc.lower()
        ]

    snip_matches = re.findall(
        r'<(?:a|div|td|span)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div|td|span)>',
        raw_html,
        flags=re.S | re.I,
    )
    out = []
    seen = set()
    for href, title_html in link_matches:
        clean_href = html.unescape(href).strip()
        if "uddg=" in clean_href:
            parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(clean_href).query)
            if parsed_q.get("uddg"):
                clean_href = parsed_q["uddg"][0]
        if not clean_href.startswith(("http://", "https://")) or clean_href in seen:
            continue
        seen.add(clean_href)
        clean_title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(title_html))).strip()
        if not clean_title:
            continue
        snippet = ""
        if len(out) < len(snip_matches):
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(snip_matches[len(out)]))).strip()
        out.append({"title": clean_title, "url": clean_href, "snippet": snippet, "source": "ddg_html"})
        if len(out) >= limit:
            break
    return out


def _ddg_instant_search(q: str, limit: int) -> list[dict]:
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote_plus(q)}&format=json&no_html=1&skip_disambig=1"
    req = urllib.request.Request(url, headers={"User-Agent": "AstraCommandCenter/1.0"}, method="GET")
    with urllib.request.urlopen(req, timeout=WEB_SEARCH_TIMEOUT_SEC) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
    out = []
    if data.get("AbstractText") and data.get("AbstractURL"):
        out.append({
            "title": data.get("Heading") or q,
            "url": data["AbstractURL"],
            "snippet": data["AbstractText"],
            "source": "ddg_instant",
        })
    for topic in (data.get("RelatedTopics") or []):
        if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
            out.append({
                "title": topic.get("Text", "").split(" - ")[0][:90],
                "url": topic["FirstURL"],
                "snippet": topic["Text"],
                "source": "ddg_instant",
            })
            if len(out) >= limit:
                break
    return out[:limit]


def _wiki_opensearch(q: str, limit: int) -> list[dict]:
    url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote_plus(q)}&limit={limit}&namespace=0&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "AstraCommandCenter/1.0"}, method="GET")
    with urllib.request.urlopen(req, timeout=WEB_SEARCH_TIMEOUT_SEC) as resp:
        arr = json.loads(resp.read().decode("utf-8", errors="ignore") or "[]")
    out = []
    if isinstance(arr, list) and len(arr) >= 4:
        titles, descs, urls = arr[1], arr[2], arr[3]
        for i in range(min(len(titles), len(urls), limit)):
            out.append({
                "title": str(titles[i]),
                "url": str(urls[i]),
                "snippet": str(descs[i] if i < len(descs) else ""),
                "source": "wikipedia",
            })
    return out


def web_search(query: str, max_results: int = 5) -> dict:
    q = (query or "").strip()
    limit = max(1, min(int(max_results or 5), 10))
    if not q:
        return {"ok": False, "query": q, "results": [], "error": "empty_query"}

    t0 = time.monotonic()
    results: list[dict] = []
    errors: list[str] = []
    for fn in (_ddg_html_search, _ddg_instant_search, _wiki_opensearch):
        try:
            hits = fn(q, limit)
            if hits:
                results = hits
                break
        except Exception as exc:
            errors.append(f"{fn.__name__}:{exc}")

    return {
        "ok": len(results) > 0,
        "query": q,
        "results": results,
        "errors": errors,
        "latency_ms": round((time.monotonic() - t0) * 1000.0, 1),
    }


def _format_search_context(search_res: dict) -> str:
    if not search_res.get("ok") or not search_res.get("results"):
        return ""
    lines = [f"[LIVE WEB SEARCH :: {search_res.get('query', '')}]"]
    for i, r in enumerate(search_res["results"], 1):
        lines.append(f"{i}. {r.get('title','')} — {r.get('url','')}\n   {r.get('snippet','')}")
    return "\n".join(lines)


class LocalPoolOrchestrator:
    __slots__ = (
        "endpoints",
        "active_idx",
        "failover_enabled",
        "developer_mode",
        "raw_mode",
        "system_prefix",
        "bind_host",
        "evidence",
        "lock",
    )

    def __init__(self, urls_csv: str = _DEFAULT_URLS):
        raw_list = [u.strip().rstrip("/") for u in (urls_csv or "").split(",") if u.strip()]
        self.endpoints = tuple(sys.intern(u) for u in (raw_list or ["http://127.0.0.1:11434"]))
        self.active_idx = 0
        self.failover_enabled = True
        self.developer_mode = True
        self.raw_mode = True
        self.system_prefix = sys.intern(DEFAULT_SYSTEM_PREFIX)
        self.bind_host = sys.intern(os.environ.get("ASTRA_POOL_BIND", "127.0.0.1"))
        self.evidence = deque(maxlen=32)
        self.lock = threading.Lock()

    def _probe_url(self, base_url: str, timeout: float = 0.6) -> dict:
        t0 = time.monotonic()
        for path in ("/api/tags", "/v1/models", "/health"):
            try:
                req = urllib.request.Request(f"{base_url}{path}", method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    ms = round((time.monotonic() - t0) * 1000.0, 1)
                    return {"url": base_url, "online": resp.status < 500, "probe_path": path, "latency_ms": ms}
            except Exception:
                continue
        ms = round((time.monotonic() - t0) * 1000.0, 1)
        return {"url": base_url, "online": False, "probe_path": None, "latency_ms": ms}

    def status(self, probe: bool = True) -> dict:
        with self.lock:
            providers = [self._probe_url(u) if probe else {"url": u, "online": None} for u in self.endpoints]
            active_url = self.endpoints[self.active_idx % len(self.endpoints)]
            return {
                "ok": True,
                "orchestrator": "Local Pool",
                "default_model": DEFAULT_POOL_MODEL,
                "active_provider": active_url,
                "providers": providers,
                "failover": self.failover_enabled,
                "developer_mode": self.developer_mode,
                "raw_mode": self.raw_mode,
                "system_prefix": self.system_prefix,
                "capabilities": ["vision_images", "json_schema", "system_prefix", "web_search"],
                "bind_host": self.bind_host,
                "evidence_count": len(self.evidence),
                "recent_evidence": list(self.evidence)[-8:] if self.developer_mode else [],
            }

    def configure(self, cfg: dict) -> dict:
        with self.lock:
            if "failover" in cfg:
                self.failover_enabled = bool(cfg["failover"])
            if "developer_mode" in cfg:
                self.developer_mode = bool(cfg["developer_mode"])
            if "raw_mode" in cfg:
                self.raw_mode = bool(cfg["raw_mode"])
            if isinstance(cfg.get("system_prefix"), str):
                self.system_prefix = sys.intern(cfg["system_prefix"])
            if isinstance(cfg.get("bind_host"), str) and cfg["bind_host"].strip():
                self.bind_host = sys.intern(cfg["bind_host"].strip())
            if isinstance(cfg.get("providers"), list) and cfg["providers"]:
                cleaned = [sys.intern(str(u).strip().rstrip("/")) for u in cfg["providers"] if str(u).strip()]
                if cleaned:
                    self.endpoints = tuple(cleaned)
                    self.active_idx = 0
            if isinstance(cfg.get("active_provider"), str):
                target = cfg["active_provider"].strip().rstrip("/")
                if target in self.endpoints:
                    self.active_idx = self.endpoints.index(target)
        return self.status(probe=False)

    def _call_provider(
        self,
        base_url: str,
        prompt: str,
        model: str | None,
        system_prompt: str | None,
        system_prefix: str | None = None,
        response_format: dict | None = None,
        use_system: bool = False,
        images: list[str] | None = None,
        search_context: str = "",
    ) -> tuple[bool, dict]:
        t0 = time.monotonic()
        chosen_model = model or DEFAULT_POOL_MODEL
        img_list = images or []

        prefix_part = (system_prefix if system_prefix is not None else self.system_prefix) or ""
        extra_sys = system_prompt or ""
        combined_system = "\n\n".join(p for p in (prefix_part.strip(), extra_sys.strip()) if p)

        effective_prompt = prompt
        if search_context:
            effective_prompt = f"{prompt}\n\n{search_context}".strip()

        if img_list:
            user_content = [{"type": "text", "text": effective_prompt}] + [
                {"type": "image_url", "image_url": {"url": u}} for u in img_list
            ]
        else:
            user_content = effective_prompt

        msgs = []
        if combined_system and (use_system or not self.raw_mode):
            msgs.append({"role": "system", "content": combined_system})
        msgs.append({"role": "user", "content": user_content})

        oai_payload = {"model": chosen_model, "messages": msgs, "stream": False}
        if response_format:
            oai_payload["response_format"] = response_format

        last_err = None
        skip_ollama_fallback = False
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    f"{base_url}/v1/chat/completions",
                    data=json.dumps(oai_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=POOL_TIMEOUT_SEC) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
                    choice = ((data.get("choices") or [{}])[0]).get("message") or {}
                    return True, {
                        "provider": base_url,
                        "api": "/v1/chat/completions",
                        "model": data.get("model") or chosen_model,
                        "schema_enforced": bool(response_format),
                        "images_attached": len(img_list),
                        "web_search_used": bool(search_context),
                        "response": choice.get("content", ""),
                        "latency_ms": round((time.monotonic() - t0) * 1000.0, 1),
                    }
            except urllib.error.HTTPError as he:
                last_err = f"oai_http_{he.code}"
                if he.code in (404, 429, 500, 502, 503, 504):
                    skip_ollama_fallback = True
                if he.code in (429, 502, 503) and attempt == 0:
                    time.sleep(0.35)
                    continue
                break
            except Exception as e_oai:
                last_err = f"oai={e_oai}"
                if "timed out" in str(e_oai).lower():
                    skip_ollama_fallback = True
                break

        if skip_ollama_fallback:
            return False, {
                "provider": base_url,
                "model": chosen_model,
                "error": str(last_err),
                "latency_ms": round((time.monotonic() - t0) * 1000.0, 1),
            }

        gen_payload = {"model": chosen_model, "prompt": effective_prompt, "stream": False}
        if combined_system and (use_system or not self.raw_mode):
            gen_payload["system"] = combined_system
        if response_format and isinstance(response_format.get("json_schema"), dict):
            gen_payload["format"] = response_format["json_schema"].get("schema") or "json"
        try:
            req = urllib.request.Request(
                f"{base_url}/api/generate",
                data=json.dumps(gen_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=POOL_TIMEOUT_SEC) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
                return True, {
                    "provider": base_url,
                    "api": "/api/generate",
                    "model": data.get("model") or chosen_model,
                    "schema_enforced": bool(response_format),
                    "images_attached": len(img_list),
                    "web_search_used": bool(search_context),
                    "response": data.get("response", ""),
                    "latency_ms": round((time.monotonic() - t0) * 1000.0, 1),
                }
        except Exception as e_ollama:
            return False, {
                "provider": base_url,
                "model": chosen_model,
                "error": f"{last_err} | ollama={e_ollama}",
                "latency_ms": round((time.monotonic() - t0) * 1000.0, 1),
            }

    def route_prompt(
        self,
        prompt: str,
        model: str | None = None,
        system_prompt: str | None = None,
        system_prefix: str | None = None,
        json_schema: dict | None = None,
        response_format: dict | None = None,
        use_system: bool = False,
        images: list[str] | None = None,
        enable_web_search: bool = False,
        search_query: str | None = None,
    ) -> dict:
        fmt = _build_response_format(json_schema, response_format)
        effective_use_system = bool(use_system or system_prefix is not None or system_prompt is not None)
        img_list = images or []

        search_meta = None
        search_ctx = ""
        if enable_web_search or (search_query and search_query.strip()):
            q = (search_query or prompt).strip()
            search_meta = web_search(q, max_results=5)
            search_ctx = _format_search_context(search_meta)

        with self.lock:
            order = list(range(len(self.endpoints)))
            start = self.active_idx % len(self.endpoints)
            ordered_urls = [self.endpoints[(start + i) % len(self.endpoints)] for i in order]
            if not self.failover_enabled:
                ordered_urls = [ordered_urls[0]]

        attempts = []
        for idx, url in enumerate(ordered_urls):
            ok, res = self._call_provider(
                url,
                prompt,
                model,
                system_prompt,
                system_prefix=system_prefix,
                response_format=fmt,
                use_system=effective_use_system,
                images=img_list,
                search_context=search_ctx,
            )
            attempts.append(res)
            if ok:
                with self.lock:
                    self.active_idx = self.endpoints.index(url)
                    rec = {
                        "ts": time.time(),
                        "provider": url,
                        "api": res.get("api"),
                        "model": res.get("model"),
                        "schema_enforced": bool(fmt),
                        "images_attached": len(img_list),
                        "web_search_used": bool(search_ctx),
                        "latency_ms": res.get("latency_ms"),
                        "raw_mode": self.raw_mode,
                        "failover_used": idx > 0,
                    }
                    self.evidence.append(rec)
                out = {"ok": True, "routed": res, "attempts": attempts, "evidence": rec}
                if search_meta is not None:
                    out["web_search"] = search_meta
                return out

        with self.lock:
            rec = {
                "ts": time.time(),
                "status": "NO_PROVIDER_REACHABLE",
                "model": model or DEFAULT_POOL_MODEL,
                "schema_enforced": bool(fmt),
                "images_attached": len(img_list),
                "web_search_used": bool(search_ctx),
                "raw_mode": self.raw_mode,
                "attempts": len(attempts),
            }
            self.evidence.append(rec)
        out = {
            "ok": False,
            "status": "OFFLINE_POOL",
            "message": "No local/LAN provider responded; start Ollama/SGLang/MLX or pass a reachable provider URL.",
            "attempts": attempts,
            "evidence": rec,
        }
        if search_meta is not None:
            out["web_search"] = search_meta
        return out


_POOL = LocalPoolOrchestrator()


def get_pool_status(probe: bool = True) -> dict:
    return _POOL.status(probe=probe)


def configure_pool(cfg: dict) -> dict:
    return _POOL.configure(cfg or {})



AGENT_ROLES = {
    "coder": "You write clean, production-ready Python, Go, Node.js, and Bash scripts with explicit error handling.",
    "reviewer": "You audit code for security flaws, resource/socket/memory leaks, and edge cases. Do not modify files.",
    "architect": "You design resilient multi-node systems, telemetry pipelines, and SQLite/data schemas.",
}


def handle_agent_slash_command(prompt_text: str, state: dict | None = None) -> dict | None:
    s = state if isinstance(state, dict) else {"active_agent": "coder"}
    active = str(s.get("active_agent") or "coder").lower()
    if active not in AGENT_ROLES:
        active = "coder"
    raw = (prompt_text or "").strip()

    if raw == "/agents":
        s["active_agent"] = active
        return {
            "ok": True,
            "slash_command": "/agents",
            "active_agent": active,
            "available_agents": list(AGENT_ROLES.keys()),
            "routed": {
                "provider": "local_router",
                "api": "slash:/agents",
                "model": DEFAULT_POOL_MODEL,
                "response": f"[System] Available agents: {', '.join(AGENT_ROLES.keys())} (Active: {active})",
                "latency_ms": 0.1,
            },
        }

    if raw.startswith("/switch "):
        target = raw.split(" ", 1)[1].strip().lower()
        if target not in AGENT_ROLES:
            return {
                "ok": False,
                "slash_command": "/switch",
                "active_agent": active,
                "error": f"Unknown agent '{target}'. Available: {', '.join(AGENT_ROLES.keys())}",
            }
        s["active_agent"] = target
        return {
            "ok": True,
            "slash_command": "/switch",
            "active_agent": target,
            "role_prompt": AGENT_ROLES[target],
            "routed": {
                "provider": "local_router",
                "api": "slash:/switch",
                "model": DEFAULT_POOL_MODEL,
                "response": f"[System] Switched active agent to '{target}'.",
                "latency_ms": 0.1,
            },
        }

    return None


_AGENT_STATE = {"active_agent": "coder"}


def route_chat(payload: dict) -> dict:
    p = payload or {}
    prompt = str(p.get("prompt") or p.get("message") or "")
    req_agent = str(p.get("agent") or "").strip().lower()
    if req_agent in AGENT_ROLES:
        _AGENT_STATE["active_agent"] = req_agent

    slash_out = handle_agent_slash_command(prompt, _AGENT_STATE)
    if slash_out is not None:
        return slash_out

    active_role = _AGENT_STATE.get("active_agent", "coder")
    role_system = AGENT_ROLES.get(active_role, "")
    model = p.get("model")
    base_sys = str(p.get("system") or "").strip()
    system_prompt = "\n\n".join(x for x in (role_system, base_sys) if x) or None
    system_prefix = p.get("system_prefix")
    json_schema = p.get("json_schema")
    response_format = p.get("response_format")
    use_system = bool(p.get("use_system", False))
    images = _extract_images(p)
    enable_web_search = bool(p.get("web_search", False))
    search_query = p.get("search_query")
    return _POOL.route_prompt(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        system_prefix=system_prefix,
        json_schema=json_schema,
        response_format=response_format,
        use_system=use_system,
        images=images,
        enable_web_search=enable_web_search,
        search_query=search_query,
    )


def handle_pool_get(handler, req_path: str) -> bool:
    if req_path not in ("/api/pool/status", "/api/pool/evidence"):
        return False
    body = json.dumps(get_pool_status(probe=(req_path == "/api/pool/status")), separators=(",", ":")).encode("utf-8")
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass
    return True


def handle_pool_post(handler, req_path: str, raw_body: bytes) -> bool:
    if req_path not in ("/api/pool/config", "/api/pool/route", "/api/pool/search"):
        return False
    try:
        data = json.loads((raw_body or b"{}").decode("utf-8", errors="ignore") or "{}")
    except Exception:
        data = {}
    if req_path == "/api/pool/config":
        out = configure_pool(data)
    elif req_path == "/api/pool/search":
        q = str(data.get("query") or data.get("prompt") or "")
        out = web_search(q, max_results=int(data.get("max_results") or 5))
    else:
        out = route_chat(data)
    body = json.dumps(out, separators=(",", ":")).encode("utf-8")
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass
    return True


if __name__ == "__main__":
    print(json.dumps(get_pool_status(probe=False), indent=2))
