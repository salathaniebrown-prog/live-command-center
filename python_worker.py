import json, time, math, os, sqlite3, subprocess, threading
from concurrent.futures import ThreadPoolExecutor

DB = "astra_ledger.db"
conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, detail TEXT, val REAL)")
conn.commit()
db_lock = threading.Lock()

def log_db(kind, detail, val=0.0):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with db_lock:
        conn.execute("INSERT INTO ledger (ts, kind, detail, val) VALUES (?, ?, ?, ?)", (ts, kind, detail, val))
        conn.commit()
    with open("telemetry_spine.jsonl", "a") as f:
        f.write(json.dumps({"ts": ts, "source": kind, "status": detail, "val": val}) + "\n")

def get_temp_c():
    try:
        out = subprocess.check_output(["termux-battery-status"], timeout=1.5).decode()
        return float(json.loads(out).get("temperature", 31.0))
    except Exception:
        return 31.0

def eth_mempool_listener():
    try:
        import websockets, asyncio
        async def watch():
            async for ws in websockets.connect("wss://://publicnode.com"):
                try:
                    await ws.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newPendingTransactions"]}))
                    count, batch = 0, []
                    while True:
                        msg = json.loads(await ws.recv())
                        tx = msg.get("params", {}).get("result")
                        if tx:
                            batch.append(tx)
                            if len(batch) >= 15:
                                count += len(batch)
                                log_db("eth-mempool", f"ETH-MAINNET TX #{count}: {batch[:14]}...", float(count))
                                batch.clear()
                except Exception:
                    await asyncio.sleep(3)
        asyncio.run(watch())
    except Exception:
        # Fallback if websockets package isn't installed yet
        while True:
            time.sleep(15)

threading.Thread(target=eth_mempool_listener, daemon=True).start()

def compute_tensor(seed):
    acc = 0.0
    for i in range(1, 32000):
        acc += math.sin(i * seed) * math.cos(i / (seed + 1.0))
    return acc

cycle = 0
while True:
    temp = get_temp_c()
    throttled = temp >= 38.0
    workers = 1 if throttled else 4
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(compute_tensor, [1.1 * (i + 1) for i in range(workers)]))
    dt = max(1e-6, time.perf_counter() - t0)
    gflops = round(((workers * 32000 * 4) / dt) / 1e6, 2)
    cycle += 1
    mode = f"THROTTLED-1T ({temp}C)" if throttled else f"HPC-4T ({temp}C)"
    log_db("python-worker", f"{mode} {gflops} MFLOPS", gflops)
    time.sleep(2.5 if throttled else 0.9)
