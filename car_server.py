import asyncio, json, subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from car_core import load_state, sync_all

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:monospace}
body{background:#03080d;color:#0ff;height:100vh;overflow:hidden;display:grid;grid-template-rows:38px 1fr 48px;gap:5px;padding:5px}
.box{border:1px solid #0ff5;background:#05101a;padding:5px;overflow:hidden}
.top{display:flex;justify-content:space-between;align-items:center;font-size:11px;border-bottom:2px solid #0ff}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;height:100%}
.list{height:calc(100% - 16px);overflow-y:auto;font-size:10px}
.row{display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #0ff2}
.ONLINE{color:#0f8;font-weight:bold}.OFFLINE{color:#f35;font-weight:bold}
.btns{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}
button{background:#062133;color:#0ff;border:1px solid #0ff;font-size:10px;font-weight:bold}
</style></head><body>
<div class="box top"><span id="m">UPGRADE: JET-CRUISE</span><span id="v">290KTS | 2500FT</span><span id="u">UPGRADE ACTIVE</span></div>
<div class="grid">
  <div class="box"><b>UPGRADE PORTS</b><div class="list" id="p"></div></div>
  <div class="box"><b>UPGRADE NODES</b><div class="list" id="s"></div></div>
</div>
<div class="box btns">
  <button onclick="cmd({mode:'JET-CRUISE',airspeed_kts:290,altitude_ft:2500})">CRUISE</button>
  <button onclick="cmd({mode:'HOVER-VTOL',airspeed_kts:35,altitude_ft:450})">HOVER</button>
  <button onclick="cmd({mode:'EV-GROUND',airspeed_kts:65,altitude_ft:0})">GROUND</button>
  <button onclick="cmd({revive:1})">REVIVE</button>
</div>
<script>
async function tick(){
  let r=await fetch('/api/flying-car/step'),d=await r.json();
  document.getElementById('m').innerText='UPGRADE: '+d.mode;
  document.getElementById('v').innerText=d.airspeed_kts+'KTS | '+d.altitude_ft+'FT';
  document.getElementById('p').innerHTML=Object.entries(d.nodes).map(([k,v])=>`<div class="row"><span>${k}:${v.port}</span><span class="${v.status}">${v.status}</span></div>`).join('');
  document.getElementById('s').innerHTML=Object.entries(d.pm2).map(([k,v])=>`<div class="row"><span>${k}</span><span class="${v}">${v}</span></div>`).join('');
}
async function cmd(b){await fetch('/api/flying-car/step',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});tick();}
setInterval(tick,1500);tick();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/api/flying-car/step"):
            st = asyncio.run(sync_all(load_state()))
            body = json.dumps(st).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        st = load_state()
        if ln:
            d = json.loads(self.rfile.read(ln))
            for k in ("mode", "airspeed_kts", "altitude_ft", "heading", "kw_output", "livery"):
                if k in d: st[k] = d[k]
        st = asyncio.run(sync_all(st))
        body = json.dumps(st).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

print("UPGRADE SERVER LISTENING ON 8899")
ThreadingHTTPServer(("127.0.0.1", 8899), Handler).serve_forever()
