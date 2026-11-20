import argparse, json, math, os, socket, struct, sys, threading, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path.home()))
from astra_shm_schema import AstraBusFrame, FRAME_SIZE, MAGIC, open_shm, read_frame_lockfree, read_ring_snapshot

def cpu_starve_worker(stop_evt, target_core):
    try:
        os.sched_setaffinity(0, {target_core})
    except Exception:
        pass
    x = 1.0001
    while not stop_evt.is_set():
        x = (x * 1.000001) % 997.0

def run_packet_burst(host, port, count):
    latencies_us = []
    ok = 0
    for i in range(1, count + 1):
        t0 = time.perf_counter_ns()
        try:
            with socket.create_connection((host, port), timeout=1.0) as s:
                s.sendall(struct.pack("<d", float(i) * 3.14159))
                resp = s.recv(FRAME_SIZE)
                if len(resp) == FRAME_SIZE:
                    ok += 1
            latencies_us.append((time.perf_counter_ns() - t0) / 1000.0)
        except OSError:
            pass
    latencies_us.sort()
    p50 = latencies_us[len(latencies_us)//2] if latencies_us else 0.0
    p99 = latencies_us[int(len(latencies_us)*0.99)] if latencies_us else 0.0
    return ok, p50, p99

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--burst", type=int, default=200, help="Number of raw 8B packets to fire at :8088")
    ap.add_argument("--starve-sec", type=float, default=2.0, help="CPU starvation duration on ingress core")
    ap.add_argument("--ci", action="store_true", help="Headless CI mode (validates mmap schema + burst only)")
    args = ap.parse_args()

    mm = open_shm(create=False)
    before = read_frame_lockfree(mm)
    start_core = before.pinned_core
    start_act = before.actuations
    start_pkts = before.ingress_pkts

    print(f"=== ASTRA CHAOS BENCHMARK (Burst={args.burst}, Starve={args.starve_sec}s) ===")
    print(f"[BEFORE] seq={before.seq} core={start_core} actuations={start_act} pkts={start_pkts}")

    stop_evt = threading.Event()
    starvers = []
    if not args.ci and args.starve_sec > 0:
        for _ in range(2):
            t = threading.Thread(target=cpu_starve_worker, args=(stop_evt, start_core), daemon=True)
            t.start()
            starvers.append(t)

    t0 = time.perf_counter()
    ok, p50, p99 = run_packet_burst("127.0.0.1", 8088, args.burst)
    elapsed = time.perf_counter() - t0

    if starvers:
        rem = max(0.0, args.starve_sec - elapsed)
        if rem > 0:
            time.sleep(rem)
        stop_evt.set()
        for t in starvers:
            t.join(timeout=1.0)

    after = read_frame_lockfree(mm)
    mm.close()
    ring = read_ring_snapshot(128)

    # Verify :8090 HTTP bus endpoint if not in headless CI
    gw_ok = True
    if not args.ci:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8090/api/bus/frame", timeout=2.0) as r:
                gw_ok = (r.status == 200 and json.loads(r.read())["magic"] == hex(MAGIC))
        except Exception:
            gw_ok = False

    pkt_delta = after.ingress_pkts - start_pkts
    pps = ok / max(elapsed, 0.001)
    print(f"[BURST]  ok={ok}/{args.burst} ({pps:.0f} pkt/s) | p50={p50:.1f} us | p99={p99:.1f} us")
    print(f"[AFTER]  seq={after.seq} core={after.pinned_core} actuations={after.actuations} pkts_delta={pkt_delta}")
    print(f"[RING]   slots_valid={len(ring)} | frame_bytes={FRAME_SIZE} | gw_8090={'PASS' if gw_ok else 'FAIL'}")

    assert after.magic == MAGIC, "Corrupt SHM magic"
    assert ok >= int(args.burst * 0.95), f"Packet loss exceeded 5% ({ok}/{args.burst})"
    assert len(ring) > 0, "Persistent mmap ring buffer empty"
    assert gw_ok, "Gateway :8090 /api/bus/frame check failed"
    print("[PASS]   ALL CHAOS & REGRESSION CHECKS PASSED")

if __name__ == "__main__":
    main()
