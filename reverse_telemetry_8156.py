import ast, hashlib, http.client, json, os, re, sqlite3, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "astra_ai_memory.db")
TRACKED_PORTS = (8088, 8090, 8095, 8096, 8097, 8098, 8099, 8100, 8101, 8102, 8115, 8117, 8119, 8121, 8125, 8132, 8140, 8150, 8152, 8154, 8156)

def map_running_pids():
    # Android-safe process scanner via /proc/<pid>/cmdline (no lsof/fuser needed)
    procs = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        cmd_file = f"/proc/{entry}/cmdline"
        try:
            raw = open(cmd_file, "rb").read().replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
            if any(k in raw for k in ("python", "node", "pm2", "cloudflared", "astra", "salathanie")):
                procs.append({"pid": int(entry), "cmd": raw[:140]})
        except Exception:
            continue
    return procs

def probe_port_telemetry(port):
    t0 = time.time()
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
        c.request("GET", "/")
        r = c.getresponse()
        body = r.read().decode("utf-8", errors="ignore")[:180]
        ms = round((time.time() - t0) * 1000.0, 2)
        return {"port": port, "online": True, "http": r.status, "latency_ms": ms, "signature": body.strip()[:80]}
    except Exception as e:
        return {"port": port, "online": False, "error": type(e).__name__}

def reverse_trace_recent_errors():
    # Scans PM2 and local logs for exact file:line tracebacks without base64 or shell limits
    log_dirs = [os.path.join(HOME, ".pm2", "logs"), HOME, os.path.join(HOME, "live-command-center")]
    frame_re = re.compile(r'File "([^"]+)", line (\d+)')
    findings = []
    for d in log_dirs:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".log"):
                continue
            fp = os.path.join(d, fn)
            try:
                tail = open(fp, "r", encoding="utf-8", errors="ignore").read()[-3000:]
                if "Traceback" in tail or "Error:" in tail:
                    frames = frame_re.findall(tail)
                    err_lines = [l.strip() for l in tail.splitlines() if "Error:" in l or "Exception:" in l]
                    if frames:
                        src_file, line_no = frames[-1]
                        findings.append({
                            "log": fn,
                            "source_file": src_file,
                            "line": int(line_no),
                            "exception": err_lines[-1] if err_lines else "UnknownError"
                        })
            except Exception:
                continue
    return findings[-10:]

