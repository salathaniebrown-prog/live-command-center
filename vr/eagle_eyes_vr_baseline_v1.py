import os
import sys
import gc
import time
import sqlite3
import threading
import urllib.request
import urllib.error
import json
import ctypes

import pyglet
from pyglet.gl import *

# ==============================================================================
# ENVIRONMENT MECHANICS & CORE WATCHDOG DETECTION
# ==============================================================================
try:
    import psutil
    PROCESS = psutil.Process(os.getpid())
except ImportError:
    PROCESS = None

try:
    import xr
    from xr.constants import XR_CURRENT_API_VERSION
    OPENXR_AVAILABLE = True
except (ImportError, NameError):
    xr = None
    XR_CURRENT_API_VERSION = None
    OPENXR_AVAILABLE = False

# ==============================================================================
# UNIFIED GLOBAL STRUCTURAL HEALTH STATE MATRICES
# ==============================================================================
SYSTEM_STATE = {
    "db_alive": False,
    "feed_freshness": "NEVER_UPDATED",
    "feed_source": "NONE",
    "memory_rss_mb": 0.0,
    "memory_growth_mb": 0.0,
    "render_fps": 0.0,
    "xr_runtime_status": "DISCONNECTED",
    "active_nws_alerts": 0,
    "active_usgs_quakes": 0,
    "active_nasa_events": 0,
    "last_error": "NONE",
    "watchdog_cycles": 0,
    "network_throttled": "NOMINAL"
}

DB_PATH = "eagle_eyes_baseline.db"
LOCK = threading.Lock()
STOP_EVENT = threading.Event()

POLL_INTERVAL_SECONDS = 30.0
WATCH_GROWTH_MB = 100.0
ABSOLUTE_MEMORY_LIMIT_MB = 250.0

STARTUP_MEMORY_MB = (
    PROCESS.memory_info().rss / (1024 * 1024)
    if PROCESS else 0.0
)

NWS_URL = "https://api.weather.gov/alerts/active"
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
NASA_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100"

# ==============================================================================
# STATE HELPERS
# ==============================================================================
def set_error(message):
    with LOCK:
        SYSTEM_STATE["last_error"] = str(message)[:300]

def snapshot_state():
    with LOCK:
        return dict(SYSTEM_STATE)

# ==============================================================================
# ISOLATED TRANSACTION STORAGE SYSTEM
# ==============================================================================
def initialize_database():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_log (
                    timestamp REAL PRIMARY KEY,
                    metric_type TEXT NOT NULL,
                    value_json TEXT NOT NULL
                )
            """)
        conn.close()

        with LOCK:
            SYSTEM_STATE["db_alive"] = True
    except Exception as e:
        with LOCK:
            SYSTEM_STATE["db_alive"] = False
        set_error(f"DB_INIT_FAIL: {e}")

def persist_snapshot(snapshot):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO telemetry_log
                (timestamp, metric_type, value_json)
                VALUES (?, ?, ?)
                """,
                (
                    time.time(),
                    "LIVE_SNAPSHOT",
                    json.dumps(snapshot, separators=(",", ":"))
                )
            )
        conn.close()
    except Exception as e:
        set_error(f"DB_WRITE_FAIL: {e}")

def pull_cached_state_fallback():
    """Restore the last known snapshot but mark it explicitly as stale cache."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT value_json
            FROM telemetry_log
            WHERE metric_type = 'LIVE_SNAPSHOT'
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False

        data = json.loads(row[0])

        with LOCK:
            SYSTEM_STATE["active_nws_alerts"] = int(data.get("nws", 0))
            SYSTEM_STATE["active_usgs_quakes"] = int(data.get("usgs", 0))
            SYSTEM_STATE["active_nasa_events"] = int(data.get("nasa", 0))
            SYSTEM_STATE["feed_freshness"] = "STALE_CACHE"
            SYSTEM_STATE["feed_source"] = "LOCAL_SQLITE_CACHE"
            SYSTEM_STATE["network_throttled"] = "RESTORED_FROM_CACHE"

        return True
    except Exception as e:
        set_error(f"CACHE_RESTORE_FAIL: {e}")
        return False

# ==============================================================================
# RESILIENT ASYNCHRONOUS DATA PIPELINE
# ==============================================================================
def fetch_json_safely(url, source_name):
    """Return parsed JSON or None while recording rate/error state."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EagleEyesVR/1.0 (read-only telemetry baseline)",
                "Accept": "application/json, application/geo+json"
            }
        )

        with urllib.request.urlopen(req, timeout=5.0) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8"))

        return data

    except urllib.error.HTTPError as e:
        with LOCK:
            if e.code == 429:
                SYSTEM_STATE["network_throttled"] = f"{source_name}_RATE_LIMITED_429"
            else:
                SYSTEM_STATE["network_throttled"] = f"{source_name}_HTTP_ERR_{e.code}"
        set_error(f"{source_name}_HTTP_{e.code}")
        return None

    except urllib.error.URLError as e:
        with LOCK:
            SYSTEM_STATE["network_throttled"] = f"{source_name}_DISCONNECTED"
        set_error(f"{source_name}_URL_FAIL: {e.reason}")
        return None

    except Exception as e:
        with LOCK:
            SYSTEM_STATE["network_throttled"] = f"{source_name}_TIMEOUT_DISCONNECT"
        set_error(f"{source_name}_FETCH_FAIL: {e}")
        return None

