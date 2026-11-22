#!/usr/bin/env python3
"""
SalathanieAI — OpenAI-Compatible /v1/chat/completions & /v1/models Engine
Fuses live Greensboro (KGSO) atmospheric vectors, SQLite WAL flight ledger telemetry,
Offline Wikipedia RAG, and live [EXEC] multi-agent control directives.
Additive-only: zero extra PM2 processes (mounted inside universal_pilot.py :8125).
"""
import json
import re
import time
import urllib.request
import uuid

import astra_alstra_jet_bridge as bridge
import astra_flight_ledger as ledger
import astra_memory_spine as spine
from hdc_shm_bus import HDCSharedMemoryBus, deterministic_hv

KGSO_URL = "https://api.weather.gov/stations/KGSO/observations/latest"
_KGSO_CACHE = {"ts": 0.0, "data": None}
_NEURAL_STATS = {
    "v1_requests": 0,
    "exec_runs": 0,
    "last_ts": 0,
    "last_action": "STANDBY",
    "last_score": 0.0,
    "last_exec": [],
    "last_prompt": "",
}

VALID_MODES = {"AUTONOMOUS-MUTATE", "TURBULENCE-LOCK", "THERMAL-DERATE", "CRUISE-VECTOR"}
POD_INDEX = {"L1": 0, "SAR": 0, "R1": 1, "RF": 1, "L2": 2, "OPTIC": 2, "R2": 3, "AUX": 3}


