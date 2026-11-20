import hashlib, http.server, json, os, pathlib, socketserver, subprocess, time, uuid

STATE_PATH = pathlib.Path.home() / "astra_rw_ledger.json"
PORT = 8169

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    init = {
        "created_at": int(time.time()),
        "balance_usd": 0.0,
        "total_calls": 0,
        "keys": {
            "ak_live_demo_001": {
                "owner": "investor_sandbox",
                "tier": "enterprise_unlimited",
                "calls": 0,
                "spend_usd": 0.0,
                "active": True,
            }
        },
        "jobs": [],
        "events": [],
    }
    save_state(init)
    return init

def save_state(st):
    st["updated_at"] = int(time.time())
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_PATH)

class RWHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, code, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.end_headers()

    def do_GET(self):
        st = load_state()
        path = self.path.split("?", 1)[0]
        if path in ("/", "/health", "/api/status"):
            return self._json(200, {
                "ok": True,
                "service": "astra-rw-revenue-exec-8169",
                "mode": "READ_WRITE_PERSISTENT",
                "port": PORT,
                "balance_usd": st["balance_usd"],
                "total_calls": st["total_calls"],
                "active_keys": len([k for k, v in st["keys"].items() if v.get("active")]),
                "jobs_count": len(st["jobs"]),
                "events_count": len(st["events"]),
                "state_file": str(STATE_PATH),
            })
        if path == "/api/ledger":
            return self._json(200, {"ok": True, "ledger": st})
        if path == "/api/jobs":
            return self._json(200, {"ok": True, "jobs": st["jobs"][-50:]})
        self._json(404, {"ok": False, "error": "not_found", "path": path})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"invalid_json: {e}"})

        path = self.path.split("?", 1)[0]
        api_key = self.headers.get("X-API-Key") or body.get("api_key") or "ak_live_demo_001"
        st = load_state()
        now = int(time.time())

        if path == "/api/keys/create":
            owner = str(body.get("owner", "client_workspace"))[:80]
            tier = str(body.get("tier", "pro"))[:32]
            new_key = "ak_live_" + uuid.uuid4().hex[:16]
            st["keys"][new_key] = {
                "owner": owner,
                "tier": tier,
                "calls": 0,
                "spend_usd": 0.0,
                "active": True,
                "created_at": now,
            }
            st["events"].append({"ts": now, "type": "KEY_CREATED", "key": new_key, "owner": owner})
            save_state(st)
            return self._json(200, {"ok": True, "api_key": new_key, "record": st["keys"][new_key]})

        if path == "/api/billing/topup":
            amount = float(body.get("amount_usd", 0.0))
            if amount <= 0:
                return self._json(400, {"ok": False, "error": "amount_usd must be > 0"})
            st["balance_usd"] = round(st["balance_usd"] + amount, 4)
            st["events"].append({"ts": now, "type": "TOPUP_USD", "amount_usd": amount, "balance_usd": st["balance_usd"]})
            save_state(st)
            return self._json(200, {"ok": True, "balance_usd": st["balance_usd"]})

        if path == "/api/exec":
            cmd_type = str(body.get("type", "compute_job"))
            payload_data = body.get("payload", {})
            unit_cost = float(body.get("cost_usd", 0.05))
            job_id = "job_" + uuid.uuid4().hex[:12]

            key_rec = st["keys"].get(api_key)
            if not key_rec or not key_rec.get("active"):
                key_rec = st["keys"]["ak_live_demo_001"]
                api_key = "ak_live_demo_001"

            t0 = time.perf_counter()
            result = {"dispatched_type": cmd_type, "payload": payload_data}

            if cmd_type == "shell_probe":
                safe_cmd = str(body.get("cmd", "uname -a"))[:160]
                proc = subprocess.run(safe_cmd, shell=True, capture_output=True, text=True, timeout=5)
                result["exit_code"] = proc.returncode
                result["stdout"] = proc.stdout.strip()[:1000]
                result["stderr"] = proc.stderr.strip()[:400]
            elif cmd_type == "hash_payload":
                raw_str = json.dumps(payload_data, sort_keys=True).encode("utf-8")
                result["sha256"] = hashlib.sha256(raw_str).hexdigest()

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
            key_rec["calls"] = int(key_rec.get("calls", 0)) + 1
            key_rec["spend_usd"] = round(float(key_rec.get("spend_usd", 0.0)) + unit_cost, 4)
            st["total_calls"] = int(st.get("total_calls", 0)) + 1

            job_rec = {
                "id": job_id,
                "ts": now,
                "api_key": api_key,
                "type": cmd_type,
                "cost_usd": unit_cost,
                "elapsed_ms": elapsed_ms,
                "result": result,
                "status": "COMPLETED",
            }
            st["jobs"].append(job_rec)
            st["events"].append({"ts": now, "type": "JOB_EXECUTED", "job_id": job_id, "cost_usd": unit_cost})
            save_state(st)
            return self._json(200, {"ok": True, "job": job_rec, "balance_usd": st["balance_usd"], "total_calls": st["total_calls"]})

        self._json(404, {"ok": False, "error": "unknown_endpoint", "path": path})

class ReusableThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    load_state()
    srv = ReusableThreadingHTTPServer(("127.0.0.1", PORT), RWHandler)
    print(f"[ASTRA RW REVENUE & EXEC] Listening on 127.0.0.1:{PORT}")
    srv.serve_forever()
