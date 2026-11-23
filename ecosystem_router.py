#!/usr/bin/env python3
"""
SalathanieAI — Zero-RAM Multi-Folder Vault & On-Demand Launcher for :8090
Exposes:
  - GET  /ecosystem                  -> Unified interactive folder, vault & launcher UI
  - GET  /api/ecosystem/status       -> Live RAM %, PM2 state & folder registry JSON
  - GET  /vault/<folder>/<filename>  -> Serves HTML/assets from any mapped folder (0 MB extra RAM)
  - POST /api/ecosystem/control      -> Start/Stop on-demand workers with 82% RAM hard guard
"""
import json
import mimetypes
import subprocess
from pathlib import Path
from urllib.parse import unquote

HOME = Path.home()
REPO = HOME / "live-command-center"
REGISTRY_JSON = REPO / "salathanie_ondemand_registry.json"
RAM_GUARD_PCT = 82.0


def _ram_pct() -> float:
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(":")] = int(parts[1])
        tot = mem.get("MemTotal", 1)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        return round(((tot - avail) / max(1, tot)) * 100.0, 1)
    except Exception:
        return 0.0


def _pm2_status_map() -> dict:
    out = {}
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip().startswith("["):
            for p in json.loads(r.stdout):
                nm = p.get("name", "")
                env = p.get("pm2_env") or {}
                mem_mb = round(((p.get("monit") or {}).get("memory", 0)) / (1024 * 1024), 1)
                if nm:
                    out[nm] = {"status": env.get("status", "unknown"), "mem_mb": mem_mb, "restarts": env.get("restart_time", 0)}
    except Exception:
        pass
    return out


def _load_registry() -> dict:
    if REGISTRY_JSON.exists():
        try:
            return json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"core_names": [], "folders": [], "ondemand_services": []}