def fetch_kgso_atmos(force: bool = False) -> dict:
    """Fetch live Greensboro (KGSO) NWS observation with 120s TTL cache and safe offline fallback."""
    now = time.time()
    if not force and _KGSO_CACHE["data"] and (now - _KGSO_CACHE["ts"]) < 120.0:
        return dict(_KGSO_CACHE["data"])

    fallback = {
        "station": "KGSO",
        "city": "Greensboro, NC",
        "source": "offline_cached_baseline",
        "temp_c": 14.0,
        "wind_kmh": 9.5,
        "wind_deg": 240,
        "pressure_hpa": 1016.2,
        "humidity_pct": 62.0,
        "condition": "Offline Nominal",
        "wind_turbulence_factor": 0.12,
        "ts": int(now),
    }

    try:
        req = urllib.request.Request(
            KGSO_URL,
            headers={
                "User-Agent": "SalathanieAI-V1-Shim/4.1 (PiedmontTriadNC)",
                "Accept": "application/geo+json, application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=4.5) as r:
            raw = json.loads(r.read().decode("utf-8", errors="ignore"))
        props = raw.get("properties") or {}

        def _val(key, default, scale=1.0):
            obj = props.get(key)
            if isinstance(obj, dict) and obj.get("value") is not None:
                try:
                    return round(float(obj["value"]) * scale, 2)
                except (TypeError, ValueError):
                    return default
            return default

        temp_c = _val("temperature", fallback["temp_c"])
        wind_kmh = _val("windSpeed", fallback["wind_kmh"])
        wind_deg = int(_val("windDirection", fallback["wind_deg"]))
        pressure_hpa = _val("barometricPressure", fallback["pressure_hpa"], scale=0.01)
        humidity = _val("relativeHumidity", fallback["humidity_pct"])
        cond = str(props.get("textDescription") or "Clear").strip() or "Clear"
        turb_factor = round(min(1.0, max(0.05, wind_kmh / 55.0)), 3)

        obs = {
            "station": "KGSO",
            "city": "Greensboro, NC",
            "source": "nws_live_kgso",
            "temp_c": temp_c,
            "wind_kmh": wind_kmh,
            "wind_deg": wind_deg,
            "pressure_hpa": pressure_hpa,
            "humidity_pct": humidity,
            "condition": cond,
            "wind_turbulence_factor": turb_factor,
            "ts": int(now),
        }
        _KGSO_CACHE["ts"] = now
        _KGSO_CACHE["data"] = obs
        return dict(obs)
    except Exception:
        if _KGSO_CACHE["data"]:
            return dict(_KGSO_CACHE["data"])
        return fallback


def _post_local(url: str, payload: dict):
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4.0) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore") or "{}")
    except Exception:
        return None


def run_exec_directives(prompt: str) -> list[dict]:
    """Execute inline [EXEC:...] directives for mode switches, pod toggles, memory recall, snapshots, and mutation."""
    actions = []
    tags = re.findall(r"\[EXEC(?::([^\]]+))?\]", prompt, flags=re.IGNORECASE)
    if not tags:
        return actions

    st = ledger.read_state_safe()
    pods = st.get("pods") if isinstance(st.get("pods"), list) and len(st["pods"]) == 4 else [True, True, True, True]

    for raw_tag in tags:
        cmd = (raw_tag or "").strip().upper()
        if not cmd:
            up = prompt.upper()
            if "MEMORY" in up or "RECALL" in up:
                cmd = "MEMORY"
            elif "MUTATE" in up:
                cmd = "MUTATE"
            elif "SNAPSHOT" in up:
                cmd = "SNAPSHOT"
            else:
                for m in VALID_MODES:
                    if m in up:
                        cmd = f"MODE={m}"
                        break

        if cmd.startswith("MODE="):
            mode = cmd.split("=", 1)[1].strip()
            if mode in VALID_MODES:
                ledger.atomic_write_state({"model": "SalathanieAI", "mode": mode}, preserve_overrides=False)
                _post_local("http://127.0.0.1:8125/api/mode", {"mode": mode})
                actions.append({"directive": cmd, "ok": True, "result": f"mode_switched:{mode}"})
            else:
                actions.append({"directive": cmd, "ok": False, "result": f"invalid_mode:{mode}"})

        elif cmd.startswith("PODS="):
            mask = cmd.split("=", 1)[1].strip()
            if re.fullmatch(r"[01]{4}", mask):
                pods = [ch == "1" for ch in mask]
                ledger.atomic_write_state({"pods": pods}, preserve_overrides=False)
                _post_local("http://127.0.0.1:8125/api/pods", {"pods": pods})
                actions.append({"directive": cmd, "ok": True, "result": f"pods_set:{mask}"})
            else:
                actions.append({"directive": cmd, "ok": False, "result": "expected_4bit_mask"})

        elif cmd.startswith("POD="):
            spec = cmd.split("=", 1)[1].strip()
            parts = re.split(r"[:=]", spec)
            if len(parts) == 2 and parts[0] in POD_INDEX:
                idx = POD_INDEX[parts[0]]
                val = parts[1] in ("1", "ON", "TRUE", "UP")
                pods[idx] = val
                ledger.atomic_write_state({"pods": pods}, preserve_overrides=False)
                _post_local("http://127.0.0.1:8125/api/pods", {"pods": pods})
                mask = "".join("1" if b else "0" for b in pods)
                actions.append({"directive": cmd, "ok": True, "result": f"pod_{parts[0]}={'ON' if val else 'OFF'} mask={mask}"})
            else:
                actions.append({"directive": cmd, "ok": False, "result": f"invalid_pod:{spec}"})

        elif cmd in ("MEMORY", "RECALL"):
            ms = spine.spine_status()
            actions.append({
                "directive": cmd,
                "ok": True,
                "result": {
                    "db_kb": ms.get("db_kb"),
                    "totals": ms.get("totals"),
                    "boot_hook": ms.get("boot_hook_installed"),
                    "latest_event": (ms.get("recent_events") or [{}])[0].get("type", "NONE"),
                },
            })

        elif cmd == "SNAPSHOT":
            sn = spine.take_snapshot(reason="v1_exec", save_pm2_dump=False)
            actions.append({"directive": cmd, "ok": sn.get("ok", False), "result": {"hmac_sig": sn.get("hmac_sig"), "services": sn.get("services")}})

        elif cmd == "MUTATE":
            cyc = bridge.run_closed_loop_cycle(force_external_sync=False)
            actions.append({"directive": cmd, "ok": True, "result": {"gen_id": cyc.get("gen_id"), "fitness": cyc.get("new_fitness"), "promoted": cyc.get("promoted")}})

        else:
            actions.append({"directive": cmd or "EMPTY", "ok": False, "result": "unrecognized_exec_directive"})

    if actions:
        _NEURAL_STATS["exec_runs"] += len(actions)
        _NEURAL_STATS["last_exec"] = actions[-3:]
    return actions


def handle_v1_models() -> dict:
    ts = int(time.time())
    models = [
        ("SalathanieAI", "salathanie-sovereign"),
        ("salathanie-ai-v4", "salathanie-sovereign"),
        ("astra-alstra-jet", "salathanie-sovereign"),
        ("salathanie-offline-wiki", "salathanie-sovereign"),
    ]
    return {
        "object": "list",
        "data": [
            {"id": mid, "object": "model", "created": ts, "owned_by": owner}
            for mid, owner in models
        ],
    }


def _extract_user_prompt(body: dict) -> str:
    msgs = body.get("messages")
    if isinstance(msgs, list):
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, list):
                    content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
                if str(content).strip():
                    return str(content).strip()
    return str(body.get("prompt", "")).strip() or "Status and ranked control recommendation"


