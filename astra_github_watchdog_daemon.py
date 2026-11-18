#!/usr/bin/env python3
"""
ASTRA // Local GitHub Watchdog Daemon (127.0.0.1:8141)
- Monitors local & remote Git commits, branch pushes, and GitHub Actions workflow runs
- Feeds every event into Local Enhancement Station (8137) & SQLite WAL Fused Telemetry
- Triggers immediate on-device model task execution via Local Proxy (8139) with zero data exfiltration
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import threading
import subprocess
import urllib.request
import http.server
import socketserver
from pathlib import Path

HOME_DIR = Path.home()
BRAIN_DB = HOME_DIR / ".astra_local_brain.db"
ENHANCEMENT_STATION = "http://127.0.0.1:8137"
LOCAL_MODEL_PROXY = "http://127.0.0.1:8139/v1/chat/completions"

HOST = "127.0.0.1"
PORT = 8141
POLL_INTERVAL_SEC = 15

STATE_LOCK = threading.Lock()
LAST_SEEN = {
    "local_head": "",
    "remote_head": "",
    "latest_run_id": "",
    "latest_run_status": "",
    "events_processed": 0,
    "last_dispatch_summary": "IDLE_READY"
}


def init_watchdog_db():
    conn = sqlite3.connect(str(BRAIN_DB), timeout=10.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS astra_github_watchdog_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            event_source TEXT,
            event_type TEXT,
            branch TEXT,
            commit_sha TEXT,
            workflow_run_id TEXT,
            workflow_status TEXT,
            local_model_response TEXT,
            event_sha256 TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS astra_cognitive_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            event_type TEXT,
            session_id TEXT,
            coherence_score REAL,
            payload TEXT
        )
    """)
    conn.commit()
    conn.close()


def run_cmd(cmd: list, timeout: int = 12) -> str:
    try:
        res = subprocess.run(
            cmd,
            cwd=str(HOME_DIR),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return (res.stdout or res.stderr or "").strip()
    except Exception as exc:
        return f"ERR:{exc}"


def trigger_local_enhancement_and_model(event_payload: dict) -> str:
    """
    Feeds the GitHub event into the Local Enhancement Station (8137) and
    dispatches an immediate task execution request to the local model proxy (8139).
    All processing remains strictly on 127.0.0.1.
    """
    # 1. Trigger Context-Telemetry & Multi-Chain Station checkpoint (POST 127.0.0.1:8137)
    try:
        req_station = urllib.request.Request(
            f"{ENHANCEMENT_STATION}/api/context/telemetry",
            data=json.dumps(event_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_station, timeout=6.0) as resp:
            resp.read()
    except Exception:
        pass

    # 2. Dispatch immediate task execution to Local Model Proxy (POST 127.0.0.1:8139/v1/chat/completions)
    task_prompt = (
        f"LOCAL_GITHUB_WATCHDOG_EVENT: type={event_payload['event_type']} "
        f"branch={event_payload['branch']} commit={event_payload['commit_sha']} "
        f"workflow={event_payload['workflow_run_id']}:{event_payload['workflow_status']}. "
        f"Verify local node telemetry & audit integrity."
    )
    try:
        chat_body = json.dumps({
            "model": "astra-sovereign-tool-router-v1",
            "messages": [{"role": "user", "content": task_prompt}]
        }).encode("utf-8")
        req_model = urllib.request.Request(
            LOCAL_MODEL_PROXY,
            data=chat_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_model, timeout=8.0) as mresp:
            mdata = json.loads(mresp.read().decode("utf-8"))
            return mdata.get("choices", [{}])[0].get("message", {}).get("content", "DISPATCHED_OK")[:400]
    except Exception as exc:
        return f"LOCAL_QUEUED_FALLBACK:{str(exc)[:120]}"


def record_and_dispatch_event(
    source: str,
    event_type: str,
    branch: str,
    commit_sha: str,
    run_id: str = "N/A",
    run_status: str = "N/A"
) -> dict:
    init_watchdog_db()
    now = time.time()

    event_payload = {
        "timestamp": now,
        "event_source": source,
        "event_type": event_type,
        "branch": branch,
        "commit_sha": commit_sha,
        "workflow_run_id": run_id,
        "workflow_status": run_status,
    }

    model_out = trigger_local_enhancement_and_model(event_payload)
    digest = hashlib.sha256(json.dumps(event_payload, sort_keys=True).encode("utf-8")).hexdigest()

    conn = sqlite3.connect(str(BRAIN_DB), timeout=10.0)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO astra_github_watchdog_events
        (timestamp, event_source, event_type, branch, commit_sha, workflow_run_id, workflow_status, local_model_response, event_sha256)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, source, event_type, branch, commit_sha, run_id, run_status, model_out, digest))

    cur.execute("""
        INSERT INTO astra_cognitive_telemetry
        (timestamp, event_type, session_id, coherence_score, payload)
        VALUES (?, ?, ?, ?, ?)
    """, (
        now,
        f"GITHUB_WATCHDOG_{event_type}",
        "github-watchdog-8141",
        0.9995,
        json.dumps({
            "source": source,
            "branch": branch,
            "commit": commit_sha,
            "workflow": f"{run_id}:{run_status}",
            "sha256": digest
        })
    ))
    conn.commit()
    conn.close()

    with STATE_LOCK:
        LAST_SEEN["events_processed"] += 1
        LAST_SEEN["last_dispatch_summary"] = f"{event_type}@{commit_sha[:7]} -> {run_status}"

    return {**event_payload, "event_sha256": digest, "local_model_dispatch": model_out}


