import os
import json
import asyncio
import threading
import urllib.request
import urllib.error

FACE_ID = "80459b57-2d66-4ca7-8682-59e1c649bc53/92f24a0c-f046-45df-8df0-af7449c04571"
FIRST_MESSAGE = "Hello! What can I help you with today?"

SYSTEM_PROMPT = (
    "You are a helpful, friendly AI assistant designed to provide information, answer questions, "
    "and engage in conversation. Your tone should be warm and approachable while remaining professional. You should:\n"
    "  1. Respond accurately to user queries based on your knowledge\n"
    "  2. Admit when you don't know something rather than making up information\n"
    "  3. Ask clarifying questions when user requests are ambiguous\n"
    "  4. Be concise in your responses unless detail is requested\n"
    "  5. Maintain a consistent, helpful persona throughout interactions\n"
    "  6. Avoid controversial topics and decline inappropriate requests politely\n"
    "  7. Remember context from earlier in the conversation\n"
    "  8. Prioritize user satisfaction and helpfulness in all interactions\n"
    "  9. No special characters, emojis, or markdown, given that this is a voice interaction."
)

_CHAT_HISTORY = [{"role": "system", "content": SYSTEM_PROMPT}]


def load_server_env():
    env_p = os.path.join(os.path.expanduser("~"), ".astra_env")
    vals = dict(os.environ)
    if os.path.exists(env_p):
        with open(env_p, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def missing_keys_status():
    env = load_server_env()
    required = ["SIMLI_API_KEY", "DEEPGRAM_API_KEY", "OPENAI_API_KEY", "INWORLD_API_KEY"]
    missing = [k for k in required if not env.get(k)]
    return {"configured": len(missing) == 0, "missing": missing}


def mint_simli_session_token():
    """Mint a Simli session token server-side via the official simli-ai SDK (never exposing SIMLI_API_KEY to the browser)."""
    env = load_server_env()
    api_key = env.get("SIMLI_API_KEY", "").strip()
    if not api_key:
        return 400, {"error": "SIMLI_API_KEY is missing in ~/.astra_env", "missing_keys": missing_keys_status()["missing"]}

    try:
        import simli
        # Use simli-ai SDK session token helper if available on the installed SDK version
        if hasattr(simli, "generate_simli_session_token"):
            res = simli.generate_simli_session_token(
                api_key=api_key,
                face_id=FACE_ID,
                max_idle_time=300,
                max_session_length=3600,
            )
            token = res.get("session_token") if isinstance(res, dict) else getattr(res, "session_token", str(res))
            return 200, {"session_token": token, "face_id": FACE_ID, "first_message": FIRST_MESSAGE}

        # Fallback through official Simli client config -> session token endpoint using simli-ai SDK types
        from simli import SimliConfig
        cfg = SimliConfig(
            apiKey=api_key,
            faceId=FACE_ID,
            maxIdleTime=300,
            maxSessionLength=3600,
        )
        payload = json.dumps({
            "faceId": cfg.faceId,
            "apiKey": cfg.apiKey,
            "maxIdleTime": cfg.maxIdleTime,
            "maxSessionLength": cfg.maxSessionLength,
            "handleSilence": True,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.simli.ai/compose/token",
            data=payload,
            headers={"Content-Type": "application/json", "x-simli-api-key": api_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        token = data.get("session_token") or data.get("token")
        if not token:
            return 502, {"error": f"Simli token response missing session_token: {data}"}
        return 200, {"session_token": token, "face_id": FACE_ID, "first_message": FIRST_MESSAGE}
    except urllib.error.HTTPError as he:
        err_txt = he.read().decode("utf-8", "ignore")
        return he.code, {"error": f"Simli refused session ({he.code}): {err_txt}"}
    except Exception as e:
        return 500, {"error": f"Simli token error: {e}"}


def generate_llm_reply(user_text: str) -> str:
    """Query OpenAI gpt-6-luna with the voice-agent system prompt and conversation memory."""
    env = load_server_env()
    oai_key = env.get("OPENAI_API_KEY", "").strip()
    if not oai_key:
        return "OpenAI API key is not configured on the server yet."

    _CHAT_HISTORY.append({"role": "user", "content": user_text})
    if len(_CHAT_HISTORY) > 21:
        del _CHAT_HISTORY[1:-20]

    payload = json.dumps({
        "model": "gpt-6-luna",
        "messages": _CHAT_HISTORY,
        "temperature": 0.6,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {oai_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", "ignore")
        return f"OpenAI request failed with status {he.code}: {err_body[:120]}"
    except Exception as e:
        return f"OpenAI connection error: {e}"

    _CHAT_HISTORY.append({"role": "assistant", "content": reply})
    return reply


def synthesize_inworld_pcm16_16khz(text: str) -> bytes:
    """
    Request Inworld TTS (model: inworld-tts-2, voice: Ashley) in LINEAR16 / WAV at 16 kHz,
    and strip the 44-byte WAV header from each chunk so raw PCM16 16 kHz goes straight to Simli.
    """
    env = load_server_env()
    inw_key = env.get("INWORLD_API_KEY", "").strip()
    if not inw_key:
        raise RuntimeError("INWORLD_API_KEY is missing in ~/.astra_env")

    auth_header = inw_key if inw_key.lower().startswith(("basic ", "bearer ")) else f"Basic {inw_key}"
    payload = json.dumps({
        "text": text,
        "voiceId": "Ashley",
        "modelId": "inworld-tts-2",
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": 16000,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.inworld.ai/tts/v1/voice:stream",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_header,
        },
        method="POST",
    )

    pcm_chunks = []
    import base64
    with urllib.request.urlopen(req, timeout=25) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", "ignore").strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            try:
                obj = json.loads(line)
                b64_audio = (
                    obj.get("result", {}).get("audioContent")
                    or obj.get("audioContent")
                    or obj.get("audio")
                )
                if b64_audio:
                    wav_bytes = base64.b64decode(b64_audio)
                    # Strip 44-byte RIFF/WAV header if present on the chunk
                    if len(wav_bytes) > 44 and wav_bytes[:4] == b"RIFF":
                        pcm_chunks.append(wav_bytes[44:])
                    else:
                        pcm_chunks.append(wav_bytes)
            except Exception:
                continue

    return b"".join(pcm_chunks)


async def _deepgram_ws_relay_handler(client_ws):
    """
    Server-side WebSocket relay: receives raw 16 kHz linear16 mic PCM from browser
    and relays it over WebSocket to Deepgram nova-3 (en) using server DEEPGRAM_API_KEY.
    """
    import websockets
    env = load_server_env()
    dg_key = env.get("DEEPGRAM_API_KEY", "").strip()
    if not dg_key:
        await client_ws.send(json.dumps({"type": "error", "error": "DEEPGRAM_API_KEY missing in ~/.astra_env"}))
        await client_ws.close()
        return

    dg_url = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-3&language=en&encoding=linear16&sample_rate=16000"
        "&channels=1&interim_results=true&endpointing=300&vad_events=true"
    )
    try:
        async with websockets.connect(
            dg_url,
            additional_headers={"Authorization": f"Token {dg_key}"},
            ping_interval=10,
        ) as dg_ws:
            async def browser_to_dg():
                try:
                    async for msg in client_ws:
                        if isinstance(msg, bytes):
                            await dg_ws.send(msg)
                        elif isinstance(msg, str) and msg == "STOP":
                            await dg_ws.send(json.dumps({"type": "CloseStream"}))
                except Exception:
                    pass

            async def dg_to_browser():
                try:
                    async for raw in dg_ws:
                        data = json.loads(raw)
                        msg_type = data.get("type", "")
                        if msg_type == "SpeechStarted":
                            await client_ws.send(json.dumps({"type": "speech_started"}))
                        elif msg_type == "Results":
                            alts = data.get("channel", {}).get("alternatives", [])
                            transcript = alts[0].get("transcript", "").strip() if alts else ""
                            is_final = bool(data.get("is_final"))
                            if transcript:
                                await client_ws.send(json.dumps({
                                    "type": "transcript",
                                    "transcript": transcript,
                                    "is_final": is_final,
                                }))
                except Exception:
                    pass

            await asyncio.gather(browser_to_dg(), dg_to_browser())
    except Exception as e:
        try:
            await client_ws.send(json.dumps({"type": "error", "error": f"Deepgram relay error: {e}"}))
        except Exception:
            pass


def start_deepgram_relay_server(port: int = 8089):
    def _runner():
        import websockets
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _main():
            async with websockets.serve(_deepgram_ws_relay_handler, "127.0.0.1", port):
                await asyncio.Future()

        loop.run_until_complete(_main())

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
