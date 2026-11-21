#!/usr/bin/env python3
"""
Salathanie A.I — Semantic Vector Router (10,000-bit HDC)
Routes incoming requests by Hamming similarity against capability hypervectors
and resolves live target ports dynamically from salathanie_hdc_ring.shm.
"""
import re
import sys
from hdc_shm_bus import HDCSharedMemoryBus, HV_ACTIVE_BYTES, deterministic_hv, hamming_distance


def bundle_tokens(tokens: list[str]) -> bytes:
    """Superpose token hypervectors into a single 10,000-bit binary hypervector (majority vote)."""
    if not tokens:
        return deterministic_hv("EMPTY")
    hvs = [deterministic_hv(f"TOK:{t.lower()}") for t in tokens]
    if len(hvs) == 1:
        return hvs[0]
    out = bytearray(HV_ACTIVE_BYTES)
    half = len(hvs) / 2.0
    for byte_idx in range(HV_ACTIVE_BYTES):
        b_val = 0
        for bit in range(8):
            mask = 1 << bit
            ones = sum(1 for hv in hvs if hv[byte_idx] & mask)
            if ones > half or (ones == half and (byte_idx + bit) % 2 == 0):
                b_val |= mask
        out[byte_idx] = b_val
    return bytes(out)


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9]+", text.lower()) if len(t) >= 2]


SERVICE_CAPABILITIES = {
    "salathanie-wal-8182": {
        "default_port": 8182,
        "tokens": ["wal", "health", "ledger", "sqlite", "db", "event", "events", "log", "metrics", "audit"],
    },
    "astra-ingress-8088": {
        "default_port": 8088,
        "tokens": ["ingress", "spine", "edge", "stream", "ingest", "telemetry", "webhook", "pipe"],
    },
    "astra-spatial-3d-8151": {
        "default_port": 8151,
        "tokens": ["spatial", "3d", "vr", "mesh", "scene", "render", "orbital", "frame", "geometry"],
    },
    "salathanie-gw-8090": {
        "default_port": 8090,
        "tokens": ["gateway", "status", "root", "index", "dashboard", "ui", "command", "center", "api"],
    },
}

SERVICE_VECTORS = {
    name: bundle_tokens(cfg["tokens"]) for name, cfg in SERVICE_CAPABILITIES.items()
}


def route_request(path_or_intent: str) -> dict:
    q_hv = bundle_tokens(tokenize(path_or_intent))
    best_svc, best_dist = "salathanie-gw-8090", 1.0
    for svc, s_hv in SERVICE_VECTORS.items():
        d = hamming_distance(q_hv, s_hv)
        if d < best_dist:
            best_svc, best_dist = svc, d

    with HDCSharedMemoryBus() as bus:
        port = bus.get_active_port(best_svc, SERVICE_CAPABILITIES[best_svc]["default_port"])
        with bus.read_latest_view() as latest:
            ring_attested = bool(latest and latest.get("hmac_ok"))

    return {
        "intent": path_or_intent,
        "target_service": best_svc,
        "target_url": f"http://127.0.0.1:{port}",
        "hamming_dist": round(best_dist, 4),
        "ring_attested": ring_attested,
    }


if __name__ == "__main__":
    queries = sys.argv[1:] or [
        "/api/wal/events/ledger",
        "/vr/spatial/3d/mesh",
        "/spine/telemetry/ingest",
        "/command/dashboard",
    ]
    for q in queries:
        res = route_request(q)
        print(f"[ROUTE] {res['intent']} -> {res['target_service']} ({res['target_url']}) dist={res['hamming_dist']} hmac_ok={res['ring_attested']}")