def count_nws(data):
    if isinstance(data, dict) and isinstance(data.get("features"), list):
        return len(data["features"])
    return None

def count_usgs(data):
    if isinstance(data, dict) and isinstance(data.get("features"), list):
        return len(data["features"])
    return None

def count_nasa(data):
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return len(data["events"])
    return None

def memory_watchdog():
    if not PROCESS:
        return

    try:
        current_mb = PROCESS.memory_info().rss / (1024 * 1024)
        growth_mb = max(0.0, current_mb - STARTUP_MEMORY_MB)

        with LOCK:
            SYSTEM_STATE["memory_rss_mb"] = round(current_mb, 2)
            SYSTEM_STATE["memory_growth_mb"] = round(growth_mb, 2)

        critical = (
            current_mb >= ABSOLUTE_MEMORY_LIMIT_MB
            or growth_mb >= WATCH_GROWTH_MB
        )

        if critical:
            with LOCK:
                SYSTEM_STATE["watchdog_cycles"] += 1

            gc.collect()

            if sys.platform.startswith("linux"):
                try:
                    libc = ctypes.CDLL(None)
                    trim = getattr(libc, "malloc_trim", None)
                    if trim is not None:
                        trim(0)
                except Exception:
                    pass

    except Exception as e:
        set_error(f"MEMORY_WATCHDOG_FAIL: {e}")

def live_telemetry_pipeline_spine():
    """Read-only background ingest with truthful cache fallback."""
    initialize_database()

    while not STOP_EVENT.is_set():
        with LOCK:
            SYSTEM_STATE["network_throttled"] = "NOMINAL"

        nws_data = fetch_json_safely(NWS_URL, "NWS")
        usgs_data = fetch_json_safely(USGS_URL, "USGS")
        nasa_data = fetch_json_safely(NASA_URL, "NASA_EONET")

        successful_sources = 0

        nws_count = count_nws(nws_data)
        usgs_count = count_usgs(usgs_data)
        nasa_count = count_nasa(nasa_data)

        with LOCK:
            if nws_count is not None:
                SYSTEM_STATE["active_nws_alerts"] = nws_count
                successful_sources += 1

            if usgs_count is not None:
                SYSTEM_STATE["active_usgs_quakes"] = usgs_count
                successful_sources += 1

            if nasa_count is not None:
                SYSTEM_STATE["active_nasa_events"] = nasa_count
                successful_sources += 1

        if successful_sources == 0:
            pull_cached_state_fallback()
        else:
            now_iso = time.strftime(
                "%Y-%m-%d %H:%M:%S %Z",
                time.localtime()
            )

            with LOCK:
                SYSTEM_STATE["feed_freshness"] = now_iso
                SYSTEM_STATE["feed_source"] = f"LIVE_{successful_sources}_OF_3"
                state_copy = {
                    "nws": SYSTEM_STATE["active_nws_alerts"],
                    "usgs": SYSTEM_STATE["active_usgs_quakes"],
                    "nasa": SYSTEM_STATE["active_nasa_events"],
                    "freshness": now_iso,
                }

            if snapshot_state()["db_alive"]:
                persist_snapshot(state_copy)

        memory_watchdog()

        STOP_EVENT.wait(POLL_INTERVAL_SECONDS)

