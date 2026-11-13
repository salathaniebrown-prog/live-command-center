import os, sys, json, time, sqlite3, subprocess, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = os.path.expanduser("~/astra-mediapipe-tasks")
OUT_FILE = os.path.join(BASE, "test_1030_results.json")
DB_FILE = os.path.join(BASE, "mediapipe_tasks.db")
LOCAL = "http://127.0.0" + ".1"

def run_cmd(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {"ok": p.returncode == 0, "output": (p.stdout or p.stderr).strip()[:600]}
    except Exception as e:
        return {"ok": False, "output": str(e)}

def check_http(name, url, headers=None, payload=None, timeout=10):
    try:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if payload is not None else "GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode(errors="ignore")[:300]
            return {"service": name, "status": "ONLINE", "http_code": r.status, "sample": body}
    except Exception as e:
        return {"service": name, "status": "OFFLINE_OR_UNCONFIGURED", "detail": str(e)[:150]}

def check_ollama():
    ollama_base = f"{LOCAL}:11434"
    tags = check_http("Ollama_Tags", f"{ollama_base}/api/tags", timeout=5)
    if tags["status"] != "ONLINE":
        return {"status": "OFFLINE", "detail": f"Ollama server not listening on {ollama_base}"}
    try:
        models = [m["name"] for m in json.loads(tags.get("sample", "{}")).get("models", [])]
    except Exception:
        models = []
    target_model = models[0] if models else "llama3.2:1b"
    infer = check_http(
        "Ollama_Generate",
        f"{ollama_base}/api/generate",
        {"Content-Type": "application/json"},
        {"model": target_model, "prompt": "Reply with READY", "stream": False},
        timeout=25
    )
    return {"status": "ONLINE", "installed_models": models, "tested_model": target_model, "inference": infer}

def check_github_cli():
    auth = run_cmd("gh auth status 2>&1")
    runs = run_cmd("gh run list --repo salathaniebrown-prog/live-command-center --limit 5 --json databaseId,workflowName,status,conclusion,headBranch 2>&1")
    trigger = run_cmd("gh workflow run astra-ci.yml --repo salathaniebrown-prog/live-command-center 2>&1")
    return {"auth": auth, "recent_runs": runs, "ci_dispatch": trigger}

def persist_sqlite(results):
    c = sqlite3.connect(DB_FILE)
    c.execute("CREATE TABLE IF NOT EXISTS scheduled_test_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, pass_count INTEGER, total_checks INTEGER, report_json TEXT, ts REAL)")
    checks = [
        results["local_services"]["dashboard_8088"]["status"] == "ONLINE",
        results["local_services"]["mediapipe_8113"]["status"] == "ONLINE",
        results["termux_build_and_code"]["python_compile"]["ok"],
        results["termux_build_and_code"]["playback_benchmark"]["status"] == "ONLINE",
        results["github_sync"]["git_remote_verify"]["ok"],
    ]
    c.execute("INSERT INTO scheduled_test_runs(pass_count, total_checks, report_json, ts) VALUES(?,?,?,?)", (sum(1 for x in checks if x), len(checks), json.dumps(results), time.time()))
    c.commit()
    c.close()

def wait_until_1030_est():
    tz = ZoneInfo("America/New_York")
    while True:
        now = datetime.now(tz)
        if now.hour > 22 or (now.hour == 22 and now.minute >= 30):
            break
        time.sleep(20)

def run_full_suite():
    gem_host = "generativelanguage." + "googleapis." + "com"
    oai_host = "api." + "openai." + "com"
    results = {
        "local_services": {
            "dashboard_8088": check_http("Dashboard", f"{LOCAL}:8088/"),
            "mediapipe_8113": check_http("MediaPipe_Tasks", f"{LOCAL}:8113/"),
        },
        "ollama_local_models": check_ollama(),
        "termux_build_and_code": {
            "python_compile": run_cmd("python3 -m py_compile ~/dashboard_server.py ~/astra-mediapipe-tasks/mediapipe_edge_ml.py ~/astra-mediapipe-tasks/sdks/python/astra_desktop_ml.py"),
            "playback_benchmark": check_http("Model_Playback", f"{LOCAL}:8113/playback", {"Content-Type": "application/json"}, {})
        },
        "github_sync": {
            "git_status_count": run_cmd("git -C ~ status -s | wc -l"),
            "git_remote_verify": run_cmd("git -C ~ ls-remote --heads origin main"),
            "github_cli": check_github_cli()
        },
        "docker_runtime": run_cmd("docker --version && docker ps 2>&1 || echo 'Docker daemon unavailable in unrooted Termux'"),
        "external_apis": {
            "gemini": check_http("Gemini_API", f"https://{gem_host}/v1beta/models?key={os.environ.get('GEMINI_API_KEY','')}") if os.environ.get("GEMINI_API_KEY") else {"status": "SKIPPED"},
            "openai": check_http("OpenAI_API", f"https://{oai_host}/v1/models", {"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY','')}"}) if os.environ.get("OPENAI_API_KEY") else {"status": "SKIPPED"},
            "ibm": {"status": "CONFIGURED" if os.environ.get("IBM_API_KEY") else "SKIPPED"}
        }
    }
    persist_sqlite(results)
    with open(OUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    return results

if __name__ == "__main__":
    if "--now" not in sys.argv:
        wait_until_1030_est()
    out = run_full_suite()
    print(json.dumps(out, indent=2))
