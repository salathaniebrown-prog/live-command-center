#!/usr/bin/env python3
"""
Local Pool + Failover + Diagnostics + Raw/Open-Weights Router.
Supports Gemma 4 31B default, reusable system prefix caching, and JSON-schema outputs.
"""
import json
import os
import sys
import threading
import time
import urllib.error
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
    ) -> tuple[bool, dict]:
        t0 = time.monotonic()
        chosen_model = model or DEFAULT_POOL_MODEL

        prefix_part = (system_prefix if system_prefix is not None else self.system_prefix) or ""
        extra_sys = system_prompt or ""
        combined_system = "\n\n".join(p for p in (prefix_part.strip(), extra_sys.strip()) if p)

        msgs = []
        if combined_system and (use_system or not self.raw_mode):
            msgs.append({"role": "system", "content": combined_system})
        msgs.append({"role": "user", "content": prompt})

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

        gen_payload = {"model": chosen_model, "prompt": prompt, "stream": False}
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
    ) -> dict:
        fmt = _build_response_format(json_schema, response_format)
        effective_use_system = bool(use_system or system_prefix is not None or system_prompt is not None)
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
                        "latency_ms": res.get("latency_ms"),
                        "raw_mode": self.raw_mode,
                        "failover_used": idx > 0,
                    }
                    self.evidence.append(rec)
                return {"ok": True, "routed": res, "attempts": attempts, "evidence": rec}

        with self.lock:
            rec = {
                "ts": time.time(),
                "status": "NO_PROVIDER_REACHABLE",
                "model": model or DEFAULT_POOL_MODEL,
                "schema_enforced": bool(fmt),
                "raw_mode": self.raw_mode,
                "attempts": len(attempts),
            }
            self.evidence.append(rec)
        return {
            "ok": False,
            "status": "OFFLINE_POOL",
            "message": "No local/LAN provider responded; start Ollama/SGLang/MLX or pass a reachable provider URL.",
            "attempts": attempts,
            "evidence": rec,
        }


_POOL = LocalPoolOrchestrator()


def get_pool_status(probe: bool = True) -> dict:
    return _POOL.status(probe=probe)


def configure_pool(cfg: dict) -> dict:
    return _POOL.configure(cfg or {})


def route_chat(payload: dict) -> dict:
    p = payload or {}
    prompt = str(p.get("prompt") or p.get("message") or "")
    model = p.get("model")
    system_prompt = p.get("system")
    system_prefix = p.get("system_prefix")
    json_schema = p.get("json_schema")
    response_format = p.get("response_format")
    use_system = bool(p.get("use_system", False))
    return _POOL.route_prompt(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        system_prefix=system_prefix,
        json_schema=json_schema,
        response_format=response_format,
        use_system=use_system,
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
    if req_path not in ("/api/pool/config", "/api/pool/route"):
        return False
    try:
        data = json.loads((raw_body or b"{}").decode("utf-8", errors="ignore") or "{}")
    except Exception:
        data = {}
    out = configure_pool(data) if req_path == "/api/pool/config" else route_chat(data)
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
