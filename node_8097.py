import gc
import signal

def _handle_sigusr1_compact(signum, frame):
    gc.collect()

signal.signal(signal.SIGUSR1, _handle_sigusr1_compact)

import hashlib, json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8097
SERVICE_NAME = "COMPLIANCE_VAULT_8097"
ROLE_DESC = "Zero-Trust Policy & Audit Proof Validator"
IDLE_TTL_SEC = 120
LAST_HIT = time.time()

def idle_reaper():
    while True:
        time.sleep(10)
        if time.time() - LAST_HIT > IDLE_TTL_SEC:
            os._exit(0)

class OnDemandNodeHandler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        global LAST_HIT
        LAST_HIT = time.time()
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self._json(200, {
            "service": SERVICE_NAME,
            "port": PORT,
            "role": ROLE_DESC,
            "status": "ONLINE_ON_DEMAND",
            "idle_ttl_remaining_sec": max(0, round(IDLE_TTL_SEC - (time.time() - LAST_HIT), 1))
        })

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln).decode("utf-8", errors="ignore") if ln else "{}"
        data = json.loads(raw) if raw.strip() else {}
        job_id = f"JOB-{PORT}-" + uuid.uuid4().hex[:6].upper()
        proof = "0x" + hashlib.sha256(f"{job_id}|{PORT}|{time.time()}".encode()).hexdigest()
        self._json(200, {
            "job_id": job_id,
            "service": SERVICE_NAME,
            "port": PORT,
            "status": "EXECUTED_AND_HIBERNATION_ARMED",
            "echo_input": data,
            "attestation_hash": proof
        })

if __name__ == "__main__":
    threading.Thread(target=idle_reaper, daemon=True).start()
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("0.0.0.0", PORT), OnDemandNodeHandler).serve_forever()
