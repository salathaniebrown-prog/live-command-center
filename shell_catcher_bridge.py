#!/usr/bin/env python3
"""
Zero-Overhead Shell Catcher Bridge & Agent Mastery Inspector.
Reads ~/wargame_shell_catcher/shell_catcher_core.py & shell_catcher_events.db
so ASTRA, ALSTRA, and SALATHANIE-AI agents can query & enforce shell rules.
"""
import json
import os
import re
import sqlite3
import time

HOME = os.path.expanduser("~")
SC_DIR = os.path.join(HOME, "wargame_shell_catcher")
SC_CORE = os.path.join(SC_DIR, "shell_catcher_core.py")
SC_DB = os.path.join(SC_DIR, "shell_catcher_events.db")

DANGEROUS_PATTERNS = [
    (r"\brm\s+-rf\s+/(?:\s|$)", "CRITICAL_ROOT_WIPE"),
    (r"\bpkill\s+-USR1\s+-f\s+['\"]?python", "PYTHON_DEFAULT_SIGUSR1_KILL"),
    (r"\bkill\s+-9\s+-1\b", "GLOBAL_PROCESS_KILL"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "FORK_BOMB"),
    (r"\bdd\s+if=/dev/zero\s+of=/dev/", "BLOCK_DEVICE_OVERWRITE"),
]


def get_shell_catcher_status() -> dict:
    core_exists = os.path.exists(SC_CORE)
    db_exists = os.path.exists(SC_DB)
    tables = []
    recent_events = []
    event_count = 0
    if db_exists:
        try:
            con = sqlite3.connect(f"file:{SC_DB}?mode=ro", uri=True, timeout=1.0)
            cur = con.cursor()
            tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if tables:
                t0 = tables[0]
                event_count = cur.execute(f"SELECT COUNT(*) FROM [{t0}]").fetchone()[0]
                rows = cur.execute(f"SELECT * FROM [{t0}] ORDER BY rowid DESC LIMIT 5").fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                recent_events = [dict(zip(cols, r)) for r in rows]
            con.close()
        except Exception as e:
            recent_events = [{"read_note": type(e).__name__}]

    return {
        "ok": True,
        "ts": time.time(),
        "guard_active": core_exists,
        "core_path": SC_CORE,
        "db_path": SC_DB,
        "db_exists": db_exists,
        "tables": tables,
        "event_count": event_count,
        "recent_events": recent_events,
        "agent_mastery_rules": [code for _, code in DANGEROUS_PATTERNS],
    }


def audit_shell_command(cmd: str) -> dict:
    hits = [code for pat, code in DANGEROUS_PATTERNS if re.search(pat, cmd or "")]
    return {
        "ok": len(hits) == 0,
        "allowed": len(hits) == 0,
        "violations": hits,
        "command": (cmd or "")[:240],
        "guard": "wargame_shell_catcher",
    }