def _send(handler, code: int, body: bytes, ctype: str):
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _render_ui() -> bytes:
    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SALATHANIE AI // UNIFIED ECOSYSTEM</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,-apple-system,sans-serif}
  body{background:#060b14;color:#e2f1ff;padding:12px}
  .bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;border-bottom:1px solid #16304d;padding-bottom:10px;margin-bottom:12px}
  .ram{font-weight:800;padding:4px 10px;border-radius:99px;background:#0b3b35;color:#34f5c5;font-size:13px}
  .ram.warn{background:#4c1d1d;color:#fca5a5}
  .links a{display:inline-block;text-decoration:none;font-size:12px;font-weight:700;padding:5px 9px;border-radius:6px;background:#102238;color:#c9ecff;border:1px solid #1e4268;margin:2px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
  .card{background:#0b1524;border:1px solid #1a3554;border-radius:10px;padding:12px}
  .card h3{font-size:14px;color:#52d1ff;margin-bottom:6px;word-break:break-all}
  .row{display:flex;justify-content:space-between;align-items:center;gap:6px;padding:4px 0;border-top:1px solid #12263f;font-size:12px}
  button{cursor:pointer;border:none;border-radius:5px;padding:4px 8px;font-size:11px;font-weight:700}
  .btn-go{background:#0b5c4d;color:#d8fff6}
  .btn-stop{background:#7f1d1d;color:#fee2e2}
  .tag{font-size:11px;color:#93b4d4}
  #msg{font-size:12px;color:#34f5c5;margin-bottom:8px;min-height:16px}
</style></head><body>
<div class="bar">
  <div><strong>SALATHANIE AI // UNIFIED ECOSYSTEM (RAM-SAFE)</strong></div>
  <div id="ram_badge" class="ram">RAM: --%</div>
</div>
<div class="links" style="margin-bottom:10px">
  <a href="http://127.0.0.1:8088/">:8088 OMEGA</a>
  <a href="http://127.0.0.1:8090/flying-car">:8090 Flying Car</a>
  <a href="http://127.0.0.1:8090/avatars">:8090 Avatars</a>
  <a href="http://127.0.0.1:8090/jet">:8090 3D Jet</a>
  <a href="http://127.0.0.1:8132/">:8132 Car HUD</a>
</div>
<div id="msg"></div>
<div id="folders" class="grid">Loading unified ecosystem...</div>
<script>
async function ctl(action, name){
  document.getElementById('msg').textContent = action.toUpperCase() + ' ' + name + '...';
  const r = await fetch('/api/ecosystem/control', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action, name})});
  const d = await r.json();
  document.getElementById('msg').textContent = d.ok ? ('[OK] ' + d.message) : ('[BLOCKED] ' + (d.error || 'failed'));
  load();
}
async function load(){
  const r = await fetch('/api/ecosystem/status');
  const d = await r.json();
  const rb = document.getElementById('ram_badge');
  rb.textContent = 'RAM: ' + d.ram_pct + '% (Guard ' + d.ram_guard_pct + '%)';
  rb.className = 'ram' + (d.ram_pct >= d.ram_guard_pct ? ' warn' : '');
  const pm = d.pm2 || {};
  const wrap = document.getElementById('folders');
  wrap.innerHTML = '';
  for(const f of (d.registry.folders || [])){
    let h = '<div class="card"><h3>' + f.folder + '</h3>';
    if((f.html_files || []).length){
      h += '<div class="links" style="margin-bottom:6px">';
      for(const hf of f.html_files){
        h += '<a target="_blank" href="/vault/' + encodeURIComponent(f.folder) + '/' + encodeURIComponent(hf) + '">HUD: ' + hf + '</a>';
      }
      h += '</div>';
    }
    if((f.db_files || []).length){
      h += '<div class="tag" style="margin-bottom:6px">WAL/DBs: ' + f.db_files.join(', ') + '</div>';
    }
    for(const s of (f.services || [])){
      const st = pm[s.name] ? (pm[s.name].status + ' ' + pm[s.name].mem_mb + 'MB') : 'parked (0MB)';
      const online = pm[s.name] && pm[s.name].status === 'online';
      h += '<div class="row"><span>' + s.file + '<br><span class="tag">' + st + '</span></span>'
        + (online ? '<button class="btn-stop" onclick="ctl(\\'stop\\',\\''+s.name+'\\')">Park</button>'
                  : '<button class="btn-go" onclick="ctl(\\'start\\',\\''+s.name+'\\')">Wake</button>')
        + '</div>';
    }
    h += '</div>';
    wrap.innerHTML += h;
  }
}
load(); setInterval(load, 6000);
</script></body></html>"""
    return html.encode("utf-8")


def handle_get(handler) -> bool:
    p = (getattr(handler, "path", "") or "").split("?", 1)[0]
    if p == "/ecosystem":
        _send(handler, 200, _render_ui(), "text/html; charset=utf-8")
        return True
    if p == "/api/ecosystem/status":
        payload = {"ok": True, "ram_pct": _ram_pct(), "ram_guard_pct": RAM_GUARD_PCT, "pm2": _pm2_status_map(), "registry": _load_registry()}
        _send(handler, 200, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")
        return True
    if p.startswith("/vault/"):
        parts = [unquote(x) for x in p[len("/vault/"):].split("/", 1)]
        if len(parts) == 2 and ".." not in parts[0] and ".." not in parts[1]:
            folder, fname = parts
            base = HOME if folder == "__home__" else (HOME / folder)
            fp = (base / fname).resolve()
            if str(fp).startswith(str(HOME.resolve())) and fp.is_file():
                ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
                _send(handler, 200, fp.read_bytes(), ctype)
                return True
        _send(handler, 404, b"Vault file not found", "text/plain; charset=utf-8")
        return True
    return False


def handle_post(handler, body: bytes) -> bool:
    p = (getattr(handler, "path", "") or "").split("?", 1)[0]
    if p != "/api/ecosystem/control":
        return False
    try:
        req = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        req = {}
    action = str(req.get("action") or "").lower()
    name = str(req.get("name") or "")
    reg = _load_registry()
    svc = next((s for s in reg.get("ondemand_services", []) if s["name"] == name), None)
    if not svc:
        _send(handler, 404, json.dumps({"ok": False, "error": f"Unknown service: {name}"}).encode("utf-8"), "application/json")
        return True

    if action == "start":
        ram = _ram_pct()
        if ram >= RAM_GUARD_PCT:
            _send(handler, 200, json.dumps({"ok": False, "error": f"RAM at {ram}% (>= {RAM_GUARD_PCT}% guard). Park an idle service first."}).encode("utf-8"), "application/json")
            return True
        subprocess.run(["pm2", "delete", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([
            "pm2", "start", svc["script"], "--name", name, "--interpreter", "python3",
            "--cwd", svc["cwd"], "--max-memory-restart", svc.get("max_memory_restart", "64M"),
            "--max-restarts", "5", "--min-uptime", "10s",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _send(handler, 200, json.dumps({"ok": True, "message": f"Started {name} ({svc['file']})"}).encode("utf-8"), "application/json")
        return True

    if action == "stop":
        subprocess.run(["pm2", "stop", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _send(handler, 200, json.dumps({"ok": True, "message": f"Parked {name} (0 MB)"}).encode("utf-8"), "application/json")
        return True

    _send(handler, 400, json.dumps({"ok": False, "error": "Invalid action"}).encode("utf-8"), "application/json")
    return True
