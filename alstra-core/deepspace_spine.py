import asyncio
import json
import sqlite3
import time
import multiprocessing
import os
import http.client
import hashlib
import subprocess
import google.generativeai as genai
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn
from skyfield.api import EarthSatellite, load
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
DB_NAME = "deepspace_core.db"

# --- SECURE CONFIGURATION ---
# Pull the key from the environment file. 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("[!] CRITICAL: GEMINI_API_KEY not found in .env file.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')

# Load Permanent Sovereign Keys
try:
    with open("alstra_private_key.pem", "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
except FileNotFoundError:
    print("[!] KEYS NOT FOUND. RUN generate_keys.py FIRST.")
    exit()

stress_processes = []
is_stressing = False
last_hash = "GENESIS_BLOCK_00000000000000000000000000000000"

def cpu_worker():
    while True:
        pass

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS deep_space_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            payload TEXT,
            prev_hash TEXT,
            block_hash TEXT,
            signature TEXT
        )
    ''')
    conn.commit()
    conn.close()

def fetch_deep_space_telemetry():
    try:
        name = "JAMES WEBB SPACE TELESCOPE"
        tle1 = "1 50463U 21130A   23324.50000000  .00000000  00000-0  00000-0 0  9999"
        tle2 = "2 50463  10.1234  45.6789 0000000  00.0000 000.0000  1.00000000    10"
        
        ts = load.timescale()
        t = ts.now()
        satellite = EarthSatellite(tle1, tle2, name, ts)
        geocentric = satellite.at(t)
        distance_km = geocentric.distance().km
        
        return {
            "name": name,
            "status": "DEEP SPACE LOCK",
            "altitude_km": f"{distance_km:,.2f}",
            "velocity_kms": "1.02"
        }
    except Exception as e:
        return {"name": "DEEP SPACE OFFLINE", "error": str(e), "altitude_km": "N/A", "velocity_kms": "N/A"}

def get_max_cpu_telemetry():
    cpu_freq = "N/A"
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "r") as f:
            freq_khz = int(f.read().strip())
            cpu_freq = f"{freq_khz / 1000000:.2f}"
    except:
        cpu_freq = "LOCKED"

    return {
        "cpu_percent": "100% (MAX)" if is_stressing else "ACTIVE",
        "cpu_cores": multiprocessing.cpu_count(),
        "cpu_freq": cpu_freq,
        "is_stressing": is_stressing
    }

def sign_and_log(payload_dict):
    global last_hash
    payload_str = json.dumps(payload_dict)
    block_data = last_hash + payload_str
    block_hash = hashlib.sha256(block_data.encode()).hexdigest()
    sig = private_key.sign(block_hash.encode())
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cursor.execute(
        "INSERT INTO deep_space_ledger (timestamp, payload, prev_hash, block_hash, signature) VALUES (?, ?, ?, ?, ?)",
        (timestamp, payload_str, last_hash, block_hash, sig.hex())
    )
    conn.commit()
    conn.close()
    
    last_hash = block_hash
    return {"block_hash": block_hash, "signature": sig.hex()}

@app.post("/ask_jeti")
async def ask_jeti(request: dict):
    user_query = request.get("query", "")
    
    sat_data = fetch_deep_space_telemetry()
    cpu_data = get_max_cpu_telemetry()
    
    prompt = f"""
    You are Jeti, the AI co-pilot of the Alstra Sovereign Deep Space Command Center.
    Current Telemetry: Tracking {sat_data['name']} at {sat_data['altitude_km']} km distance.
    Hardware Status: CPU Load is {cpu_data['cpu_percent']} at {cpu_data['cpu_freq']} GHz.
    Authority: Salathaniel S A Brown Sr.
    
    User Query: {user_query}
    
    Respond in a brief, highly tactical, sci-fi AI voice (max 2 sentences). Do not use markdown.
    """
    
    try:
        response = ai_model.generate_content(prompt)
        ai_text = response.text.replace("*", "").strip()
        
        try:
            subprocess.Popen(["termux-tts-speak", ai_text], stderr=subprocess.DEVNULL)
        except Exception:
            pass
            
        return {"response": ai_text}
    except Exception as e:
        return {"response": f"AI Core Error: {str(e)}"}

@app.post("/toggle_stress")
async def toggle_stress():
    global is_stressing, stress_processes
    if not is_stressing:
        cores = multiprocessing.cpu_count()
        for _ in range(cores + 2):
            p = multiprocessing.Process(target=cpu_worker)
            p.daemon = True
            p.start()
            stress_processes.append(p)
        is_stressing = True
    else:
        for p in stress_processes:
            p.terminate()
        stress_processes.clear()
        is_stressing = False
    return {"status": "TOGGLED"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        sat_data = fetch_deep_space_telemetry()
        cpu_data = get_max_cpu_telemetry()
        
        telemetry = {
            "satellite": sat_data,
            "hardware": cpu_data,
            "nonce": int(time.time() * 1000)
        }
        
        crypto_data = sign_and_log(telemetry)
        telemetry["crypto"] = crypto_data
        
        try:
            await websocket.send_text(json.dumps(telemetry))
        except:
            break
            
        await asyncio.sleep(1)

@app.get("/")
async def get():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "hud.html")
    return HTMLResponse(open(html_path).read())

if __name__ == "__main__":
    init_db()
    os.environ['SKYFIELD_DOWNLOAD'] = 'false' 
    uvicorn.run(app, host="0.0.0.0", port=5000)
