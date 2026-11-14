import os
# Auto-healed broken syntax stub
self.send_header("Access-Control-Allow-Origin", "*")
self.end_headers()
self.wfile.write(json.dumps(data).encode("utf-8"))

def do_GET(self):
        if self.path == "/api/nexus/state":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            ideas = [dict(r) for r in conn.execute("SELECT * FROM ideas ORDER BY created_at DESC LIMIT 12").fetchall()]
            skills = [dict(r) for r in conn.execute("SELECT * FROM evolved_skills ORDER BY upgraded_at DESC LIMIT 6").fetchall()]
            proofs = [dict(r) for r in conn.execute("SELECT * FROM proving_telemetry ORDER BY recorded_at DESC LIMIT 5").fetchall()]
            conn.close()
            self._json({
                "model_arch": "177B Sparse-MoE Transformer (Zero-Disk Streaming)",
                "gpu_topology": GPU_SHARDS,
                "ideas": ideas,
                "evolved_skills": skills,
                "proving_telemetry": proofs
            })

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length)) if length else {}
                if self.path == "/api/nexus/crossover":
                    self._json(crossover_ideas(payload.get("idea_a", "IDEA-01"), payload.get("idea_b", "IDEA-02"), payload.get("goal", "")))
                elif self.path == "/api/nexus/evolve":
                    self._json(self_improve_assistant(payload.get("goal", "Upgrade autonomous crypto & fleet telemetry skills")))
                elif self.path == "/api/nexus/add_idea":
                    title = payload.get("title", "New Operator Concept")
                    dom = payload.get("domain", "CUSTOM")
                    text = payload.get("payload", title)
                    iid = "IDEA-" + hashlib.sha256(f"{title}:{time.time()}".encode()).hexdigest()[:5].upper()
                    ph = "0x" + hashlib.sha256(f"{iid}:{text}".encode()).hexdigest()
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("INSERT INTO ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (iid, title, dom, text, 1, "OPERATOR", ph, time.time()))
                    conn.commit()
                    conn.close()
                    emit_proving_telemetry("IDEA_NODE_SEEDED", ["GPU-6"], {"idea_id": iid, "title": title})
                    self._json({"status": "SEEDED", "idea_id": iid, "title": title})

if __name__ == "__main__":
    init_db()
    threading.Thread(target=self_evolution_daemon, daemon=True).start()
    print("[🚀] 177B 8-GPU Nexus Online at http://127.0.0.1:8100")
    HTTPServer(("0.0.0.0", 8100), NexusHandler).serve_forever()
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/nexus/state":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            ideas = [dict(r) for r in conn.execute("SELECT * FROM ideas ORDER BY created_at DESC LIMIT 12").fetchall()]
            skills = [dict(r) for r in conn.execute("SELECT * FROM evolved_skills ORDER BY upgraded_at DESC LIMIT 6").fetchall()]
            proofs = [dict(r) for r in conn.execute("SELECT * FROM proving_telemetry ORDER BY recorded_at DESC LIMIT 5").fetchall()]
            conn.close()
            self._json({
                "model_arch": "177B Sparse-MoE Transformer (Zero-Disk Streaming)",
                "gpu_topology": GPU_SHARDS,
                "ideas": ideas,
                "evolved_skills": skills,
                "proving_telemetry": proofs
            })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/api/nexus/crossover":
            self._json(crossover_ideas(payload.get("idea_a", "IDEA-01"), payload.get("idea_b", "IDEA-02"), payload.get("goal", "")))
        elif self.path == "/api/nexus/evolve":
            self._json(self_improve_assistant(payload.get("goal", "Upgrade autonomous crypto & fleet telemetry skills")))
        elif self.path == "/api/nexus/add_idea":
            title = payload.get("title", "New Operator Concept")
            dom = payload.get("domain", "CUSTOM")
            text = payload.get("payload", title)
            iid = "IDEA-" + hashlib.sha256(f"{title}:{time.time()}".encode()).hexdigest()[:5].upper()
            ph = "0x" + hashlib.sha256(f"{iid}:{text}".encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (iid, title, dom, text, 1, "OPERATOR", ph, time.time()))
            conn.commit()
            conn.close()
            emit_proving_telemetry("IDEA_NODE_SEEDED", ["GPU-6"], {"idea_id": iid, "title": title})
            self._json({"status": "SEEDED", "idea_id": iid, "title": title})

if __name__ == "__main__":
    init_db()
    threading.Thread(target=self_evolution_daemon, daemon=True).start()
    print("[🚀] 177B 8-GPU Nexus Online at http://127.0.0.1:8100")
    HTTPServer(("0.0.0.0", 8100), NexusHandler).serve_forever()
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/nexus/state":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            ideas = [dict(r) for r in conn.execute("SELECT * FROM ideas ORDER BY created_at DESC LIMIT 12").fetchall()]
            skills = [dict(r) for r in conn.execute("SELECT * FROM evolved_skills ORDER BY upgraded_at DESC LIMIT 6").fetchall()]
            proofs = [dict(r) for r in conn.execute("SELECT * FROM proving_telemetry ORDER BY recorded_at DESC LIMIT 5").fetchall()]
            conn.close()
            self._json({
                "model_arch": "177B Sparse-MoE Transformer (Zero-Disk Streaming)",
                "gpu_topology": GPU_SHARDS,
                "ideas": ideas,
                "evolved_skills": skills,
                "proving_telemetry": proofs
            })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/api/nexus/crossover":
            self._json(crossover_ideas(payload.get("idea_a", "IDEA-01"), payload.get("idea_b", "IDEA-02"), payload.get("goal", "")))
        elif self.path == "/api/nexus/evolve":
            self._json(self_improve_assistant(payload.get("goal", "Upgrade autonomous crypto & fleet telemetry skills")))
        elif self.path == "/api/nexus/add_idea":
            title = payload.get("title", "New Operator Concept")
            dom = payload.get("domain", "CUSTOM")
            text = payload.get("payload", title)
            iid = "IDEA-" + hashlib.sha256(f"{title}:{time.time()}".encode()).hexdigest()[:5].upper()
            ph = "0x" + hashlib.sha256(f"{iid}:{text}".encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (iid, title, dom, text, 1, "OPERATOR", ph, time.time()))
            conn.commit()
            conn.close()
            emit_proving_telemetry("IDEA_NODE_SEEDED", ["GPU-6"], {"idea_id": iid, "title": title})
            self._json({"status": "SEEDED", "idea_id": iid, "title": title})

if __name__ == "__main__":
    init_db()
    threading.Thread(target=self_evolution_daemon, daemon=True).start()
    print("[🚀] 177B 8-GPU Nexus Online at http://127.0.0.1:8100")
    HTTPServer(("0.0.0.0", 8100), NexusHandler).serve_forever()
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/nexus/state":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            ideas = [dict(r) for r in conn.execute("SELECT * FROM ideas ORDER BY created_at DESC LIMIT 12").fetchall()]
            skills = [dict(r) for r in conn.execute("SELECT * FROM evolved_skills ORDER BY upgraded_at DESC LIMIT 6").fetchall()]
            proofs = [dict(r) for r in conn.execute("SELECT * FROM proving_telemetry ORDER BY recorded_at DESC LIMIT 5").fetchall()]
            conn.close()
            self._json({
                "model_arch": "177B Sparse-MoE Transformer (Zero-Disk Streaming)",
                "gpu_topology": GPU_SHARDS,
                "ideas": ideas,
                "evolved_skills": skills,
                "proving_telemetry": proofs
            })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/api/nexus/crossover":
            self._json(crossover_ideas(payload.get("idea_a", "IDEA-01"), payload.get("idea_b", "IDEA-02"), payload.get("goal", "")))
        elif self.path == "/api/nexus/evolve":
            self._json(self_improve_assistant(payload.get("goal", "Upgrade autonomous crypto & fleet telemetry skills")))
        elif self.path == "/api/nexus/add_idea":
            title = payload.get("title", "New Operator Concept")
            dom = payload.get("domain", "CUSTOM")
            text = payload.get("payload", title)
            iid = "IDEA-" + hashlib.sha256(f"{title}:{time.time()}".encode()).hexdigest()[:5].upper()
            ph = "0x" + hashlib.sha256(f"{iid}:{text}".encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (iid, title, dom, text, 1, "OPERATOR", ph, time.time()))
            conn.commit()
            conn.close()
            emit_proving_telemetry("IDEA_NODE_SEEDED", ["GPU-6"], {"idea_id": iid, "title": title})
            self._json({"status": "SEEDED", "idea_id": iid, "title": title})

if __name__ == "__main__":
    init_db()
    threading.Thread(target=self_evolution_daemon, daemon=True).start()
    print("[🚀] 177B 8-GPU Nexus Online at http://127.0.0.1:8100")
    HTTPServer(("0.0.0.0", 8100), NexusHandler).serve_forever()
