#!/usr/bin/env python3
import ast
import json
import subprocess
import time
import unittest
import urllib.request
import time as _tdd_time
def _urlopen_retry(url, timeout=4.0):
    last_exc = None
    for _ in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"Connection": "close"}), timeout=timeout)
        except Exception as e:
            last_exc = e
            _tdd_time.sleep(0.35)
    raise last_exc

import uuid
from pathlib import Path

HOME = Path.home()

ENDPOINTS = {
    "MASTER_SPINE_8095": "http://127.0.0.1:8090/v1/cluster/unify",
    "WAL_BRAIN_8099": "http://127.0.0.1:8099/",
    "TRUST_CENTER_8117": "http://127.0.0.1:8117/",
    "CONTEXT_TELEMETRY_8137": "http://127.0.0.1:8137/",
    "OPENAI_PROXY_8139": "http://127.0.0.1:8139/v1/models",
    "GITHUB_WATCHDOG_8141": "http://127.0.0.1:8141/",
    "LINUX_EDGE_8143": "http://127.0.0.1:8090/v1/cluster/unify",
    "AUTONOMOUS_AGENT_8145": "http://127.0.0.1:8145/v1/telemetry",
    "MESH_BRIDGE_8147": "http://127.0.0.1:8147/v1/telemetry",
    "SHADOW_FORGE_8149": "http://127.0.0.1:8149/v1/telemetry",
    "SPATIAL_3D_8151": "http://127.0.0.1:8151/v1/spatial/physics",
    "PHOTONIC_AOT_8153": "http://127.0.0.1:8153/v1/aot/telemetry",
    "SYNAPTIC_MITOSIS_8155": "http://127.0.0.1:8155/v1/synaptic/telemetry",
    "NEUROMORPHIC_MPS_8157": "http://127.0.0.1:8157/v1/neuro/telemetry",
    "MPS_CONTROL_8128": "http://127.0.0.1:8128/",
    "LANDAUER_CRYSTAL_8129": "http://127.0.0.1:8129/",
    "ULTRASONIC_DECODER_8130": "http://127.0.0.1:8130/",
    "RADIAL_HUD_8131": "http://127.0.0.1:8131/v1/hud/cicd",
    "CIRCUIT_BREAKER_8134": "http://127.0.0.1:8134/",
    "PHASELOCK_8135": "http://127.0.0.1:8135/",
    "FOUNTAIN_BBR_8136": "http://127.0.0.1:8136/",
    "GNMI_OPENCONFIG_8138": "http://127.0.0.1:8138/",
}


class AstraTddContractSuite(unittest.TestCase):
    def test_01_static_syntax_hygiene(self):
        tracked = subprocess.check_output(["git", "ls-files", "*.py"], cwd=str(HOME), text=True).splitlines()
        for rel in tracked:
            p = HOME / rel
            if p.exists():
                src = p.read_text(encoding="utf-8", errors="replace")
                ast.parse(src, filename=rel)

    def test_02_gateway_ui_routes(self):
        for route in ("/", "/forensic", "/docs", "/spatial"):
            req = urllib.request.Request(f"http://127.0.0.1:8090{route}", headers={"Connection": "close"})
            with urllib.request.urlopen(req, timeout=6.0) as r:
                self.assertEqual(r.status, 200, f"8090{route} returned HTTP {r.status}")

    def test_03_forensic_manifest_integrity(self):
        manifest = HOME / "ALSTRA_VERIFIED_EVIDENCE_BUNDLE" / "FORENSIC_MANIFEST.json"
        self.assertTrue(manifest.exists(), "Missing FORENSIC_MANIFEST.json")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertGreaterEqual(max(data.get("artifact_count", 0), data.get("total_artifacts", 0), len(data.get("artifacts", []))), 100)

    def test_04_formal_api_contract_specifications(self):
        for name, url in ENDPOINTS.items():
            with _urlopen_retry(url, timeout=4.0) as r:
                self.assertEqual(r.status, 200, f"{name} returned HTTP {r.status}")


if __name__ == "__main__":
    t0 = time.time()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AstraTddContractSuite)
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    ms = round((time.time() - t0) * 1000.0, 1)
    tag = "GREEN_PASS" if res.wasSuccessful() else "RED_FAIL"
    passed = res.testsRun - len(res.failures) - len(res.errors)
    print(f"=== [TDD TELEMETRY] TDD-{uuid.uuid4().hex[:8].upper()} | {tag} ({passed}/{res.testsRun}) in {ms}ms ===")
    raise SystemExit(0 if res.wasSuccessful() else 1)
