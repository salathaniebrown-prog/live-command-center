import json, time, math, os, random
from concurrent.futures import ThreadPoolExecutor

def compute_tensor_block(seed):
    acc = 0.0
    for i in range(1, 35000):
        acc += math.sin(i * seed) * math.cos(i / (seed + 1.0))
    return acc

cycle = 0
with ThreadPoolExecutor(max_workers=4) as pool:
    while True:
        t0 = time.perf_counter()
        results = list(pool.map(compute_tensor_block, [1.1, 2.3, 3.7, 5.1]))
        dt = max(1e-6, time.perf_counter() - t0)
        ops = 4 * 35000 * 4
        gflops = round((ops / dt) / 1e6, 2)
        cycle += 1
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "python-worker",
            "status": f"HPC-4T {gflops} MFLOPS",
            "data": {"tasks_completed": cycle, "gflops": gflops, "checksum": round(sum(results), 4)}
        }
        with open("telemetry_spine.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")
        time.sleep(0.8)
