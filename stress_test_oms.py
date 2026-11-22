#!/usr/bin/env python3
"""
Salathanie A.I — OMS, Web Trader & FIX 4.4 / FAST Wire Stress Harness
"""
import json
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8125"
WIRE_LOG = Path("/data/data/com.termux/files/usr/tmp/salathanie_fix_fast_capture.log")


def req(path: str) -> tuple[dict, float]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(BASE + path, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data, (time.perf_counter() - t0) * 1000.0


def main():
    wire_lines = []
    latencies = []

    # 1. Market BUY BTCUSD
    r1, ms1 = req("/api/oms/order?symbol=BTCUSD&side=BUY&qty=0.5&type=MARKET")
    latencies.append(ms1)
    assert r1.get("ok") and r1["status"] == "FILLED", f"Market buy failed: {r1}"
    wire_lines.append(f"[FIX_NEW]  {r1['fix_new_order']['fix_readable']}")
    wire_lines.append(f"[FIX_EXEC] {r1['fix_exec_report']['fix_readable']}")
    wire_lines.append(f"[FAST_HEX] {r1['fast_packet']['fast_hex']} ({r1['fast_packet']['bytes']}B)")

    # 2. Working LIMIT BUY ETHUSD below market -> then CANCEL
    r2, ms2 = req("/api/oms/order?symbol=ETHUSD&side=BUY&qty=2.0&type=LIMIT&price=1500")
    latencies.append(ms2)
    assert r2.get("ok") and r2["status"] == "WORKING", f"Limit buy failed: {r2}"
    rc, msc = req(f"/api/oms/cancel?id={r2['order_id']}")
    latencies.append(msc)
    assert rc.get("ok") and rc["status"] == "CANCELED", f"Cancel failed: {rc}"
    wire_lines.append(f"[FIX_CXL]  {rc['fix_cancel_report']['fix_readable']}")

    # 3. Partial SELL BTCUSD + 20-order multi-symbol burst
    burst_plan = [
        ("BTCUSD", "SELL", 0.2), ("NVDA", "BUY", 10), ("SPY", "BUY", 5),
        ("SOLUSD", "BUY", 4), ("EURUSD", "BUY", 1000), ("ETHUSD", "BUY", 1.0),
    ]
    t_burst = time.perf_counter()
    burst_ok = 0
    for i in range(20):
        sym, side, qty = burst_plan[i % len(burst_plan)]
        res, ms = req(f"/api/oms/order?symbol={sym}&side={side}&qty={qty}&type=MARKET")
        latencies.append(ms)
        if res.get("ok") and res["status"] == "FILLED":
            burst_ok += 1
            wire_lines.append(f"[BURST {i+1:02d}] {sym} {side} {qty} | FIX={res['fix_exec_report']['bytes']}B | FAST={res['fast_packet']['fast_hex']}")
    burst_sec = time.perf_counter() - t_burst

    WIRE_LOG.write_text("\n".join(wire_lines) + "\n", encoding="utf-8")
    state, _ = req("/api/oms/state")

    p50 = round(statistics.median(latencies), 2)
    p99 = round(sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)], 2)

    print("=== OMS & FIX 4.4 / FAST STRESS TEST PASS ===")
    print(f"Lifecycle : Market BUY=FILLED | Limit BUY=WORKING -> CANCELED (id={r2['order_id']})")
    print(f"Burst     : {burst_ok}/20 filled in {burst_sec:.2f}s ({burst_ok/max(burst_sec,1e-6):.1f} ord/sec)")
    print(f"Latency   : P50={p50} ms | P99={p99} ms | Max={round(max(latencies),2)} ms")
    print(f"Wire Log  : {WIRE_LOG} ({len(wire_lines)} frames captured)")
    print("\n--- Active Positions ---")
    for pos in state.get("positions", []):
        print(f"  {pos['symbol']:6s} | qty={pos['net_qty']:<8} | avg={pos['avg_price']:<10} | uPnL=${pos['unrealized_pnl']:<8} | rPnL=${pos['realized_pnl']}")
    print("\n--- Sample FIX 4.4 & FAST Wire ---")
    for ln in wire_lines[:4]:
        print(" ", ln[:140])


if __name__ == "__main__":
    main()
