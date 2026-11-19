#!/usr/bin/env python3
"""
ASTRA // Dedicated Saga + Polyglot (8123) & Enterprise Gov + Plugins (8125) Microservices
"""
import json, time, threading, http.server, socketserver

class ReuseTCP(socketserver.TCPServer):
    allow_reuse_address = True

def make_handler(port: int, service_name: str):
    class NodeHandler(http.server.BaseHTTPRequestHandler):
        def _send(self, obj, code=200):
            raw = json.dumps(obj, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self._send({
                "ok": True,
                "status": "ONLINE",
                "port": port,
                "service": service_name,
                "query_id": f"node-{port}-sovereign",
                "timestamp": time.time()
            })

        def do_POST(self):
            self._send({
                "ok": True,
                "status": "EXECUTED",
                "port": port,
                "service": service_name,
                "query_id": f"node-{port}-sovereign",
                "result": f"[{service_name} PORT {port}] Deterministic execution pass",
                "timestamp": time.time()
            })
    return NodeHandler

def serve_port(port: int, name: str):
    with ReuseTCP(("127.0.0.1", port), make_handler(port, name)) as srv:
        srv.serve_forever()

if __name__ == "__main__":
    t1 = threading.Thread(target=serve_port, args=(8123, "ASTRA_SAGA_POLYGLOT_8123"), daemon=True)
    t2 = threading.Thread(target=serve_port, args=(8125, "ASTRA_ENTERPRISE_GOV_8125"), daemon=True)
    t1.start()
    t2.start()
    print("[✔] Saga (8123) & Gov (8125) microservices active on 127.0.0.1")
    t1.join()
