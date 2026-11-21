#!/usr/bin/env python3
"""
Salathanie A.I — Lightweight Causal Shadow Daemon
Continuously samples silicon side-channel metrics, publishes 10k-bit hypervectors
to salathanie_hdc_ring.shm, and unbinds S_{t+1} XOR S_t to isolate causal drift.
"""
import argparse
import json
import signal
import sys
import time
from pathlib import Path

from hdc_shm_bus import (
    HDCSharedMemoryBus,
    encode_silicon_hv,
    sample_silicon_side_channel,
    unbind_causal_delta,
)

LOG_PATH = Path("/data/data/com.termux/files/home/live-command-center/causal_deltas.jsonl")
RUNNING = True


def _handle_stop(signum, frame):
    global RUNNING
    RUNNING = False


def run(interval: float = 2.0, once: bool = False):
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    hv_prev = None
    tick = 0

    with HDCSharedMemoryBus() as bus:
        while RUNNING:
            metrics = sample_silicon_side_channel()
            gw_port = bus.get_active_port("salathanie-gw-8090", 8090)
            sig = f"gw:{gw_port}:UP|mem:{metrics['mem_avail_kb']//1024}MB"
            hv_curr = encode_silicon_hv(metrics, sig)

            seq = bus.publish("salathanie-causal-shadow", 0, 200, hv_curr)
            cause, dist = ("INIT", 0.0) if hv_prev is None else unbind_causal_delta(hv_prev, hv_curr)

            if cause not in ("INIT", "NOMINAL") or tick % 30 == 0 or once:
                entry = {
                    "ts": int(time.time()),
                    "seq": seq,
                    "gw_port": gw_port,
                    "cause": cause,
                    "dist": round(dist, 4),
                    "jitter_ns": metrics["jitter_ns"],
                    "temp_mc": metrics["max_temp_mc"],
                    "mem_avail_mb": metrics["mem_avail_kb"] // 1024,
                }
                line = json.dumps(entry)
                print(line, flush=True)
                if cause not in ("INIT", "NOMINAL"):
                    with LOG_PATH.open("a", encoding="utf-8") as f:
                        f.write(line + "\n")

            hv_prev = hv_curr
            tick += 1
            if once:
                break
            time.sleep(interval)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    run(interval=args.interval, once=args.once)
