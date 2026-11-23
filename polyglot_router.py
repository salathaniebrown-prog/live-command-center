#!/usr/bin/env python3
"""
Zero-Overhead Polyglot Language Detector & Universal Model Prompt Enricher.
Uses stdlib unicodedata only (<0.2 MB RSS) so every Astra/Alstra model and avatar
understands and responds natively in any requested or detected world language.
"""
import unicodedata

SUPPORTED_SCRIPT_HINTS = {
    "ARABIC": "ar",
    "CYRILLIC": "ru",
    "DEVANAGARI": "hi",
    "HANGUL": "ko",
    "HIRAGANA": "ja",
    "KATAKANA": "ja",
    "CJK": "zh",
    "THAI": "th",
    "HEBREW": "he",
    "GREEK": "el",
    "BENGALI": "bn",
    "TAMIL": "ta",
    "TELUGU": "te",
}

POLYGLOT_SYSTEM_DIRECTIVE = (
    "POLYGLOT UNIVERSAL MODE (ALL LANGUAGES): Detect the user's language automatically "
    "and respond fluently, accurately, and natively in that exact language (including "
    "Spanish, French, Portuguese, German, Arabic, Mandarin, Japanese, Korean, Hindi, "
    "Russian, Swahili, and all ISO-639 languages) while keeping technical API/JSON keys intact."
)


def detect_language(text: str, explicit_lang: str | None = None) -> dict:
    if explicit_lang and str(explicit_lang).strip():
        code = str(explicit_lang).strip().split(",")[0].split(";")[0].strip()
        return {"lang": code, "source": "explicit", "polyglot_directive": POLYGLOT_SYSTEM_DIRECTIVE}

    counts: dict[str, int] = {}
    for ch in str(text or ""):
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        for script, iso in SUPPORTED_SCRIPT_HINTS.items():
            if script in name:
                counts[iso] = counts.get(iso, 0) + 1
                break
        else:
            counts["auto-latin"] = counts.get("auto-latin", 0) + 1

    if not counts:
        detected = "auto"
    else:
        top = max(counts.items(), key=lambda kv: kv[1])[0]
        detected = "auto" if top == "auto-latin" else top

    return {
        "lang": detected,
        "source": "unicodedata-auto",
        "all_languages_enabled": True,
        "polyglot_directive": POLYGLOT_SYSTEM_DIRECTIVE,
    }


def enrich_payload(payload: dict, accept_language: str | None = None) -> dict:
    out = dict(payload or {})
    text = out.get("prompt") or out.get("message") or out.get("text") or out.get("query") or ""
    explicit = out.get("lang") or out.get("language") or accept_language
    meta = detect_language(str(text), explicit)
    out["polyglot"] = meta
    if "system" in out and POLYGLOT_SYSTEM_DIRECTIVE not in str(out["system"]):
        out["system"] = f"{out['system']}\n{POLYGLOT_SYSTEM_DIRECTIVE}"
    else:
        out.setdefault("system_directive", POLYGLOT_SYSTEM_DIRECTIVE)
    return out
