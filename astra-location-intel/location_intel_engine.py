import os, math, json, time, sqlite3, hashlib, urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser("~/astra-location-intel")
DB = f"{BASE}/location_intel.db"

def hav(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)

def init_db():
    os.makedirs(BASE, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS geo_nodes(node_id TEXT PRIMARY KEY, name TEXT, lat REAL, lon REAL, demand_idx REAL, predicted_roi REAL)")
    if c.execute("SELECT COUNT(*) FROM geo_nodes").fetchone()[0] == 0:
        for nid, nm, lt, ln, dm, roi in [
            ("GEO-GSO-HQ", "Greensboro Core Command Hub", 36.0726, -79.7920, 0.95, 1.42),
            ("GEO-PTI-AIR", "PTI Airport & I-40 Logistics", 36.0978, -79.9373, 0.91, 1.38),
            ("GEO-I85-EV", "I-85 / Wendover Fleet Corridor", 36.0421, -79.8355, 0.88, 1.31),
            ("GEO-HPT-01", "High Point Commercial Hub", 35.9557, -80.0053, 0.85, 1.26),
            ("GEO-WSL-01", "Winston-Salem Innovation Node", 36.0999, -80.2442, 0.87, 1.29)
        ]:
            c.execute("INSERT INTO geo_nodes VALUES(?,?,?,?,?,?)", (nid, nm, lt, ln, dm, roi))
    c.commit(); c.close()

def live_wx():
    try:
        u = "https://open-meteo.com"
        cur = json.loads(urllib.request.urlopen(u, timeout=3).read().decode()).get("current", {})
        return {"city": "Greensboro, NC", "temp_f": cur.get("temperature_2m", 68.0), "wind_mph": cur.get("wind_speed_10m", 5.0), "demand_multiplier": 1.12 if cur.get("precipitation", 0) > 0 else 1.04}
    except Exception:
        return {"city": "Greensboro, NC", "temp_f": 68.0, "wind_mph": 5.0, "demand_multiplier": 1.04}

def build_route():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    nodes = [dict(r) for r in c.execute("SELECT * FROM geo_nodes").fetchall()]
    c.close()
    if not nodes: return {"stops": [], "total_miles": 0}
    rem, rt, mi = nodes[1:], [nodes[0]], 0.0
    while rem:
        nxt = min(rem, key=lambda n: hav(rt[-1]["lat"], rt[-1]["lon"], n["lat"], n["lon"]))
        mi += hav(rt[-1]["lat"], rt[-1]["lon"], nxt["lat"], nxt["lon"])
        rt.append(nxt); rem.remove(nxt)
    mins = round((mi / 42.0) * 60 + len(rt) * 6)
    gas, ev = round((mi / 24.0) * 3.15, 2), round((mi * 0.34) * 0.13, 2)
    sms = f"TRIAD DISPATCH ({round(mi,1)} mi | ~{mins}m | Gas ${gas} / EV ${ev}): " + " -> ".join(f"{i+1}.{s['name']}" for i, s in enumerate(rt))
    return {"weather": live_wx(), "total_miles": round(mi, 2), "est_drive_minutes": mins, "fuel_cost_usd": gas, "ev_cost_usd": ev, "sms_dispatch_text": sms, "stops": rt}

class H(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path == "/api/geo/state":
            c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
            ns = [dict(r) for r in c.execute("SELECT * FROM geo_nodes ORDER BY demand_idx DESC").fetchall()]
            c.close()
            self._j({"region": "Piedmont Triad / Greensboro, NC", "weather": live_wx(), "nodes": ns})
        elif self.path == "/api/geo/manifest":
            rt = build_route(); wx = rt.get("weather", {})
            rows = "".join(f"<tr><td>{i+1}</td><td>{s['name']}</td><td>{s['lat']:.4f},{s['lon']:.4f}</td></tr>" for i, s in enumerate(rt["stops"]))
            html = f"<!DOCTYPE html><html><body style='font-family:monospace;background:#040a10;color:#e6f9ff;padding:20px'><h2>TRIAD DISPATCH MANIFEST ({rt['total_miles']} MI | ~{rt['est_drive_minutes']} MIN | GAS ${rt['fuel_cost_usd']} / EV ${rt['ev_cost_usd']})</h2><div>GREENSBORO WEATHER: {wx.get('temp_f')}F</div><table border='1' cellpadding='6' style='border-collapse:collapse;width:100%;margin:12px 0'><tr><th>#</th><th>STOP</th><th>COORDS</th></tr>{rows}</table><button onclick='window.print()'>PRINT PDF</button></body></html>"
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(html.encode())
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/geo/route":
            self._j(build_route())
        elif self.path == "/api/geo/reset-stops":
            c = sqlite3.connect(DB)
            c.execute("DELETE FROM geo_nodes WHERE node_id NOT IN ('GEO-GSO-HQ','GEO-PTI-AIR','GEO-I85-EV','GEO-HPT-01','GEO-WSL-01')")
            c.commit(); c.close()
            self._j({"status": "RESET_COMPLETE", "message": "Custom stops cleared; 5 core Triad hubs preserved."})
        elif self.path in ("/api/geo/predict", "/api/geo/add-stop"):
            nm = d.get("name") or d.get("label") or d.get("address") or "Triad Expansion Node"
            lt, ln = float(d.get("lat", 36.0726)), float(d.get("lon", -79.7920))
            if "address" in d and "lat" not in d:
                try:
                    q = urllib.parse.quote(f"{d['address']}, North Carolina")
rq = urllib.request.Request(f"openstreetmap.org{q}&format=json&limit=1", headers={"User-Agent": "Astra-Geo/1.0"})
res = json.loads(urllib.request.urlopen(rq, timeout=4).read().decode())
if res: lt, ln = float(res[0]["lat"]), float(res[0]["lon"])
except Exception: pass
dist = hav(36.0726, -79.7920, lt, ln)
dem = round(min(0.99, max(0.65, 0.96 - dist / 150.0)), 4)
cap = float(d.get("capital_usd", 50000))
rev = round(cap * (1.18 + dem * 0.32), 2)
nid = "GEO-" + hashlib.sha256(f"{nm}{lt}{ln}".encode()).hexdigest()[:5].upper()
ph = "0x" + hashlib.sha256(f"{nid}{rev}".encode()).hexdigest()
c = sqlite3.connect(DB)
c.execute("INSERT OR REPLACE INTO geo_nodes VALUES(?,?,?,?,?,?)", (nid, nm, lt, ln, dem, round(rev/max(1,cap), 2)))
c.commit(); c.close()
self._j({"node_id": nid, "name": nm, "lat": lt, "lon": ln, "distance_from_gso_miles": dist, "demand_score": dem, "projected_30d_value_usd": rev, "proof_hash": ph})
if name == "main":
init_db()
HTTPServer(("0.0.0.0", 8103), H).serve_forever()
