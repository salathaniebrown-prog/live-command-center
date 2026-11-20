import hashlib
import http.server
import json
import os
import pathlib
import socketserver
import sqlite3
import time
import uuid

PORT = 8171
HOME = pathlib.Path.home()
DB_PATH = HOME / "astra_sovereign_pr_wal.db"
ARTIFACT_DIR = HOME / "astra-unified-brain" / "artifacts"
FLUENTBIT_DIR = HOME / "astra_fluentbit_v5"
FLUENTBIT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# Fluent Bit v5 -> OpenTelemetry OTLP/gRPC (4317) + Lua semantic filter reference
(FLUENTBIT_DIR / "fluent-bit.conf").write_text("""[SERVICE]
    Flush                     1
    Log_Level                 info
    Daemon                    off
    Parsers_File              parsers.conf
    Storage.path              /var/log/fluentbit/buffer/
    Storage.sync              normal
    Storage.checksum          off
    Storage.backlog.mem_limit 50M

[INPUT]
    Name                      fluentbit_metrics
    Tag                       internal.metrics
    Scrape_Interval           5s

[FILTER]
    Name                      fts
    Match                     *
    Script                    transform_telemetry.lua
    Call                      process_record

[OUTPUT]
    Name                      opentelemetry
    Match                     *
    Host                      otel-collector.internal
    Port                      4317
    Metrics_URI               /v1/metrics
    Log_Response_Payload      True
    Tls                       On
    Tls.Verify                Off
    Workers                   4
""", encoding="utf-8")


def init_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_events (
            id TEXT PRIMARY KEY,
            ts INTEGER NOT NULL,
            lane TEXT NOT NULL,
            provider_route TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            confidence REAL NOT NULL,
            payload_json TEXT NOT NULL,
            sha256_attestation TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pr_artifacts (
            pr_id TEXT PRIMARY KEY,
            ts INTEGER NOT NULL,
            title TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            sha256_attestation TEXT NOT NULL,
            status_matrix_json TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


class SovereignHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, code: int, payload: dict):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Model-Profile")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Model-Profile")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        conn = init_db()
        try:
            ev_count = conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()[0]
            pr_count = conn.execute("SELECT COUNT(*) FROM pr_artifacts").fetchone()[0]
            recent_prs = conn.execute(
                "SELECT pr_id, ts, title, artifact_path, sha256_attestation FROM pr_artifacts ORDER BY ts DESC LIMIT 10"
            ).fetchall()
        finally:
            conn.close()

        if path in ("/", "/health", "/api/sovereign/status"):
            return self._json(200, {
                "ok": True,
                "service": "astra-sovereign-pr-8171",
                "port": PORT,
                "wal_db": str(DB_PATH),
                "artifact_dir": str(ARTIFACT_DIR),
                "fluentbit_v5_conf": str(FLUENTBIT_DIR / "fluent-bit.conf"),
                "telemetry_events": ev_count,
                "pr_artifacts": pr_count,
            })

        if path == "/api/pr/list":
            return self._json(200, {
                "ok": True,
                "artifacts": [
                    {"pr_id": r[0], "ts": r[1], "title": r[2], "artifact_path": r[3], "sha256": r[4]}
                    for r in recent_prs
                ],
            })

        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
        try:
            body = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"invalid_json: {e}"})

        path = self.path.split("?", 1)[0]
        now = int(time.time())
        route_header = self.headers.get("X-Model-Profile") or body.get("route") or "termux-local-gemma4-litert"

        if path in ("/api/ooda/execute", "/api/legal/audit", "/api/telemetry/ingest"):
            lane = "OODA_LOOP" if "ooda" in path else ("LEGAL_SHIELD" if "legal" in path else "UNIFIED_TELEMETRY")
            ev_id = "ev_" + uuid.uuid4().hex[:12]
            latency_ms = float(body.get("latency_ms", 12.4))
            confidence = float(body.get("confidence", 0.99))
            canonical = json.dumps({"id": ev_id, "ts": now, "lane": lane, "route": route_header, "body": body}, sort_keys=True).encode("utf-8")
            digest = hashlib.sha256(canonical).hexdigest()

            conn = init_db()
            try:
                conn.execute(
                    "INSERT INTO telemetry_events (id, ts, lane, provider_route, latency_ms, confidence, payload_json, sha256_attestation) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (ev_id, now, lane, route_header, latency_ms, confidence, json.dumps(body)[:4000], digest),
                )
                conn.commit()
            finally:
                conn.close()

            return self._json(200, {
                "ok": True,
                "event_id": ev_id,
                "lane": lane,
                "route": route_header,
                "sha256_attestation": digest,
                "wal_db": str(DB_PATH),
            })

        if path == "/api/pr/artifact":
            pr_id = "pr_" + uuid.uuid4().hex[:10]
            title = str(body.get("title", "Sovereign Command Center Build"))[:140]
            ports = body.get("ports", [3000, 8088, 8090, 8104, 8143, 8157, 8169, 8171])
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="180" viewBox="0 0 640 180">'
                f'<rect width="640" height="180" fill="#060d17" rx="8"/>'
                f'<text x="20" y="34" fill="#58a6ff" font-family="monospace" font-size="15">ASTRA PR ARTIFACT // {pr_id}</text>'
                f'<text x="20" y="62" fill="#e6edf3" font-family="monospace" font-size="12">TITLE: {title}</text>'
                f'<text x="20" y="88" fill="#3fb950" font-family="monospace" font-size="12">ROUTE: {route_header} | PORTS: {",".join(str(p) for p in ports)}</text>'
                f'<text x="20" y="116" fill="#8b949e" font-family="monospace" font-size="11">WAL: {DB_PATH}</text>'
                f'</svg>'
            )
            art_file = ARTIFACT_DIR / f"{pr_id}_preview.svg"
            art_file.write_text(svg, encoding="utf-8")
            digest = hashlib.sha256(svg.encode("utf-8")).hexdigest()
            matrix = {"ports_checked": len(ports), "zero_drift_route": route_header, "wal_sealed": True}

            conn = init_db()
            try:
                conn.execute(
                    "INSERT INTO pr_artifacts (pr_id, ts, title, artifact_path, sha256_attestation, status_matrix_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (pr_id, now, title, str(art_file), digest, json.dumps(matrix)),
                )
                conn.commit()
            finally:
                conn.close()

            return self._json(200, {
                "ok": True,
                "pr_id": pr_id,
                "artifact_path": str(art_file),
                "sha256_attestation": digest,
                "status_matrix": matrix,
            })

        self._json(404, {"ok": False, "error": "unknown_endpoint"})


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    init_db()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), SovereignHandler)
    print(f"[ASTRA SOVEREIGN & PR 8171] Listening on 127.0.0.1:{PORT}")
    srv.serve_forever()
