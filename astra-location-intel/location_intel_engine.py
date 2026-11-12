import os, math, json, time, sqlite3, hashlib, urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-location-intel")
DB = f"{BASE}/location_intel.db"

def hav(a, b, c, d):
    p1, p2, dp, dl = math.radians(a), math.radians(c), math.radians(c-a), math.radians(d-b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return round(7917.6 * math.atan2(math.sqrt(x), math.sqrt(1-x)), 2)

def init():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS geo_nodes(node_id TEXT PRIMARY KEY, name TEXT, lat REAL, lon REAL, demand_idx REAL, predicted_roi REAL)")
    if c.execute("SELECT COUNT(*) FROM geo_nodes").fetchone() == 0:
        for r in [("GEO-GSO-HQ","Greensboro HQ",36.0726,-79.7920,0.95,1.42),("GEO-PTI-AIR","PTI Airport Hub",36.0978,-79.9373,0.91,1.38),("GEO-I85-EV","I-85 EV Corridor",36.0421,-79.8355,0.88,1.31),("GEO-HPT-01","High Point Hub",35.9557,-80.0053,0.85,1.26),("GEO-WSL-01","Winston-Salem Node",36.0999,-80.2442,0.87,1.29)]:
            c.execute("INSERT INTO geo_nodes VALUES(?,?,?,?,?,?)", r)
    c.commit(); c.close()

def wx():
    try:
        u = "https://open-meteo.com"
        cur = json.loads(urllib.request.urlopen(u, timeout=3).read().decode()).get("current", {})
        return {"city":"Greensboro, NC","temp_f":cur.get("temperature_2m",68.0),"wind_mph":cur.get("wind_speed_10m",5.0),"demand_multiplier":1.04}
    except Exception:
        return {"city":"Greensboro, NC","temp_f":68.0,"wind_mph":5.0,"demand_multiplier":1.04}

def route():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ns = [dict(r) for r in c.execute("SELECT * FROM geo_nodes").fetchall()]; c.close()
    rem, rt, mi = ns[1:], [ns], 0.0
    while rem:
        nxt = min(rem, key=lambda n: hav(rt[-1]["lat"], rt[-1]["lon"], n["lat"], n["lon"]))
        mi += hav(rt[-1]["lat"], rt[-1]["lon"], nxt["lat"], nxt["lon"])
        rt.append(nxt); rem.remove(nxt)
    mins, gas, ev = round((mi/42)*60+len(rt)*6), round((mi/24)*3.15,2), round(mi*0.34*0.13,2)
    sms = f"TRIAD ({round(mi,1)}mi|{mins}m|Gas ${gas}/EV ${ev}): " + "->".join(s["name"] for s in rt)
    return {"weather":wx(),"total_miles":round(mi,2),"est_drive_minutes":mins,"fuel_cost_usd":gas,"ev_cost_usd":ev,"sms_dispatch_text":sms,"stops":rt}

class H(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path == "/api/geo/manifest":
            rt = route(); rows = "".join(f"<tr><td>{i+1}</td><td>{s['name']}</td><td>{s['lat']},{s['lon']}</td></tr>" for i,s in enumerate(rt["stops"]))
            h = f"<html><body style='font-family:monospace;background:#040a10;color:#fff;padding:16px'><h3>TRIAD ROUTE ({rt['total_miles']} MI | {rt['est_drive_minutes']} MIN | GAS ${rt['fuel_cost_usd']} / EV ${rt['ev_cost_usd']})</h3><table border='1' cellpadding='5'>{rows}</table><button onclick='window.print()'>PRINT</button></body></html>"
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.end_headers(); self.wfile.write(h.encode())
        else:
            c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
            ns = [dict(r) for r in c.execute("SELECT * FROM geo_nodes ORDER BY demand_idx DESC").fetchall()]; c.close()
            self._j({"region":"Piedmont Triad / Greensboro, NC","weather":wx(),"nodes":ns})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
        if self.path == "/api/geo/route": self._j(route())
        elif self.path == "/api/geo/reset-stops":
            c = sqlite3.connect(DB); c.execute("DELETE FROM geo_nodes WHERE node_id NOT IN ('GEO-GSO-HQ','GEO-PTI-AIR','GEO-I85-EV','GEO-HPT-01','GEO-WSL-01')"); c.commit(); c.close()
            self._j({"status":"RESET_COMPLETE","message":"5 core Triad hubs preserved."})
        else:
            nm = d.get("name") or d.get("label") or d.get("address") or "Triad Stop"
            lt, ln = float(d.get("lat",36.0726)), float(d.get("lon",-79.7920))
            dist = hav(36.0726, -79.7920, lt, ln)
            dem = round(min(0.99, max(0.65, 0.96 - dist/150)), 4)
            cap = float(d.get("capital_usd", 50000)); rev = round(cap*(1.18 + dem*0.32), 2)
            nid = "GEO-" + hashlib.sha256(f"{nm}{time.time()}".encode()).hexdigest()[:5].upper()
            c = sqlite3.connect(DB); c.execute("INSERT OR REPLACE INTO geo_nodes VALUES(?,?,?,?,?,?)", (nid, nm, lt, ln, dem, round(rev/max(1,cap),2))); c.commit(); c.close()
            self._j({"node_id":nid,"name":nm,"lat":lt,"lon":ln,"distance_from_gso_miles":dist,"demand_score":dem,"projected_30d_value_usd":rev,"proof_hash":"0x"+hashlib.sha256(nid.encode()).hexdigest()})

init()
HTTPServer(("0.0.0.0", 8103), H).serve_forever()
