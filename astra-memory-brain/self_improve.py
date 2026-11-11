import os
import json
import sqlite3
from datetime import datetime
from llm_router import query_177b

DB_PATH = os.path.expanduser("~/astra-memory-brain/episodic_reflexion.db")
SKILL_PATH = os.path.expanduser("~/astra-ooda-os/skill_packs.json")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trajectories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            domain TEXT,
            directive TEXT,
            outcome TEXT,
            success INTEGER,
            lesson TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generated_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            title TEXT,
            blueprint TEXT,
            status TEXT DEFAULT 'PROPOSED'
        )
    """)
    conn.commit()
    conn.close()

def record_and_reflect(domain: str, directive: str, outcome: str, success: bool):
    """Logs execution results and uses the 177B model to extract a reusable rule on failure."""
    init_db()
    lesson = "Execution nominal."
    if not success:
        prompt = (
            f"Domain: {domain}\nDirective: {directive}\nFailure Output: {outcome}\n"
            "Write a 1-sentence technical rule to prevent this exact failure next time."
        )
        lesson = query_177b("You are an AI self-correction critic.", prompt, temperature=0.1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO trajectories (ts, domain, directive, outcome, success, lesson) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), domain, directive, outcome, int(success), lesson)
    )
    conn.commit()
    conn.close()
    return lesson

def get_active_skill_context(domain: str) -> str:
    """Injects domain skill pack + past self-improvement lessons into the prompt."""
    init_db()
    skills = {}
    if os.path.exists(SKILL_PATH):
        with open(SKILL_PATH, "r") as f:
            skills = json.load(f)

    pack = skills.get(domain, {"role": "Autonomous Android Agent", "constraints": "Be precise."})
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT lesson FROM trajectories WHERE domain = ? AND success = 0 ORDER BY id DESC LIMIT 5",
        (domain,)
    ).fetchall()
    conn.close()

    lessons = "\n".join([f"- {r[0]}" for r in rows]) or "- No prior failures recorded."
    return f"ROLE: {pack['role']}\nCONSTRAINTS: {pack['constraints']}\nLEARNED_RULES:\n{lessons}"

def generate_new_idea(telemetry_snapshot: str) -> str:
    """Synthesizes new automation workflows from live Android & engine telemetry."""
    init_db()
    ctx = get_active_skill_context("idea_architect")
    prompt = f"Recent System & Android Telemetry:\n{telemetry_snapshot}\n\nPropose one high-value new feature or workflow automation."
    idea = query_177b(ctx, prompt, temperature=0.6)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO generated_ideas (ts, title, blueprint) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(), "Autonomous Upgrade Proposal", idea)
    )
    conn.commit()
    conn.close()
    return idea
