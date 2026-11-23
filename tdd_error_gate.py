#!/usr/bin/env python3
"""
SalathanieAI — TDD & Error-Coding Verification Gate
Runs syntax checks, static error-coding checks, and live endpoint assertions.
Additive & non-destructive: reports pass/fail clearly.
"""
import ast
import json
import re
import sys
import urllib.request
from pathlib import Path

HOME = Path.home()
REPO = HOME / "live-command-center"


def check_syntax_and_traps(files: list[Path]) -> list[str]:
    issues = []
    for f in files:
        if not f.exists():
            continue
        try:
            src = f.read_text(encoding="utf-8", errors="ignore")
            ast.parse(src, filename=str(f))
        except SyntaxError as e:
            issues.append(f"[SYNTAX] {f}:{e.lineno} -> {e.msg}")
            continue

        # Detect unindented top-level self.* calls (caused NameError in nexus)
        for idx, line in enumerate(src.splitlines(), 1):
            if re.match(r"^self\.[A-Za-z0-9_]+\s*\(", line):
                issues.append(f"[ERROR-TRAP] {f}:{idx} -> top-level unindented self.* call")
    return issues


def check_endpoints() -> list[str]:
    failures = []
    checks = [
        ("http://127.0.0.1:8090/api/flying-car/step", "json"),
        ("http://127.0.0.1:8101/api/hub/state", "json"),
        ("http://127.0.0.1:8102/api/hub/state", "json"),
        ("http://127.0.0.1:8125/api/evtol/szero-plus", "json"),
        ("http://127.0.0.1:8132/", "html"),
        ("http://127.0.0.1:8140/health", "json"),
    ]
    for url, kind in checks:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                raw = r.read().decode("utf-8", errors="ignore")
                if r.status != 200:
                    failures.append(f"[HTTP-FAIL] {url} -> status {r.status}")
                elif kind == "json":
                    data = json.loads(raw)
                    if not isinstance(data, dict) or data.get("ok") is False:
                        failures.append(f"[CONTRACT-FAIL] {url} -> unexpected JSON body")
        except Exception as e:
            failures.append(f"[REACH-FAIL] {url} -> {str(e)[:90]}")
    return failures



def run_test_astra_suite() -> list[str]:
    import subprocess
    suite = HOME / "astra-termux-v1/test_astra.py"
    if not suite.exists():
        return ["[MISS-SUITE] ~/astra-termux-v1/test_astra.py not found"]
    try:
        res = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", str(suite.parent), "-p", "test_astra.py"],
            capture_output=True, text=True, timeout=10
        )
        combined = (res.stdout or "") + (res.stderr or "")
        if res.returncode == 0 and "Ran 0 tests" not in combined:
            return []
        res2 = subprocess.run(
            ["python3", str(suite)],
            capture_output=True, text=True, timeout=10
        )
        if res2.returncode == 0:
            return []
        err = (res2.stderr or res2.stdout or res.stderr or "test_astra.py failed").strip().splitlines()[-1]
        return [f"[TEST-ASTRA-FAIL] {err[:120]}"]
    except Exception as e:
        return [f"[TEST-ASTRA-ERR] {str(e)[:120]}"]


def main() -> int:
    targets = [
        HOME / "dashboard_server.py",
        HOME / "alstra_unified_8090_gateway.py",
        HOME / "astra_tdd_guardrails.py",
        HOME / "ai-studio-legal/legal_brain.py",
        HOME / "astra-177b-nexus/astra_177b_nexus.py",
        REPO / "car_port_bridge.py",
        REPO / "avatar_car_hub.py",
        REPO / "szero_plus_evtol_telemetry.py",
        REPO / "main_head_router.py",
        REPO / "ecosystem_router.py",
        HOME / "astra-termux-v1/test_astra.py",
    ]
    trap_issues = check_syntax_and_traps(targets)
    net_issues = check_endpoints()
    suite_issues = run_test_astra_suite()

    print("=== TDD SYNTAX & ERROR-CODING AUDIT ===")
    if trap_issues:
        for t in trap_issues:
            print(" ", t)
    else:
        print("  [PASS] Zero syntax or top-level self.* traps across target files.")

    print("=== TDD TEST_ASTRA SUITE ===")
    if suite_issues:
        for s in suite_issues:
            print(" ", s)
    else:
        print("  [PASS] ~/astra-termux-v1/test_astra.py passed.")

    print("=== TDD LIVE ENDPOINT & CONTRACT ASSERTIONS ===")
    if net_issues:
        for n in net_issues:
            print(" ", n)
    else:
        print("  [PASS] All core telemetry, hub, bridge, and Main Head endpoints passed.")

    total_fail = len(trap_issues) + len(net_issues) + len(suite_issues)
    print(f"=== SUMMARY: {total_fail} issue(s) detected ===")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
