#!/data/data/com.termux/files/usr/bin/bash
cp "$HOME/dashboard_server.py" "$HOME/dashboard_server.py.bak.$(date +%s)"

python3 - << 'PY'
with open("/data/data/com.termux/files/home/dashboard_server.py", "r") as f:
    src = f.read()

old_block = """    def _proxy(self):
        H = ".".join(["127","0","0","1"])
        port = next((p for k, p in ROUTES.items() if self.path.startswith(k)), None)
        if not port: return False
        sub = self.path.replace("/dealership", "", 1) or "/" """.rstrip()

new_block = """    def _proxy(self):
        import re as _re
        H = ".".join(["127","0","0","1"])
        m = _re.match(r"^/p/(\\d+)(/.*)?$", self.path)
        if m:
            port = int(m.group(1))
            sub = m.group(2) or "/"
        else:
            port = next((p for k, p in ROUTES.items() if self.path.startswith(k)), None)
            if not port: return False
            sub = self.path.replace("/dealership", "", 1) or "/" """.rstrip()

assert old_block in src, "Target _proxy block not found!"
src = src.replace(old_block, new_block, 1)

if "allow_reuse_address" not in src:
    src = src.replace(
        'http.server.ThreadingHTTPServer(("0.0.0.0", 8088), UnifiedHandler).serve_forever()',
        'http.server.ThreadingHTTPServer.allow_reuse_address = True\n    http.server.ThreadingHTTPServer(("0.0.0.0", 8088), UnifiedHandler).serve_forever()'
    )

with open("/data/data/com.termux/files/home/dashboard_server.py", "w") as f:
    f.write(src)
print("PATCHED_OK")
PY

echo "=== Checking port 8088 owner ==="
ps -ef | grep -E "8088|node|python|cloudflared" | grep -v grep