def handle_v1_chat_completions(body: dict, infer_fn) -> dict:
    ts = int(time.time())
    req_model = str(body.get("model") or "SalathanieAI")
    prompt = _extract_user_prompt(body)
    kgso = fetch_kgso_atmos()
    exec_results = run_exec_directives(prompt)

    base_hazard = ledger.external_hazard_score()
    fused_hazard = round(min(1.0, base_hazard + kgso["wind_turbulence_factor"] * 0.35), 3)
    in_telem = body.get("telemetry") if isinstance(body.get("telemetry"), dict) else {}
    in_telem.setdefault("hazard", fused_hazard)

    inf = infer_fn({"prompt": prompt, "telemetry": in_telem, "apply": bool(body.get("apply", False))})
    top = inf.get("top_decision") or {}
    ranked = inf.get("ranked_decisions") or []
    lctx = inf.get("ledger_context") or {}
    tvec = inf.get("telemetry_vector") or {}

    rag_snippet = ""
    try:
        from offline_wiki_rag import build_grounded_context
        rag = build_grounded_context(prompt, max_chars=360)
        if rag.get("hits", 0) > 0:
            rag_snippet = rag.get("context", "")
    except Exception:
        pass

    lines = [
        f"[SALATHANIE AI // {req_model}] Ranked Control & Execution Synthesis",
        f"• Top Action (#1, score {top.get('score', 0)}): {top.get('action', 'HOLD')} -> Mode: {top.get('recommended_mode', 'AUTONOMOUS-MUTATE')}",
        f"• Rationale: {top.get('rationale', 'Telemetry nominal')}",
        f"• Control Vector: {json.dumps(top.get('control_vector', {}))}",
        f"• Runner-Up: " + ", ".join(f"#{x['rank']} {x['action']} ({x['score']})" for x in ranked[1:3]),
        f"• KGSO Atmos ({kgso['source']}): {kgso['temp_c']}°C | Wind {kgso['wind_kmh']} km/h @ {kgso['wind_deg']}° | {kgso['pressure_hpa']} hPa | {kgso['condition']} (turb={kgso['wind_turbulence_factor']})",
        f"• WAL Flight Ledger: Latest {lctx.get('latest_gen', '--')} | Best {lctx.get('best_gen', '--')} | Gens={lctx.get('total_generations', 0)} | RAM={tvec.get('ram_pct', '--')}% | Pods={tvec.get('pods_active', 4)}/4 | PX4={lctx.get('px4_vehicle', '--')}",
    ]
    if exec_results:
        lines.append("• [EXEC] Executed: " + json.dumps(exec_results))
    if rag_snippet:
        lines.append("• Offline Wiki Grounding: " + rag_snippet.replace("\n", " | ")[:320])
    lines.append(f"• Attestation HMAC: {inf.get('hmac_sig', '--')}")

    reply_text = "\n".join(lines)

    _NEURAL_STATS["v1_requests"] += 1
    _NEURAL_STATS["last_ts"] = ts
    _NEURAL_STATS["last_action"] = str(top.get("action", "HOLD"))
    _NEURAL_STATS["last_score"] = float(top.get("score", 0.0))
    _NEURAL_STATS["last_prompt"] = prompt[:120]

    try:
        with HDCSharedMemoryBus() as bus:
            bus.publish("salathanie-v1-shim", 8125, 200, deterministic_hv(f"v1:{top.get('action')}:{kgso['wind_kmh']}"))
    except Exception:
        pass

    prompt_tokens = max(1, len(prompt.split()))
    comp_tokens = max(1, len(reply_text.split()))
    return {
        "id": f"chatcmpl-salathanie-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": ts,
        "model": req_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": comp_tokens,
            "total_tokens": prompt_tokens + comp_tokens,
        },
        "salathanie_telemetry": {
            "kgso": kgso,
            "exec_results": exec_results,
            "top_decision": top,
            "ledger_context": lctx,
            "hmac_sig": inf.get("hmac_sig"),
        },
    }


def get_neural_state() -> dict:
    """Live telemetry packet driving the glowing SalathanieAI Neural Telemetry Visualizer."""
    kgso = fetch_kgso_atmos()
    snap = ledger.get_ledger_snapshot(5)
    g0 = (snap.get("generations") or [{}])[0]
    fitness = float(g0.get("fitness", 95.0))
    ram_pct = float(g0.get("ram_pct", 78.8))
    hazard = float(snap.get("hazard_score", 0.0))
    synapse_load = round(min(1.0, max(0.18, (ram_pct / 120.0) + kgso["wind_turbulence_factor"] * 0.3 + hazard * 0.25)), 3)
    return {
        "ok": True,
        "ts": int(time.time()),
        "model": "SalathanieAI",
        "v1_endpoint": "http://127.0.0.1:8125/v1/chat/completions",
        "kgso": kgso,
        "gen_id": g0.get("gen_id", "GEN-000"),
        "fitness": fitness,
        "ram_pct": ram_pct,
        "pods_mask": g0.get("pods_mask", "1111"),
        "hazard": hazard,
        "synapse_load": synapse_load,
        "stats": dict(_NEURAL_STATS),
    }
