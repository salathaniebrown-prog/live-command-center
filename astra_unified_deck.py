#!/usr/bin/env python3
"""
SalathanieAI — Unified Port 8099 Master Cockpit Router (astra_unified_deck.py)
Zero-scroll single-screen layout combining:
  - Left:   3D Jet Cockpit (8095 -> auto-failover :8125/jet-3d) with live interactive controls
  - Center: Unified Gateway (8090) + Live External Feeds (USGS / NWS / NASA EONET) & PX4 Drone Coordinates
  - Right:  Live SQLite WAL Flight-Recorder Ledger Stream (astra_flight_ledger.db)
"""
import http.server
import json
import socketserver
import time
import urllib.request

import astra_alstra_jet_bridge as bridge
import astra_flight_ledger as ledger

PORT = 8099


def _proxy(targets: list[str], method: str = "GET", body: bytes = b"") -> tuple[int, str, bytes]:
    for url in targets:
        try:
            headers = {"User-Agent": "Salathanie-Deck-8099/1.0"}
            if method == "POST":
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=(body if method == "POST" else None), headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=5.0) as r:
                return r.status, r.headers.get("Content-Type", "text/html; charset=utf-8"), r.read()
        except Exception:
            continue
    return 502, "application/json", json.dumps({"error": "upstream_down", "targets": targets}).encode("utf-8")


