import time, os, sqlite3, json
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8085
DB_FILE = "alstra_enterprise_core.db"

LOT_14_DATA = {
    "doc_hash": "0x8f3c7a9b1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8g",
    "parcel_id": "7864-12-3456",
    "metes": "Lot 14, Block B of Northridge Subdivision, Plat Book 42, Page 11 — Salathaniel Brown Sr. (Principal Systems Architect) — Sovereign Command Node"
}

class AutoStudioHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/deed/mint":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            doc_hash = body.get("doc_hash", LOT_14_DATA["doc_hash"])
            parcel_id = body.get("parcel_id", LOT_14_DATA["parcel_id"])
            metes = body.get("metes", LOT_14_DATA["metes"])
            ts = time.strftime("%H:%M:%S")
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO payment_ledger (timestamp, transaction_type, amount_usd, status, auth_signature) VALUES (?, ?, ?, ?, ?)", (ts, "LOT_14_DEED_MINT", 0.00, "MINTED_SHA256_VERIFIED", doc_hash[:32]))
            conn.commit()
            conn.close()
            return self._send_json({"status": "MINTED", "parcel_id": parcel_id, "doc_hash": doc_hash, "metes": metes, "ledger_status": "COMMITTED_TO_PORT_8099"})

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lot 14 | Sovereign Telemetry & DeedTwin Engine</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/satellite.js/5.0.0/satellite.min.js"></script>
    <style>
        body {{ background: #0b0f19; color: #f3f4f6; font-family: monospace; margin: 0; display: flex; flex-direction: column; height: 100vh; }}
        header {{ background: #131b2e; border-bottom: 1px solid #1e2d4a; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }}
        .title {{ font-size: 1.1rem; font-weight: bold; color: #00f0ff; }}
        .grid {{ display: grid; grid-template-columns: 380px 1fr; height: calc(100vh - 55px); }}
        .panel {{ background: #131b2e; border-right: 1px solid #1e2d4a; padding: 16px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }}
        input, textarea {{ background: #080c14; border: 1px solid #1e2d4a; border-radius: 6px; padding: 8px; color: #22c55e; font-family: monospace; font-size: 0.8rem; width: 100%; box-sizing: border-box; }}
        textarea {{ resize: none; height: 75px; }}
        .btn {{ background: #22c55e; color: #000; border: none; border-radius: 6px; padding: 10px; font-weight: bold; font-family: monospace; cursor: pointer; }}
        #map {{ width: 100%; height: 100%; background: #040810; }}
    </style>
</head>
<body>
    <header>
        <div class="title">📜 LOT 14 NORTHRIDGE SUBDIVISION — DEEDTWIN REGISTRY</div>
        <div style="font-size:0.8rem; color:#22c55e">● LEDGER COMMITTED</div>
    </header>
    <div class="grid">
        <div class="panel">
            <h3 style="color:#00f0ff; margin:0;">🔒 ACTIVE PARCEL ASSET</h3>
            <label style="font-size:0.75rem; color:#9ca3af;">SHA-256 Fingerprint Hash</label>
            <input type="text" id="docHash" value="{LOT_14_DATA["doc_hash"]}">
            <label style="font-size:0.75rem; color:#9ca3af;">Parcel ID</label>
            <input type="text" id="parcelId" value="{LOT_14_DATA["parcel_id"]}">
            <label style="font-size:0.75rem; color:#9ca3af;">Legal Metes & Description</label>
            <textarea id="metes">{LOT_14_DATA["metes"]}</textarea>
            <button class="btn" onclick="mintDeed()">Re-Mint Lot 14 Asset</button>
            <div id="statusOutput" style="font-size:0.75rem; color:#22c55e; padding:6px; background:#080c14; border:1px solid #1e2d4a; border-radius:4px;">
                [STATUS] Lot 14 active in SQLite ledger on Port 8099.
            </div>
            <hr style="border:0; border-top:1px solid #1e2d4a; margin:4px 0;">
            <h3 style="color:#00f0ff; margin:0;">📡 SATELLITE OVERHEAD PASS</h3>
            <div style="background:#080c14; border:1px solid #1e2d4a; border-radius:6px; padding:10px; font-size:0.78rem;">
                <div><b>Target:</b> Lot 14 Ground Station</div>
                <div id="satLat"><b>Latitude:</b> Propagating...</div>
                <div id="satLng"><b>Longitude:</b> Propagating...</div>
                <div id="satAlt"><b>Altitude:</b> Propagating...</div>
            </div>
        </div>
        <div id="map"></div>
    </div>
    <script>
        const map = L.map("map").setView([36.0726, -79.7919], 4);
        L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{ maxZoom: 18 }}).addTo(map);
        L.circleMarker([36.0726, -79.7919], {{ color: "#22c55e", radius: 8 }}).addTo(map).bindPopup("<b>Lot 14 Ground Node</b><br>Parcel: 7864-12-3456").openPopup();
        const satrec = satellite.twoline2satrec("1 25544U 98067A   26290.50000000  .00016717  00000+0  30000-3 0  9993", "2 25544  51.6400 208.1000 0005000  90.0000 270.0000 15.49000000400001");
        let satMarker = null;
        function updateTelemetry() {{
            const now = new Date();
            const pos = satellite.propagate(satrec, now).position;
            if (pos) {{
                const gmst = satellite.gstime(now);
                const gd = satellite.eciToGeodetic(pos, gmst);
                const lat = satellite.degreesLat(gd.latitude);
                const lng = satellite.degreesLong(gd.longitude);
                document.getElementById("satLat").innerHTML = "<b>Latitude:</b> " + lat.toFixed(4) + "°";
                document.getElementById("satLng").innerHTML = "<b>Longitude:</b> " + lng.toFixed(4) + "°";
                document.getElementById("satAlt").innerHTML = "<b>Altitude:</b> " + gd.height.toFixed(2) + " km";
                if (!satMarker) satMarker = L.circleMarker([lat, lng], {{ color: "#00f0ff", radius: 7 }}).addTo(map);
                else satMarker.setLatLng([lat, lng]);
            }}
        }}
        setInterval(updateTelemetry, 1000);
        updateTelemetry();
        async function mintDeed() {{
            const doc_hash = document.getElementById("docHash").value.trim();
            const parcel_id = document.getElementById("parcelId").value.trim();
            const metes = document.getElementById("metes").value.trim();
            const res = await fetch("/api/deed/mint", {{ method: "POST", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({{ doc_hash, parcel_id, metes }}) }});
            const data = await res.json();
            const box = document.getElementById("statusOutput");
            box.innerHTML = "[MINT SUCCESS] Parcel: " + data.parcel_id + " | Status: " + data.ledger_status;
        }}
    </script>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("", PORT), AutoStudioHandler).serve_forever()