# ==============================================================================
# OPENXR DETECTION & DESKTOP GRAPHICS PIPELINE
# ==============================================================================
class EagleEyesVRBaseline:
    """
    Desktop-safe Eagle Eyes HUD.

    OpenXR is detected but native XR rendering is not falsely claimed unless a
    valid graphics binding/session lifecycle is established. This baseline
    deliberately stays in desktop mode rather than creating an invalid OpenXR
    session without a graphics binding.
    """

    def __init__(self):
        self.xr_active = False
        self.instance = None
        self.session = None
        self.space = None
        self.swapchain = None

        with LOCK:
            SYSTEM_STATE["xr_runtime_status"] = (
                "OPENXR_MODULE_AVAILABLE_DESKTOP_RENDER"
                if OPENXR_AVAILABLE
                else "DESKTOP_EMULATION_FALLBACK"
            )

        self.window = pyglet.window.Window(
            width=1150,
            height=850,
            caption="Eagle Eyes VR Baseline v1",
            resizable=True
        )

        self.last_frame_time = time.time()
        self.fps_smoothed = 0.0

        self.lbl_headline = pyglet.text.Label(
            "",
            font_name="Courier New",
            font_size=16,
            bold=True,
            color=(0, 255, 120, 255),
            x=30,
            y=805,
            anchor_x="left",
            anchor_y="top"
        )

        self.lbl_telemetry = pyglet.text.Label(
            "",
            font_name="Courier New",
            font_size=12,
            color=(0, 200, 255, 255),
            x=30,
            y=710,
            width=1080,
            multiline=True,
            anchor_x="left",
            anchor_y="top"
        )

        self.lbl_diagnostics = pyglet.text.Label(
            "",
            font_name="Courier New",
            font_size=11,
            color=(255, 215, 0, 255),
            x=30,
            y=485,
            width=1080,
            multiline=True,
            anchor_x="left",
            anchor_y="top"
        )

        @self.window.event
        def on_draw():
            self.execute_render_pipeline()

        @self.window.event
        def on_resize(width, height):
            self.lbl_headline.y = height - 30
            self.lbl_telemetry.y = height - 125
            self.lbl_diagnostics.y = height - 350

        @self.window.event
        def on_close():
            STOP_EVENT.set()

    def execute_render_pipeline(self):
        current_time = time.time()
        delta = max(1e-6, current_time - self.last_frame_time)
        self.last_frame_time = current_time

        instantaneous_fps = 1.0 / delta
        if self.fps_smoothed <= 0:
            self.fps_smoothed = instantaneous_fps
        else:
            self.fps_smoothed = (
                self.fps_smoothed * 0.90
                + instantaneous_fps * 0.10
            )

        with LOCK:
            SYSTEM_STATE["render_fps"] = round(self.fps_smoothed, 1)
            state = dict(SYSTEM_STATE)

        glClearColor(0.015, 0.020, 0.025, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        self.lbl_headline.text = (
            "EAGLE EYES // VR BASELINE v1 // OBSERVATION-ONLY"
        )

        self.lbl_telemetry.text = (
            f"LIVE INTELLIGENCE\n"
            f"  NWS ACTIVE ALERTS : {state['active_nws_alerts']}\n"
            f"  USGS QUAKES       : {state['active_usgs_quakes']}\n"
            f"  NASA EONET EVENTS : {state['active_nasa_events']}\n"
            f"  FEED FRESHNESS    : {state['feed_freshness']}\n"
            f"  FEED SOURCE       : {state['feed_source']}\n"
            f"  NETWORK STATE     : {state['network_throttled']}"
        )

        self.lbl_diagnostics.text = (
            f"SYSTEM DIAGNOSTICS\n"
            f"  DATABASE          : {'ONLINE' if state['db_alive'] else 'OFFLINE'}\n"
            f"  MEMORY RSS        : {state['memory_rss_mb']:.2f} MB\n"
            f"  MEMORY GROWTH     : {state['memory_growth_mb']:.2f} MB\n"
            f"  WATCHDOG CYCLES   : {state['watchdog_cycles']}\n"
            f"  RENDER FPS        : {state['render_fps']:.1f}\n"
            f"  XR STATUS         : {state['xr_runtime_status']}\n"
            f"  LAST ERROR        : {state['last_error']}\n\n"
            f"TRUTH POLICY\n"
            f"  Simulation        : OFF\n"
            f"  Cache fallback    : Explicitly marked STALE_CACHE\n"
            f"  Vehicle authority : NONE"
        )

        self.lbl_headline.draw()
        self.lbl_telemetry.draw()
        self.lbl_diagnostics.draw()

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
def main():
    initialize_database()

    telemetry_thread = threading.Thread(
        target=live_telemetry_pipeline_spine,
        daemon=True,
        name="eagle-eyes-telemetry"
    )
    telemetry_thread.start()

    app = EagleEyesVRBaseline()

    try:
        pyglet.app.run()
    finally:
        STOP_EVENT.set()
        telemetry_thread.join(timeout=2.0)

if __name__ == "__main__":
    main()
