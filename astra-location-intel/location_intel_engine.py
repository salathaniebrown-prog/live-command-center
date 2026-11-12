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
        if self.path == "/api/geo/state":
            conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
            nodes = [dict(r) for r in conn.execute("SELECT * FROM geo_nodes ORDER BY demand_idx DESC").fetchall()]
            conn.close()
            self._j({"region": "Piedmont Triad / Greensboro, NC", "weather": get_live_weather(), "nodes": nodes})
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/geo/route":
            self._j(optimize_triad_route())
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
    return {"weather": wx, "total_miles": round(total_mi, 2), "stops": [{"id": n["node_id"], "name": n["name"], "lat": n["lat"], "lon": n["lon"]} for n in route]}
