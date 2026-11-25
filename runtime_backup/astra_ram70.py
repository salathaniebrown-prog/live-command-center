import gc, os, time, sqlite3, subprocess

TARGET_PCT = 70.0
POLL_SEC = 10
DB_PATH = "/data/data/com.termux/files/home/astra_state.db"
PROTECTED = ("astra_3stream.py", "astra_ram70.py", "dashboard_server.py", "shm_port_monitor.py", "telemetry_assistant.py", "astra_live_backend.py", "sshd", "bash", "tmux", "python3 -", "py_compile", "alstra_master_spine_8095.py", "alstra_genius_brain_8099.py")

def get_ram_pct():
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(":")] = int(parts[1])
    total = mem.get("MemTotal", 1)
    avail = mem.get("MemAvailable", mem.get("MemFree", 0))
    return round(((total - avail) / total) * 100, 1)

def trim_memory():
    gc.collect()
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=2)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.execute("PRAGMA shrink_memory;")
            conn.close()
        except Exception:
            pass

    # Terminate non-protected duplicate/orphan python or node workers if over ceiling
    out = subprocess.getoutput("ps -eo pid,args")
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        pid, cmd = parts
        if any(p in cmd for p in PROTECTED):
            continue
        if ("python" in cmd or "node" in cmd) and " defunct" not in cmd:
            try:
                # ASTRA_GRACE_45S
                if (time.time() - os.stat(f'/proc/{pid}').st_mtime) < 45:
                    continue
                os.kill(int(pid), 15)
            except Exception:
                pass

if __name__ == "__main__":
    while True:
        usage = get_ram_pct()
        if usage >= TARGET_PCT:
            trim_memory()
            after = get_ram_pct()
            print(f"[TRIM] RAM {usage}% -> {after}% (Target <={TARGET_PCT}%)", flush=True)
        time.sleep(POLL_SEC)
