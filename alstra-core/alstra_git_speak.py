#!/usr/bin/env python3
"""
Alstra Sovereign Git-Speak Pipeline
Combines automated local payload commits, multi-point version synchronization,
and spoken audio feedback metrics via Termux API TTS engines.
"""

import os
import json
import sqlite3
import subprocess
import sys

DB_PATH = os.path.expanduser("~/alstra-core/alstra_core.db")
REPO_DIR = os.path.expanduser("~/alstra-core")

def speak_notification(text: str):
    """Triggers localized audio notifications via Termux TTS interface."""
    print(f"[*] Verbalizing Status: \"{text}\"")
    try:
        subprocess.Popen(
            ["termux-tts-speak", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        print("[!] Warning: termux-tts-speak engine binary not accessible.")

def gather_latest_payload_summary() -> str:
    """Extracts tracking state from the zero-latency structural ledger."""
    if not os.path.exists(DB_PATH):
        return "Generic system matrix state change."
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT command, nonce FROM verified_commands ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return f"Command vector {row[0]} verified under sequential identifier block {row[1]}"
    except Exception as e:
        print(f"[-] Meta extraction note: {e}")
        
    return "Optimized infrastructure payload alignment complete."

def execute_sovereign_git_push():
    os.chdir(REPO_DIR)
    
    # 1. Check for untracked infrastructure changes
    status_proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if not status_proc.stdout.strip():
        msg = "Local repository state fully synchronized. No pending telemetry items require transition."
        speak_notification(msg)
        print(f"[+] {msg}")
        return

    # 2. Compile verbal script based on actual ledger history
    payload_summary = gather_latest_payload_summary()
    tts_announcement = f"Initiating secure handshake. Synchronizing master workspace payload data to GitHub. {payload_summary}."
    
    # Speak prior to starting the network layer push
    speak_notification(tts_announcement)

    # 3. Process the sequential git pipeline steps
    try:
        print("[*] Stage 1: Staging workspace payload updates...")
        subprocess.run(["git", "add", "."], check=True)
        
        print("[*] Stage 2: Packaging ledger verification blocks...")
        commit_msg = f"telemetry-sync: {payload_summary}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        print("[*] Stage 3: Routing secure stream to GitHub upstream branch...")
        # Redirecting stream output tracking directly to stdout
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        success_msg = "GitHub telemetry sync verified. Distribution channel locked with zero errors."
        speak_notification(success_msg)
        print(f"[⚡] SUCCESS: {success_msg}")
        
    except subprocess.CalledProcessError as e:
        error_msg = "Pipeline restriction encountered during remote data transport operations."
        speak_notification(error_msg)
        print(f"[!] Critical structural failure: {e}", file=sys.stderr)

if __name__ == "__main__":
    execute_sovereign_git_push()