def build_reverse_telemetry_snapshot():
    ports = [probe_port_telemetry(p) for p in TRACKED_PORTS]
    online = [x for x in ports if x["online"]]
    offline = [x["port"] for x in ports if not x["online"]]
    procs = map_running_pids()
    traces = reverse_trace_recent_errors()
    snap_id = "RTELEM-" + uuid.uuid4().hex[:8].upper()

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS reverse_telemetry_snapshots (
        snap_id TEXT PRIMARY KEY,
        online_count INTEGER,
        total_ports INTEGER,
        traces_count INTEGER,
        payload_json TEXT,
        timestamp REAL
    )""")
    report = {
        "snap_id": snap_id,
        "service": "REVERSE_CODING_TELEMETRY_ENGINE",
        "port": 8156,
        "ports_online": f"{len(online)}/{len(ports)}",
        "online_details": online,
        "offline_ports": offline,
        "active_pids": procs,
        "reverse_traced_errors": traces
    }
    conn.execute("INSERT INTO reverse_telemetry_snapshots VALUES (?, ?, ?, ?, ?, ?)", (snap_id, len(online), len(ports), len(traces), json.dumps(report), time.time()))
    conn.commit()
    conn.close()
    return report


def inspect_and_repair_target(target_file, line_no=0, apply_fix=False):
    import py_compile, shutil
    home_dir = os.path.expanduser("~")
    full_path = target_file if os.path.isabs(target_file) else os.path.join(home_dir, target_file)
    if not full_path.startswith(home_dir) or not os.path.isfile(full_path):
        return {"status": "INVALID_TARGET", "file": full_path}

    lines = open(full_path, "r", encoding="utf-8", errors="ignore").readlines()
    lno = int(line_no or 0)

    # Extract +/- 4 lines of surrounding source context
    ctx = []
    if 1 <= lno <= len(lines):
        start = max(1, lno - 4)
        end = min(len(lines), lno + 4)
        for i in range(start, end + 1):
            ctx.append({"line": i, "target": i == lno, "code": lines[i - 1].rstrip("\n")})

    compile_ok = False
    compile_err = ""
    try:
        py_compile.compile(full_path, doraise=True)
        compile_ok = True
    except py_compile.PyCompileError as exc:
        compile_err = str(exc.exc_value)
        if not lno:
            lno = getattr(exc.exc_value, "lineno", 0) or 0

    fix_applied = "NONE"
    if apply_fix and not compile_ok and 1 <= lno <= len(lines):
        snap_dir = os.path.join(home_dir, ".astra_atomic_checkpoints", "reverse_repair")
        os.makedirs(snap_dir, exist_ok=True)
        shutil.copy2(full_path, os.path.join(snap_dir, os.path.basename(full_path) + f".{int(time.time())}.bak"))

        raw = lines[lno - 1]
        stripped = raw.lstrip()
        if "indent" in compile_err.lower():
            chosen_ind = "        "
            for back in range(lno - 2, max(0, lno - 25), -1):
                prev = lines[back]
                ps = prev.lstrip()
                if ps and not ps.startswith("#"):
                    pi = prev[:len(prev) - len(ps)]
                    chosen_ind = (pi + "    ") if prev.rstrip().endswith(":") else pi
                    break
            lines[lno - 1] = chosen_ind + stripped
            open(full_path, "w", encoding="utf-8").writelines(lines)
            fix_applied = f"ALIGNED_INDENT_TO_{len(chosen_ind)}_SPACES"

        try:
            py_compile.compile(full_path, doraise=True)
            compile_ok = True
            compile_err = ""
        except py_compile.PyCompileError as exc2:
            compile_err = str(exc2.exc_value)

    return {
        "file": os.path.relpath(full_path, home_dir),
        "line_inspected": lno,
        "compile_ok": compile_ok,
        "compile_error": compile_err,
        "fix_applied": fix_applied,
        "source_context": ctx
    }


DIRECTIONAL_EDGES = [
    {"from": 8088, "to": 8154, "label": "UI -> PREDICTIVE_KERNEL_WAKE"},
    {"from": 8088, "to": 8156, "label": "UI -> REVERSE_TRACE_MIRROR"},
    {"from": 8088, "to": 8119, "label": "UI -> 4GATE_SUPERCOMPUTER_MESH"},
    {"from": 8119, "to": 8117, "label": "MESH -> AGENTIC_TRUST_ATTEST"},
    {"from": 8119, "to": 8121, "label": "MESH -> CLAUDE_CINEMA_RENOISE_MCP"},
    {"from": 8088, "to": 8115, "label": "UI -> HMAC_CRYPTO_CARD_WEBHOOKS"},
    {"from": 8115, "to": 8111, "label": "WEBHOOKS -> JEV_INVOICE_LEDGER"},
    {"from": 8088, "to": 8099, "label": "UI -> VIRTUAL_CARD_DEALERSHIP"},
    {"from": 8154, "to": 8096, "label": "KERNEL -> ON_DEMAND_TELEMETRY_SYNTH"},
    {"from": 8154, "to": 8097, "label": "KERNEL -> ON_DEMAND_COMPLIANCE_VAULT"},
    {"from": 8154, "to": 8098, "label": "KERNEL -> ON_DEMAND_QUANTUM_ROUTER"},
    {"from": 8154, "to": 8100, "label": "KERNEL -> ON_DEMAND_MEDIA_BUS"}
]

def build_global_trace_mirror(sync_code_mirrors=True):
    home_dir = os.path.expanduser("~")
    snap = build_reverse_telemetry_snapshot()
    online_set = {x["port"]: x for x in snap.get("online_details") or []}

    # Evaluate live directional edges
    traced_edges = []
    for edge in DIRECTIONAL_EDGES:
        src_p = edge["from"]
        dst_p = edge["to"]
        src_up = src_p in online_set
        dst_up = dst_p in online_set
        lat = online_set[dst_p]["latency_ms"] if dst_up else None
        traced_edges.append({
            "from": src_p,
            "to": dst_p,
            "label": edge["label"],
            "flow_active": src_up and dst_up,
            "target_state": "ONLINE" if dst_up else "STANDBY_OR_OFFLINE",
            "latency_ms": lat
        })

    # Snapshot SHA-256 mirrors of core Python modules into SQLite code_mirrors
    mirrored_files = []
    core_paths = [
        os.path.join(home_dir, "dashboard_server.py"),
        os.path.join(home_dir, "agentic_mesh_8119.py"),
        os.path.join(home_dir, "trust_center_8117.py"),
        os.path.join(home_dir, "studio_cinema_mcp_8121.py"),
        os.path.join(home_dir, "live-command-center", "predictive_kernel_8154.py"),
        os.path.join(home_dir, "live-command-center", "reverse_telemetry_8156.py")
    ]
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS code_mirrors (
        file_path TEXT PRIMARY KEY,
        sha256_hash TEXT,
        known_good_code TEXT,
        timestamp REAL
    )""")
    now = time.time()
    for fp in core_paths:
        if os.path.isfile(fp):
            try:
                py_compile.compile(fp, doraise=True)
                raw = open(fp, "r", encoding="utf-8", errors="ignore").read()
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                if sync_code_mirrors:
                    conn.execute("INSERT OR REPLACE INTO code_mirrors VALUES (?, ?, ?, ?)", (fp, digest, raw, now))
                mirrored_files.append({"file": os.path.relpath(fp, home_dir), "sha256": digest[:16], "verified": True})
            except Exception as e:
                mirrored_files.append({"file": os.path.relpath(fp, home_dir), "verified": False, "error": str(e)})
    conn.commit()
    conn.close()

    active_flows = sum(1 for e in traced_edges if e["flow_active"])
    return {
        "mirror_id": "MIR-" + uuid.uuid4().hex[:8].upper(),
        "ports_online": snap.get("ports_online"),
        "active_directional_flows": f"{active_flows}/{len(traced_edges)}",
        "directional_edges": traced_edges,
        "code_mirrors": mirrored_files,
        "reverse_traced_errors": snap.get("reverse_traced_errors") or [],
        "timestamp": now
    }

class ReverseTelemetryHandler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self._json(200, {"ok": True})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln).decode("utf-8", errors="ignore") if ln else "{}"
        data = json.loads(raw) if raw.strip() else {}
        target = str(data.get("file") or "").strip()
        line_no = int(data.get("line") or 0)
        apply_fix = bool(data.get("apply_fix", False))
        if not target:
            traces = reverse_trace_recent_errors()
            if traces:
                last_t = next(reversed(traces))
                target = last_t.get("source_file", "")
                line_no = last_t.get("line", 0)
        res = inspect_and_repair_target(target, line_no=line_no, apply_fix=apply_fix)
        self._json(200, res)

    def do_GET(self):
        if self.path.startswith("/mirror"):
            self._json(200, build_global_trace_mirror(sync_code_mirrors=True))
            return
        self._json(200, build_reverse_telemetry_snapshot())

if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("0.0.0.0", 8156), ReverseTelemetryHandler).serve_forever()
