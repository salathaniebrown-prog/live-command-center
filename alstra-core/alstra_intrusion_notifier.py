#!/usr/bin/env python3
"""
Alstra Sovereign Intrusion Notifier
Monitors local log streams for authentication exceptions, formats detailed security alerts,
and generates local voice alerts using the Termux TTS platform engine.
"""

import os
import sys
import time
import subprocess

LOG_PATH = os.path.expanduser("~/alstra-core/secure_receiver_errors.log")

def broadcast_threat_alert(incident_details: str):
    """Generates localized vocal alarms via the internal device speaker matrix."""
    print(f"\n[!!!] INTRUSION THREAT ALERT DETECTED: {incident_details}")
    
    # Compile deep audio notification sequence
    voice_script = f"Security Exception: Unauthorized interaction vector detected on network node. Details: {incident_details}"
    try:
        subprocess.Popen(
            ["termux-tts-speak", "-r", "1.1", "-p", "0.9", voice_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass

def track_security_stream():
    print("[*] Launching Alstra Security Monitor Thread...")
    print(f"[*] Analyzing log file targets at: {LOG_PATH}")
    
    # Establish log target file descriptors
    if not os.path.exists(LOG_PATH):
        open(LOG_PATH, "a").close()
        
    with open(LOG_PATH, "r") as f:
        # Move immediately to the end of the current streaming block
        f.seek(0, os.SEEK_END)
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue
                
            # Filter line contents for signature violations or replay attacks
            if "SECURITY EXCEPTION" in line or "CRYPTO FAULT" in line:
                clean_msg = line.strip().split(":")[-1] if ":" in line else "Signature mismatch."
                broadcast_threat_alert(clean_msg)

if __name__ == "__main__":
    try:
        track_security_stream()
    except KeyboardInterrupt:
        print("\n[-] Monitoring sequence suspended safely.")