def scan_github_state(force_emit: bool = False) -> dict:
    """Checks local HEAD, remote origin/main HEAD, and latest GitHub Actions runs."""
    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "main"
    local_head = run_cmd(["git", "rev-parse", "HEAD"])

    # Fetch remote refs silently so branch pushes on GitHub are caught in real time
    run_cmd(["git", "fetch", "origin", branch, "--quiet"], timeout=15)
    remote_head = run_cmd(["git", "rev-parse", f"origin/{branch}"])

    # Query latest GitHub Actions workflow run via authenticated gh CLI
    run_id = "NONE"
    run_status = "NO_RUNS"
    run_name = "CI"
    gh_json = run_cmd([
        "gh", "run", "list", "--limit", "1",
        "--json", "databaseId,status,conclusion,name,headSha"
    ], timeout=12)
    if gh_json.startswith("["):
        try:
            runs = json.loads(gh_json)
            if runs:
                r = runs[0]
                run_id = str(r.get("databaseId", "NONE"))
                run_status = str(r.get("conclusion") or r.get("status") or "UNKNOWN")
                run_name = str(r.get("name", "CI"))
        except Exception:
            pass

    dispatched = []
    with STATE_LOCK:
        prev_local = LAST_SEEN["local_head"]
        prev_remote = LAST_SEEN["remote_head"]
        prev_run = f"{LAST_SEEN['latest_run_id']}:{LAST_SEEN['latest_run_status']}"

        LAST_SEEN["local_head"] = local_head
        LAST_SEEN["remote_head"] = remote_head
        LAST_SEEN["latest_run_id"] = run_id
        LAST_SEEN["latest_run_status"] = run_status

    curr_run = f"{run_id}:{run_status}"

    if force_emit or (prev_local and local_head != prev_local):
        dispatched.append(record_and_dispatch_event(
            "LOCAL_GIT", "COMMIT_DETECTED", branch, local_head, run_id, run_status
        ))

    if prev_remote and remote_head != prev_remote:
        dispatched.append(record_and_dispatch_event(
            "GITHUB_REMOTE", "BRANCH_PUSH_DETECTED", branch, remote_head, run_id, run_status
        ))

    if prev_run != ":" and curr_run != prev_run and run_id != "NONE":
        dispatched.append(record_and_dispatch_event(
            "GITHUB_ACTIONS", f"WORKFLOW_{run_name.upper().replace(' ', '_')}", branch, local_head, run_id, run_status
        ))

    return {
        "watchdog": "ASTRA_GITHUB_WATCHDOG_DAEMON_V1",
        "branch": branch,
        "local_head": local_head,
        "remote_head": remote_head,
        "in_sync": (local_head == remote_head),
        "latest_workflow": {"id": run_id, "name": run_name, "status": run_status},
        "events_processed": LAST_SEEN["events_processed"],
        "dispatched_now": dispatched
    }


def background_poll_loop():
    # Initial baseline capture + boot telemetry event
    scan_github_state(force_emit=True)
    while True:
        time.sleep(POLL_INTERVAL_SEC)
        try:
            scan_github_state(force_emit=False)
        except Exception:
            pass


class ReusableWatchdogServer(socketserver.TCPServer):
    allow_reuse_address = True


class WatchdogHandler(http.server.BaseHTTPRequestHandler):
    def _json(self, payload: dict, status: int = 200):
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/health", "/api/github/watchdog"):
            state = scan_github_state(force_emit=False)
            return self._json(state)
        elif path == "/api/github/events":
            init_watchdog_db()
            conn = sqlite3.connect(str(BRAIN_DB), timeout=5.0)
            rows = conn.execute(
                "SELECT id, timestamp, event_source, event_type, branch, commit_sha, workflow_run_id, workflow_status, event_sha256 "
                "FROM astra_github_watchdog_events ORDER BY id DESC LIMIT 10;"
            ).fetchall()
            conn.close()
            events = [
                {
                    "id": r[0], "timestamp": r[1], "source": r[2], "type": r[3],
                    "branch": r[4], "commit": r[5], "workflow_id": r[6],
                    "workflow_status": r[7], "sha256": r[8]
                }
                for r in rows
            ]
            return self._json({"events": events})
        return self._json({"error": "Not Found"}, status=404)

    def do_POST(self):
        # Instant trigger endpoint called by local git post-commit / post-merge hooks
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {}
        ev_type = data.get("event_type", "GIT_HOOK_PUSH")
        branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "main"
        sha = run_cmd(["git", "rev-parse", "HEAD"])
        res = record_and_dispatch_event("GIT_LOCAL_HOOK", ev_type, branch, sha)
        return self._json({"status": "HOOK_EVENT_DISPATCHED", "event": res})


if __name__ == "__main__":
    if "--serve" in sys.argv:
        init_watchdog_db()
        t = threading.Thread(target=background_poll_loop, daemon=True)
        t.start()
        with ReusableWatchdogServer((HOST, PORT), WatchdogHandler) as httpd:
            print(f"[✔] ASTRA Local GitHub Watchdog Daemon locked on http://{HOST}:{PORT}")
            httpd.serve_forever()
    else:
        print(json.dumps(scan_github_state(force_emit=True), indent=2))
