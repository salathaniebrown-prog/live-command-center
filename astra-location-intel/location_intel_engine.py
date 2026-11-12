import os, math, json, time, sqlite3, hashlib, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

HOME = os.path.expanduser("~")
DB = os.path.join(HOME, "astra-location-intel", "location_intel.db")
REAL_LOG = os.path.join(HOME, "telemetry-spine", "REAL.log")

def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''CREATE TABLE IF NOT EXISTS geo_nodes(
        node_id TEXT PRIMARY KEY, name TEXT, zone TEXT, lat REAL, lon REAL,
        demand_idx REAL, infra_score REAL, predicted_roi REAL, updated_at REAL)''')
    if conn.execute("SELECT COUNT(*) FROM geo_nodes").fetchone() == 0:
        seeds = [
            ("GEO-GSO-HQ", "Greensboro Core Command Hub", "Downtown Greensboro", 36.0726, -79.7920, 0.94, 0.96, 1.42),
            ("GEO-PTI-AIR", "PTI Airport & I-40 Logistics Node", "West Greensboro / PTI", 36.0978, -79.9373, 0.91, 0.93, 1.38),
            ("GEO-I85-EV", "I-85 / Wendover Fleet & EV Corridor", "South Greensboro", 36.0421, -79.8355, 0.88, 0.89, 1.31),
            ("GEO-HPT-01", "High Point Commercial Dispatch Hub", "High Point Triad", 35.9557, -80.0053, 0.84, 0.86, 1.26),
            ("GEO-WSL-01", "Winston-Salem Innovation & Medical Node", "Winston-Salem Triad", 36.0999, -80.2442, 0.87, 0.90, 1.29)
        ]
        now = time.time()
        for nid, name, zone, lat, lon, dem, inf, roi in seeds:
            conn.execute("INSERT INTO geo_nodes VALUES(?,?,?,?,?,?,?,?,?)", (nid, name, zone, lat, lon, dem, inf, roi, now))
    conn.commit(); conn.close()

def run_predictive_model(target_name, lat, lon, capital_usd=50000.0):
    hq_lat, hq_lon = 36.0726, -79.7920
    dist_mi = haversine_miles(hq_lat, hq_lon, lat, lon)
    # Spatial gravity & corridor proximity decay model
    proximity_factor = max(0.55, round(1.0 - (dist_mi / 120.0), 4))
    demand_score = round(min(0.99, 0.72 + (proximity_factor * 0.25)), 4)
    projected_rev = round(capital_usd * (1.18 + demand_score * 0.32), 2)
    node_id = "GEO-" + hashlib.sha256(f"{target_name}:{lat}:{lon}".encode()).hexdigest()[:5].upper()
    proof = "0x" + hashlib.sha256(f"{node_id}:{projected_rev}:{time.time()}".encode()).hexdigest()

    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO geo_nodes VALUES(?,?,?,?,?,?,?,?,?)",
                 (node_id, target_name, f"{dist_mi} mi from GSO HQ", lat, lon, demand_score, proximity_factor, round(projected_rev/max(1,capital_usd), 2), time.time()))
    conn.commit(); conn.close()

    try:
        os.makedirs(os.path.dirname(REAL_LOG), exist_ok=True)
        with open(REAL_LOG, "a", encoding="utf-8") as lf:
            lf.write(json.dumps({"ts": time.time(), "source": "LOCATION_INTEL_8103", "node_id": node_id, "target": target_name, "projected_rev": projected_rev, "proof": proof}) + "\n")
    except Exception:
        pass

    return {
        "node_id": node_id, "name": target_name, "lat": lat, "lon": lon,
        "distance_from_gso_miles": dist_mi, "demand_score": demand_score,
        "projected_30d_value_usd": projected_rev, "proof_hash": proof
    }

class GeoHandler(BaseHTTPRequestHandler):
    def _j(self, d, s=200):
        self.send_response(s); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def do_GET(self):
        if self.path == "/api/geo/manifest":
            html = render_route_manifest_html().encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(html); return
        if self.path == "/api/geo/state":
            conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
            nodes = [dict(r) for r in conn.execute("SELECT * FROM geo_nodes ORDER BY demand_idx DESC").fetchall()]
            conn.close()
            self._j({"region": "Piedmont Triad / Greensboro, NC", "weather": get_live_weather(), "nodes": nodes})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/geo/route":
            rt = optimize_triad_route(); dispatch_route_alert(rt); self._j(rt)
        elif self.path == "/api/geo/reset-stops":
            self._j(reset_custom_stops())
        elif self.path == "/api/geo/add-stop":
            self._j(geocode_triad_address(d.get("label", "Client Stop"), d.get("address", "Greensboro, NC")))
        elif self.path == "/api/geo/predict":
            self._j(run_predictive_model(
                d.get("name", "Triad Expansion Node"),
                float(d.get("lat", 36.0850)),
                float(d.get("lon", -79.8200)),
                float(d.get("capital_usd", 50000))
            ))

if __name__ == "__main__":
    init_db()
    HTTPServer(("0.0.0.0", 8103), GeoHandler).serve_forever()

def get_live_weather():
    try:
        url = "https://open-meteo.com"
        data = json.loads(urllib.request.urlopen(url, timeout=4).read().decode())
        cur = data.get("current", {})
        temp = cur.get("temperature_2m", 68.0)
        wind = cur.get("wind_speed_10m", 5.0)
        precip = cur.get("precipitation", 0.0)
        weather_mult = 1.12 if precip > 0 else 1.04
        return {"city": "Greensboro, NC", "temp_f": temp, "wind_mph": wind, "precip_in": precip, "demand_multiplier": weather_mult}
    except Exception:
        return {"city": "Greensboro, NC", "temp_f": 68.0, "wind_mph": 5.0, "precip_in": 0.0, "demand_multiplier": 1.04}

def optimize_triad_route():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    nodes = [dict(r) for r in conn.execute("SELECT * FROM geo_nodes").fetchall()]
    conn.close()
    if not nodes:
        return {"stops": [], "total_miles": 0}
    unvisited = nodes[1:]
    route = [nodes]
    total_mi = 0.0
    while unvisited:
        curr = route[-1]
        nxt = min(unvisited, key=lambda n: haversine_miles(curr["lat"], curr["lon"], n["lat"], n["lon"]))
        total_mi += haversine_miles(curr["lat"], curr["lon"], nxt["lat"], nxt["lon"])
        route.append(nxt)
        unvisited.remove(nxt)
    wx = get_live_weather()
    est_minutes = round((total_mi / 42.0) * 60 + (len(route) * 6))
    fuel_cost_usd = round((total_mi / 24.0) * 3.15, 2)
    ev_kwh_cost_usd = round((total_mi * 0.34) * 0.13, 2)
    stop_list = " -> ".join(f"{i+1}.{n['name']}" for i, n in enumerate(route))
    sms_text = f"TRIAD DISPATCH ({round(total_mi,1)} mi | ~{est_minutes} min | Gas ${fuel_cost_usd} / EV ${ev_kwh_cost_usd}): {stop_list}"
    return {
        "weather": wx, "total_miles": round(total_mi, 2),
        "est_drive_minutes": est_minutes, "fuel_cost_usd": fuel_cost_usd, "ev_cost_usd": ev_kwh_cost_usd,
        "sms_dispatch_text": sms_text,
        "stops": [{"id": n["node_id"], "name": n["name"], "lat": n["lat"], "lon": n["lon"]} for n in route]
    }

def geocode_triad_address(label, address_query):
    lat, lon = 36.0726, -79.7920
    try:
        q = urllib.parse.quote(f"{address_query}, North Carolina")
        req = urllib.request.Request(f"https://openstreetmap.org{q}&format=json&limit=1", headers={"User-Agent": "Astra-Location-Intel/1.0"})
        res = json.loads(urllib.request.urlopen(req, timeout=5).read().decode())
        if res:
            lat, lon = float(res["lat"]), float(res["lon"])
    except Exception:
        pass
    return run_predictive_model(label or address_query, lat, lon, 35000.0)

def dispatch_route_alert(route_data):
    wx = route_data.get("weather", {})
    msg = f"Triad Route ({route_data.get('total_miles')} mi) | GSO {wx.get('temp_f')}F | Stops: {len(route_data.get('stops', []))}"
    try:
        os.makedirs(os.path.dirname(REAL_LOG), exist_ok=True)
        with open(REAL_LOG, "a", encoding="utf-8") as lf:
            lf.write(json.dumps({"ts": time.time(), "source": "GEO_DISPATCH_8103", "alert": msg, "stops": route_data.get("stops", [])}) + "\n")
    except Exception:
        pass
    try:
        rq = urllib.request.Request("http://127.0.0", data=b"{}", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(rq, timeout=2)
    except Exception:
        pass

def reset_custom_stops():
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM geo_nodes WHERE node_id NOT IN ('GEO-GSO-HQ','GEO-PTI-AIR','GEO-I85-EV','GEO-HPT-01','GEO-WSL-01')")
    conn.commit(); conn.close()
    return {"status": "RESET_COMPLETE", "message": "Custom client stops cleared; 5 core Triad hubs preserved."}

def render_route_manifest_html():
    rt = optimize_triad_route()
    wx = rt.get("weather", {})
    rows = "".join(
        f"<tr><td>{i+1}</td><td>{s['id']}</td><td>{s['name']}</td><td>{s['lat']:.4f}, {s['lon']:.4f}</td></tr>"
        for i, s in enumerate(rt.get("stops", []))
    )
    ts = time.strftime("%Y-%m-%d %H:%M EST")
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Piedmont Triad Field Dispatch Manifest</title>
<style>
  body{{font-family:monospace;background:#040a10;color:#e6f9ff;padding:20px}}
  .box{{max-width:780px;margin:auto;border:2px solid #00f0ff;background:#071420;padding:22px}}
  h1{{color:#39ff14;font-size:17px;margin:0 0 8px}}
  table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:12px}}
  th,td{{border:1px solid #00f0ff44;padding:8px;text-align:left}}
  th{{background:#0b2236;color:#00f0ff}}
  button{{padding:8px 16px;background:#39ff1422;border:1px solid #39ff14;color:#39ff14;font-family:monospace;font-weight:bold;cursor:pointer}}
  @media print{{button{{display:none}}body{{background:#fff;color:#000}}.box{{border-color:#000;background:#fff}}th,td{{border-color:#000}}}}
</style></head><body><div class="box">
  <h1>PIEDMONT TRIAD FIELD DISPATCH &amp; ROUTE MANIFEST</h1>
  <div>GENERATED: {ts} | TOTAL ROUTE: <strong>{rt.get('total_miles')} MILES</strong> (~{rt.get('est_drive_minutes')} MIN) | EST COST: <strong>${rt.get('fuel_cost_usd')} GAS</strong> / <strong>${rt.get('ev_cost_usd')} EV</strong></div>
  <div>GREENSBORO WEATHER: <strong>{wx.get('temp_f')}°F</strong> | WIND: {wx.get('wind_mph')} MPH | DEMAND MULT: {wx.get('demand_multiplier')}x</div>
  <table><thead><tr><th>STOP #</th><th>NODE ID</th><th>LOCATION / CLIENT</th><th>COORDINATES</th></tr></thead><tbody>{rows}</tbody></table>
  <button onclick="window.print()">PRINT / SAVE DISPATCH SHEET (PDF)</button> <a href="sms:?body={urllib.parse.quote(rt.get('sms_dispatch_text',''))}" style="display:inline-block;padding:8px 14px;margin-left:8px;border:1px solid #00f0ff;color:#00f0ff;text-decoration:none;font-weight:bold">SEND VIA MOBILE SMS</a>
</div></body></html>"""