DECK_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>SALATHANIE AI // PORT 8099 MASTER COCKPIT DECK</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:monospace}
html,body{width:100vw;height:100vh;overflow:hidden;background:#02060f;color:#e6f7ff}
#app{display:grid;grid-template-columns:46% 27% 27%;grid-template-rows:38px 1fr;gap:5px;padding:5px;width:100vw;height:100vh}
#topbar{grid-column:1/4;display:flex;align-items:center;justify-content:space-between;background:#081428;border:1px solid #00f0ff66;border-radius:6px;padding:0 10px;font-size:11px;gap:6px;overflow:hidden}
.pane{background:#071122;border:1px solid #1c3556;border-radius:6px;display:flex;flex-direction:column;overflow:hidden;min-height:0}
.phead{background:#0b1b34;border-bottom:1px solid #1c3556;padding:4px 8px;font-size:10px;font-weight:bold;color:#38bdf8;display:flex;justify-content:space-between;align-items:center}
.pbody{flex:1;overflow:auto;padding:6px;font-size:10px;min-height:0}
.split{display:grid;grid-template-rows:44% 56%;gap:5px;min-height:0}
iframe{width:100%;height:100%;border:none;background:#02060f}
button{background:#0ea5e9;color:#02060f;border:none;padding:3px 7px;border-radius:4px;font-family:monospace;font-size:9px;font-weight:bold;cursor:pointer}
button.grn{background:#39ff14}button.amb{background:#f59e0b}button.pur{background:#a855f7;color:#fff}
.row{border-bottom:1px solid #142844;padding:4px 0}
.badge{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:bold;background:#1e3a5f;color:#7ef9ff}
.b-ok{background:#14532d;color:#4ade80}.b-warn{background:#78350f;color:#fde047}.b-err{background:#7f1d1d;color:#fca5a5}
.px4-box{background:#040b18;border:1px solid #0ea5e955;border-radius:5px;padding:5px;margin-bottom:6px}
.px4-in{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:3px;margin-top:4px}
input{background:#02060f;color:#e6f7ff;border:1px solid #2b4568;border-radius:3px;padding:3px;font-family:monospace;font-size:9px;width:100%}
</style></head><body>
<div id="app">
  <div id="topbar">
    <b>SALATHANIE AI // PORT 8099 MASTER COCKPIT DECK</b>
    <span id="topMeta" style="color:#39ff14">WAL LEDGER: SYNCING...</span>
    <div style="display:flex;gap:4px">
      <button class="grn" onclick="forceMutate()">FUSE &amp; MUTATE</button>
      <button class="amb" onclick="syncExternal()">SYNC USGS/NWS/EONET</button>
      <button class="pur" onclick="walFlush()">WAL CHECKPOINT</button>
      <button onclick="window.open('http://127.0.0.1:8125','_blank')">PILOT :8125</button>
    </div>
  </div>

  <!-- LEFT: 3D JET COCKPIT (8095 / 8125 FAILOVER) -->
  <div class="pane">
    <div class="phead"><span>1. 3D JET COCKPIT (8095 &rarr; LIVE FUSED CONTROLS)</span><span id="jetBadge" class="badge b-ok">LIVE</span></div>
    <iframe src="/proxy/jet" title="3D Jet Cockpit"></iframe>
  </div>

  <!-- CENTER: PORT 8090 GATEWAY + EXTERNAL USGS/NWS/EONET & PX4 -->
  <div class="split">
    <div class="pane">
      <div class="phead"><span>2. UNIFIED GATEWAY PROXY (:8090)</span><span class="badge">8095 + 8088</span></div>
      <iframe src="/proxy/8090" title="Port 8090 Gateway"></iframe>
    </div>
    <div class="pane">
      <div class="phead"><span>3. PX4 DRONE COORDS + USGS / NWS / EONET</span><span id="hazBadge" class="badge">HAZARD 0.0</span></div>
      <div class="pbody">
        <div class="px4-box">
          <div id="px4Live">Loading PX4 telemetry...</div>
          <div class="px4-in">
            <input id="pLat" value="36.0999" title="PX4 Lat">
            <input id="pLon" value="-80.2442" title="PX4 Lon">
            <input id="pAlt" value="120.5" title="Alt (m)">
            <button class="grn" onclick="pushPX4()">PX4 FIX</button>
          </div>
        </div>
        <div id="extList">Loading live USGS/NWS/EONET feeds...</div>
      </div>
    </div>
  </div>

  <!-- RIGHT: LIVE SQLITE WAL FLIGHT-RECORDER LEDGER -->
  <div class="pane">
    <div class="phead"><span>4. SQLITE WAL FLIGHT LEDGER (astra_flight_ledger.db)</span><span id="walBadge" class="badge b-ok">WAL OK</span></div>
    <div class="pbody" id="ledgerFeed">Connecting to WAL stream...</div>
  </div>
</div>

<script>
async function refreshDeck(){
  try{
    const d=await(await fetch('/api/ledger')).json();
    const g0=(d.generations||[])[0]||{};
    document.getElementById('topMeta').textContent=
      `GEN: ${g0.gen_id||'--'} | FIT: ${g0.fitness??'--'} | PODS: ${g0.pods_mask||'----'} | RAM: ${g0.ram_pct??'--'}% | WAL: ${d.wal.db_kb}KB`;
    document.getElementById('walBadge').textContent=`${d.totals.generations} GENS | WAL ${d.wal.wal_kb}KB`;
    const hz=document.getElementById('hazBadge');
    hz.textContent=`HAZARD ${d.hazard_score}`;
    hz.className='badge '+(d.hazard_score>=0.35?'b-err':(d.hazard_score>0.1?'b-warn':'b-ok'));

    const p=d.px4_latest||{};
    document.getElementById('px4Live').innerHTML=
      `<b style="color:#39ff14">${p.vehicle_id||'PX4'}</b> [${p.flight_mode||'--'}] (${p.source||'--'})<br>`+
      `LAT: <b>${p.lat}</b> | LON: <b>${p.lon}</b> | ALT: <b>${p.alt_m}m</b> | BAT: <b>${p.battery_pct}%</b>`;

    document.getElementById('extList').innerHTML=(d.external_feeds||[]).map(e=>{
      const cls=(e.severity==='HIGH'||e.severity==='SEVERE'||e.severity==='ALERT')?'b-warn':(e.severity==='NOMINAL'?'b-ok':'');
      return `<div class="row"><span class="badge ${cls}">${e.source}</span> <b>${e.title}</b><br><small style="color:#7dd3fc">(${Number(e.lat).toFixed(2)}, ${Number(e.lon).toFixed(2)}) • ${e.severity}</small></div>`;
    }).join('')||'No external events yet.';

    document.getElementById('ledgerFeed').innerHTML=(d.generations||[]).map(g=>{
      const t=new Date(g.ts*1000).toLocaleTimeString();
      return `<div class="row">`+
        `<b>${g.gen_id}</b> <span class="badge ${g.promoted?'b-ok':''}">${g.promoted?'PROMOTED':'HOLD'}</span> `+
        `<span style="color:#38bdf8">FIT ${g.fitness}</span> <small style="color:#94a3b8">${t}</small><br>`+
        `<small>MODE: ${g.mode} | PODS: [${g.pods_mask}] | STICK: (${g.pilot_pitch},${g.pilot_roll},T${Math.round(g.pilot_thrust*100)}%)</small><br>`+
        `<small style="color:#a5f3fc">RAM ${g.ram_pct}% (${g.mem_avail_mb}MB) | PX4 (${g.px4_lat},${g.px4_lon}) | HMAC ${g.hmac_sig}</small><br>`+
        `<small style="color:#cbd5e1">${g.reason}</small>`+
        `</div>`;
    }).join('')||'Waiting for closed-loop bridge cycle...';
  }catch(e){}
}
async function forceMutate(){
  document.getElementById('topMeta').textContent='Running 3-worker closed-loop pod+stick+ledger mutation...';
  await fetch('/api/bridge/cycle',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"sync_ext":false}'});
  refreshDeck();
}
async function syncExternal(){
  document.getElementById('topMeta').textContent='Ingesting live USGS / NWS / NASA EONET into WAL ledger...';
  await fetch('/api/external/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  refreshDeck();
}
async function walFlush(){
  await fetch('/api/wal/checkpoint',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  refreshDeck();
}
async function pushPX4(){
  await fetch('/api/px4',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    vehicle_id:'PX4-EAGLE-01',
    lat:parseFloat(document.getElementById('pLat').value),
    lon:parseFloat(document.getElementById('pLon').value),
    alt_m:parseFloat(document.getElementById('pAlt').value),
    flight_mode:'MISSION_ACTIVE', armed:true, battery_pct:94.0
  })});
  refreshDeck();
}
refreshDeck();
setInterval(refreshDeck, 2500);
</script></body></html>""".encode("utf-8")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class H(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            return self._send(200, "text/html; charset=utf-8", DECK_HTML)
        if p == "/api/ledger":
            return self._send(200, "application/json", json.dumps(ledger.get_ledger_snapshot(20)).encode("utf-8"))
        if p == "/proxy/jet":
            c, ct, data = _proxy(["http://127.0.0.1:8095/", "http://127.0.0.1:8125/jet-3d"])
            return self._send(c, ct, data)
        if p == "/proxy/8090":
            c, ct, data = _proxy(["http://127.0.0.1:8090/"])
            return self._send(c, ct, data)
        if p == "/proxy/8088":
            c, ct, data = _proxy(["http://127.0.0.1:8088/", "http://127.0.0.1:8125/"])
            return self._send(c, ct, data)
        if p in ("/api/hud", "/api/gw/status"):
            targets = ["http://127.0.0.1:8095/api/hud", "http://127.0.0.1:8125/api/hud"] if p == "/api/hud" else ["http://127.0.0.1:8090/api/gw/status"]
            c, ct, data = _proxy(targets)
            return self._send(c, ct, data)
        return self._send(404, "application/json", b'{"error":"not_found"}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(min(length, 65536)) if length else b"{}"
        p = self.path.split("?")[0]
        try:
            body = json.loads(raw.decode("utf-8", errors="ignore") or "{}")
        except Exception:
            body = {}
        if p == "/api/px4":
            return self._send(200, "application/json", json.dumps({"ok": True, "px4": ledger.record_px4(body, "px4_deck_8099")}).encode("utf-8"))
        if p == "/api/external/sync":
            return self._send(200, "application/json", json.dumps(ledger.sync_external_feeds()).encode("utf-8"))
        if p == "/api/wal/checkpoint":
            return self._send(200, "application/json", json.dumps(ledger.wal_checkpoint()).encode("utf-8"))
        if p == "/api/bridge/cycle":
            return self._send(200, "application/json", json.dumps(bridge.run_closed_loop_cycle(bool(body.get("sync_ext")))).encode("utf-8"))
        if p in ("/api/mode", "/api/pods", "/api/pilot"):
            c, ct, data = _proxy([f"http://127.0.0.1:8095{p}", f"http://127.0.0.1:8125{p}"], "POST", raw)
            return self._send(c, ct, data)
        return self._send(404, "application/json", b'{"error":"not_found"}')

    def _send(self, code, ct, data):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    with Server(("0.0.0.0", PORT), H) as srv:
        srv.serve_forever()
